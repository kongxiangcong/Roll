"""Supplier research context, kept separate from admitted issuer/market facts."""
import time
import json
import os
import httpx

from roll.accounts.ledger import now
from roll.market import miaoxiang, source_policy
from roll.market import fuyao, baostock


def collect(store, request, run, archives, deadline, cancel, byte_budget):
    results = []
    consumed = 0
    for instrument in request['instruments']:
        remaining = request['max_calls']-sum(t.get('network_calls', 1) for t in run['tools'])
        if remaining < 1 or byte_budget-consumed <= 0 or time.monotonic() >= deadline or (cancel and cancel.is_set()):
            break
        entry = dict(instrument=instrument, provider='MIAOXIANG', status='FAILED',
                     admitted_as_fact=False, historical_pit=False, received_at=now(), raw_hashes=[])
        results.append(entry)
        tool = 'mx_ashare_finance_data' if 'PERFORMANCE' in request['groups'] else 'mx_finance_search_notice'
        question = (f"查询{instrument}在{request['start_date']}至{request['end_date']}期间的"
                    + ('财务指标及报告期、披露日期、单位与原始来源。' if 'PERFORMANCE' in request['groups'] else '公告与重大事项，返回披露日期及原始公告链接。')
                    + '返回缺失项，不推测；仅供当前取得的研究参考。')
        start_calls = len(run['tools'])

        def archive(raw, status, method):
            saved = store.archive(raw, 'MCP_RESPONSE', source_id='miaoxiang-research', source_url=miaoxiang.URL,
                                  received_at=now(), http_status=status, evidence_kind=store.evidence_kind)
            archives.append(saved)
            entry['raw_hashes'].append(saved['sha256'])
            run['tools'].append(dict(source_id='miaoxiang-research', instrument=instrument, group='RESEARCH_CONTEXT',
                method='POST', mcp_method=method, raw_hash=saved['sha256'], http_status=status, network_calls=1,
                received_bytes=len(raw), status='ARCHIVED'))
        def count_bytes(size):
            nonlocal consumed
            consumed+=size
        try:
            if source_policy.health(store, 'MIAOXIANG'):
                raise ValueError('MX_COOLDOWN_ACTIVE')
            if remaining<3:
                raise ValueError('MX_INITIALIZATION_BUDGET_UNAVAILABLE')
            entry['content'] = miaoxiang.query(tool, question, transport=store.transport, deadline=deadline,
                cancel_event=cancel, max_calls=remaining, max_bytes=byte_budget-consumed, on_response=archive,on_bytes=count_bytes)
            entry['status'] = 'ACQUIRED_REFERENCE'
        except (ValueError, OSError) as error:
            code = str(error) if isinstance(error, ValueError) and str(error).startswith('MX_') else 'MX_REQUEST_FAILED'
            entry['error'] = code
            if len(run['tools'])-start_calls < 3 and code not in {'MX_CREDENTIAL_UNAVAILABLE','MX_COOLDOWN_ACTIVE','MX_INITIALIZATION_BUDGET_UNAVAILABLE'}:
                run['tools'].append(dict(source_id='miaoxiang-research', instrument=instrument, group='RESEARCH_CONTEXT',
                    status='FAILED', code=code, network_calls=3-(len(run['tools'])-start_calls),
                    network_calls_basis='CONSERVATIVE_FAILURE_UPPER_BOUND'))
            if code in {'MX_QUOTA_EXHAUSTED', 'MX_RATE_LIMITED', 'MX_AUTH_FAILED', 'MX_CREDENTIAL_UNAVAILABLE'}:
                source_policy.health(store, 'MIAOXIANG', code)
            remaining = request['max_calls']-sum(t.get('network_calls', 1) for t in run['tools'])
            if request.get('research_fallback') and remaining and time.monotonic()<deadline and byte_budget>consumed and not (cancel and cancel.is_set()):
                fallback, used = fuyao_reference(store, request, instrument, run, archives,
                                                deadline, cancel, byte_budget-consumed)
                results.append(fallback)
                consumed += used
    return results, consumed


