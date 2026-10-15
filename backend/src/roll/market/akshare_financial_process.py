"""Pinned AKShare API with bounded raw-first anonymous transport in its own process."""
import contextlib
from datetime import date,datetime,timezone
import hashlib
from importlib.metadata import version
from importlib.util import find_spec
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit,parse_qs

SDK_VERSION='1.19.1'
SDK_SOURCE_SHA='e9cb438a5e033e9ba2d14c0341528b1aeec3f162fb2c0e5cbff41a6bc293348e'
HOST='emweb.securities.eastmoney.com'
PREFIX='/PC_HSF10/NewFinanceAnalysis/'
SOURCE_PATHS={'Index','lrbDateAjaxNew','lrbAjaxNew','zcfzbDateAjaxNew','zcfzbAjaxNew','xjllbDateAjaxNew','xjllbAjaxNew'}


def main(command):
    output=Path(command['output_directory']);output.mkdir(parents=True,exist_ok=True)
    state={'sdk_version':SDK_VERSION,'sdk_source_sha256':SDK_SOURCE_SHA,'status':'FAILED',
        'captures':[],'date_selections':{},'date_selection':None,'sdk_result':None,'errors':[],
        'evidence_kind':'METHOD_CASE' if command.get('fixture') else 'REAL_SOURCE_ASSESSMENT'}
    def save():
        temporary=output/'capture.json.tmp'
        temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(output/'capture.json')
    save()
    try:
        import requests
        package=find_spec('akshare')
        source_file=Path(package.origin).parent/'stock_feature/stock_three_report_em.py' if package else None
        if version('akshare')!=SDK_VERSION or source_file is None or hashlib.sha256(source_file.read_bytes()).hexdigest()!=SDK_SOURCE_SHA:
            raise ValueError('AKSHARE_VERSION_OR_SOURCE_MISMATCH')
        if command['instrument']!='SSE:600362':raise ValueError('AKSHARE_FINANCIAL_SCOPE_NOT_ACCEPTED')
        supplement=command.get('statement','INCOME')=='SUPPLEMENT'
        allowed={'Index','zcfzbDateAjaxNew','zcfzbAjaxNew','xjllbDateAjaxNew','xjllbAjaxNew'} if supplement else {'Index','lrbDateAjaxNew','lrbAjaxNew'}
        symbol='SH600362';used=0;selected=[]
        original_init=requests.Session.__init__;original_send=requests.Session.send
        def anonymous(session,*args,**kwargs):
            original_init(session,*args,**kwargs);session.trust_env=False
        requests.Session.__init__=anonymous
        fixtures=None
        if command.get('fixture'):
            import os
            if os.environ.get('ROLL_ENV')!='test':raise ValueError('FINANCIAL_FIXTURE_TEST_ONLY')
            fixtures=json.loads(Path(command['fixture']).read_text(encoding='utf-8'))
        def send(session,request,**kwargs):
            nonlocal used,selected
            parsed=urlsplit(request.url);query=parse_qs(parsed.query,keep_blank_values=True)
            role=parsed.path.removeprefix(PREFIX)
            if parsed.scheme!='https' or parsed.hostname!=HOST or parsed.port not in (None,443) or role not in allowed or request.method!='GET':
                raise ValueError('AKSHARE_FINANCIAL_UNAPPROVED_REQUEST')
            if query.get('code')!=[symbol.lower() if role=='Index' else symbol]:raise ValueError('AKSHARE_FINANCIAL_SYMBOL_MISMATCH')
            if role in ('lrbAjaxNew','zcfzbAjaxNew','xjllbAjaxNew') and query.get('dates')!=[','.join(selected)]:raise ValueError('AKSHARE_FINANCIAL_DATE_SELECTION_MISMATCH')
            remaining=command['deadline_at']-time.time()
            if len(state['captures'])>=8 or remaining<=0:raise ValueError('AKSHARE_FINANCIAL_CALL_OR_TIME_BUDGET')
            kwargs.update(timeout=max(.01,remaining),stream=True,allow_redirects=False)
            captured={'ordinal':len(state['captures'])+1,'url':request.url,'parameters':query,'role':role,
                'received_at':None,'status_code':None,'original_complete':False,'raw_file':None}
            state['captures'].append(captured);save()
            if fixtures is not None:
                response=requests.Response();entry=fixtures[role]
                response.status_code=entry.get('status_code',200);response.url=request.url
                response._content=entry['body'].encode();response._content_consumed=True
                if entry.get('pause_after_prefix_seconds'):
                    def slow_chunks(chunk_size):
                        yield response._content[:8192]
                        time.sleep(entry['pause_after_prefix_seconds'])
                        yield response._content[8192:]
                    response.iter_content=slow_chunks
            else:response=original_send(session,request,**kwargs)
            body=bytearray();captured['status_code']=response.status_code
            name=f"{captured['ordinal']:02}.raw"
            try:
                with (output/name).open('wb') as stream:
                    for part in response.iter_content(chunk_size=65536):
                        available=8*1024*1024-used;prefix=part[:available]
                        body.extend(prefix);used+=len(prefix)
                        # A hard parent kill cannot execute finally. Persist every
                        # application-received chunk before waiting on the stream.
                        stream.write(prefix);stream.flush()
                        captured.update(raw_file=name,bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),
                            received_at=datetime.now(timezone.utc).isoformat(),body_representation='HTTP_DECODED_ENTITY')
                        save()
                        if len(part)>available:raise ValueError('AKSHARE_FINANCIAL_BYTE_BUDGET_PREFIX')
                        if time.time()>command['deadline_at']:raise ValueError('AKSHARE_FINANCIAL_TIME_BUDGET')
                    captured['original_complete']=True
            finally:
                captured.update(raw_file=name,bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),
                    received_at=datetime.now(timezone.utc).isoformat(),body_representation='HTTP_DECODED_ENTITY')
                response.close();save()
            if response.status_code!=200:raise ValueError('AKSHARE_FINANCIAL_HTTP_'+str(response.status_code))
            response._content=bytes(body);response._content_consumed=True
            if role in ('lrbDateAjaxNew','zcfzbDateAjaxNew','xjllbDateAjaxNew'):
                value=json.loads(body);rows=value.get('data')
                if not isinstance(rows,list) or not rows:raise ValueError('AKSHARE_FINANCIAL_PERIODS_EMPTY_OR_UNKNOWN')
                periods={str(row['REPORT_DATE'])[:10] for row in rows}
                if any(date.fromisoformat(d)>datetime.now(timezone.utc).date() for d in periods):raise ValueError('AKSHARE_FINANCIAL_FUTURE_PERIOD')
                selected=sorted(periods,reverse=True)[:5]
                chosen=[next(r for r in rows if str(r['REPORT_DATE'])[:10]==d) for d in selected]
                state['date_selection']={'raw_sha256':captured['sha256'],'reported_index_rows':len(rows),
                    'selected_report_dates':selected,'selection':'LATEST_FIVE_DISTINCT_REPORT_PERIODS',
                    'library_input_is_derived':True,'upstream_original_is_unchanged':True}
                response.json=lambda **kw:{**value,'data':chosen}
                statement={'lrbDateAjaxNew':'INCOME','zcfzbDateAjaxNew':'BALANCE','xjllbDateAjaxNew':'CASH_FLOW'}[role]
                state['date_selections'][statement]=selected
                save()
            return response
        requests.Session.send=send
        with contextlib.redirect_stdout(sys.stderr):
            import akshare as ak
            if supplement:
                balance=ak.stock_balance_sheet_by_report_em(symbol=symbol)
                cash=ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)
                if not len(balance) or not len(cash):raise ValueError('FINANCIAL_SUPPLEMENT_EMPTY_STATEMENT')
                frame=balance
                state['statement_rows']={'BALANCE':len(balance),'CASH_FLOW':len(cash)}
            else:frame=ak.stock_profit_sheet_by_report_em(symbol=symbol)
        state['sdk_result']={'rows':len(frame),'columns':[str(c) for c in frame.columns]}
        state['status']='CAPTURED' if len(frame) else 'EMPTY_RESULT'
    except Exception as error:
        state['errors'].append(str(error)[:200] if isinstance(error,ValueError) else 'SDK_'+type(error).__name__)
    save()
    print(json.dumps({'status':state['status'],'calls':len(state['captures']),'errors':state['errors']},ensure_ascii=False))


if __name__=='__main__':main(json.loads(sys.stdin.read()))