def fuyao_reference(store, request, instrument, run, archives, deadline, cancel, byte_budget):
    entry = dict(instrument=instrument, provider='FUYAO', status='FAILED', admitted_as_fact=False,
                 historical_pit=False, received_at=now(), raw_hashes=[], role='FALLBACK_RESEARCH_REFERENCE')
    size = 0
    try:
        financial = 'PERFORMANCE' in request['groups']
        capability='FUYAO_RESEARCH_FINANCIAL' if financial else 'FUYAO_RESEARCH_NEWS'
        key = os.environ.get('FUYAO_API_KEY')
        if not key:
            raise ValueError('FUYAO_CREDENTIAL_NOT_CONFIGURED')
        if source_policy.health(store, 'FUYAO') or source_policy.health(store,capability):
            raise ValueError('FUYAO_COOLDOWN_ACTIVE')
        path = '/api/a-share/financials/income-statements' if financial else '/api/news/stock/timeline-list'
        params = dict(thscode=fuyao.symbol(instrument))
        params.update(dict(period='quarterly', start=fuyao.millis(request['start_date']),
                           end=fuyao.millis(request['end_date'],True)) if financial else dict(offset='first'))
        tool = dict(source_id='fuyao-research', group='RESEARCH_CONTEXT', instrument=instrument,
                    method='GET', status='FAILED', network_calls=1)
        run['tools'].append(tool)
        with httpx.Client(transport=store.transport, follow_redirects=False) as client:
            with client.stream('GET', fuyao.BASE+path, params=params, headers={'X-api-key':key},
                               timeout=min(10,max(.1,deadline-time.monotonic()))) as response:
                raw = bytearray()
                for chunk in response.iter_bytes(4096):
                    size += len(chunk)
                    if size>byte_budget or time.monotonic()>=deadline or (cancel and cancel.is_set()):
                        raise ValueError('FUYAO_TECHNICAL_LIMIT')
                    raw.extend(chunk)
                if baostock.reflected(bytes(raw)):
                    raise ValueError('FUYAO_SECRET_REFLECTED_RESPONSE_REJECTED')
                saved = store.archive(bytes(raw),'RESEARCH_RESPONSE',source_id='fuyao-research',
                    source_url=str(response.url),received_at=now(),http_status=response.status_code,evidence_kind=store.evidence_kind)
                archives.append(saved);entry['raw_hashes'].append(saved['sha256'])
                tool.update(raw_hash=saved['sha256'],http_status=response.status_code,received_bytes=size)
                if response.status_code in {401,403,429}:
                    source_policy.health(store,'FUYAO','HTTP_'+str(response.status_code))
                response.raise_for_status()
                value=json.loads(raw)
                if not isinstance(value,dict):raise ValueError('FUYAO_RESPONSE_INVALID')
                if type(value.get('code')) is not int or value['code']!=0:
                    code=value.get('code')
                    if type(code) is int and code in {2001,2003,4001}:
                        source_policy.health(store,capability if code==2003 else 'FUYAO','BUSINESS_'+str(code))
                    raise ValueError('FUYAO_BUSINESS_ERROR')
                data=value.get('data')
                rows=data.get('item' if financial else 'items') if isinstance(data,dict) else None
                if not isinstance(rows,list) or not rows:
                    raise ValueError('FUYAO_NO_REFERENCE_DATA')
                # Preserve provider output without converting it to issuer facts or
                # claiming the news endpoint implements the requested historical window.
                entry.update(status='ACQUIRED_REFERENCE',content=value,
                    reference_kind='FINANCIAL_REFERENCE' if financial else 'NEWS_REFERENCE',
                    scope='REPORT_PERIOD_WINDOW' if financial else 'LATEST_NEWS_CONTEXT_NOT_NOTICE_OR_HISTORICAL_COVERAGE')
                tool['status']='ARCHIVED'
    except (ValueError,KeyError,OSError,httpx.HTTPError) as error:
        entry['error']=str(error) if isinstance(error,ValueError) and str(error).startswith('FUYAO_') else 'FUYAO_REFERENCE_FAILED'
    return entry, size
