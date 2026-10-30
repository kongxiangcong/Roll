"""Prefer Fuyao prices; never invent the execution fields it does not supply."""
import hashlib
import os
import time
from decimal import Decimal

import httpx

from roll.accounts.ledger import now
from roll.market import fuyao, source_policy, baostock


def source(service, run, symbol, cancel):
    deadline=time.monotonic()+30
    received_bytes=0
    fallback=lambda calls=5: service._baostock_source(run,symbol,cancel,deadline=deadline,max_calls=calls,max_bytes=max(1,2*1024*1024-received_bytes))
    if os.environ.get('ROLL_DATA_SOURCE_POLICY')!='OFFICIAL_FIRST':
        return fallback()
    instrument=('SSE:' if symbol.startswith('sh.') else 'SZSE:')+symbol.split('.')[1]
    stock=symbol==service.stock_symbol(run)
    capability='fuyao-daily' if stock else 'fuyao-index-daily'
    store=service.research.evidence if service.research else None
    attempts=[]
    used_calls=0
    try:
        key=os.environ.get('FUYAO_API_KEY')
        if not key:raise ValueError('FUYAO_CREDENTIAL_NOT_CONFIGURED')
        if store and (source_policy.health(store,'FUYAO') or source_policy.health(store,capability)):raise ValueError('FUYAO_COOLDOWN_ACTIVE')
        params=dict(thscode=fuyao.symbol(instrument),interval='1d',start=fuyao.millis(run['start_date']),end=fuyao.millis(run['as_of'],True))
        if stock:params['adjust']='none'
        used_calls=1
        with httpx.Client(transport=store.transport if store else None,follow_redirects=False) as client:
            with client.stream('GET',fuyao.BASE+('/api/a-share' if stock else '/api/a-share-index')+'/prices/historical',
                               params=params,headers={'X-api-key':key},timeout=10) as response:
                raw=bytearray()
                for chunk in response.iter_bytes(4096):
                    received_bytes+=len(chunk)
                    if len(raw)+len(chunk)>2*1024*1024 or time.monotonic()>=deadline or cancel.is_set():
                        raise ValueError('FUYAO_TECHNICAL_LIMIT')
                    raw.extend(chunk)
                if baostock.reflected(bytes(raw)):raise ValueError('FUYAO_SECRET_REFLECTED_RESPONSE_REJECTED')
                archive=dict(sha256=hashlib.sha256(raw).hexdigest(),received_at=now(),source_id='fuyao-daily',
                    source_url=str(response.url),evidence_kind=store.evidence_kind if store else 'REAL_ACQUISITION',http_status=response.status_code)
                if store:archive=store.archive(bytes(raw),'ASSISTANCE_DAILY_ORIGINAL',**{k:v for k,v in archive.items() if k!='sha256'})
                else:
                    directory=service.ledger.path.parent/'assistance-raw';directory.mkdir(exist_ok=True)
                    (directory/(archive['sha256']+'.bin')).write_bytes(raw)
                if response.status_code in {401,403,429} and store:source_policy.health(store,'FUYAO','HTTP_'+str(response.status_code))
                response.raise_for_status()
                try:data=fuyao.envelope(raw)
                except ValueError as error:
                    if store and str(error) in {'FUYAO_BUSINESS_ERROR_2001','FUYAO_BUSINESS_ERROR_2003','FUYAO_BUSINESS_ERROR_4001'}:
                        source_policy.health(store,capability if str(error)=='FUYAO_BUSINESS_ERROR_2003' else 'FUYAO',str(error))
                    raise
        from roll.market.evidence import decimal_value
        facts,_=fuyao.daily(raw,archive,instrument,
            dict(purpose='OBSERVATION' if stock else 'BACKGROUND',start_date=run['start_date'],end_date=run['as_of']), 'RAW',decimal_value)
        if not facts or any(f.get('errors') for f in facts):raise ValueError('FUYAO_DAILY_INVALID_OR_EMPTY')
        mapped=[dict(date=f['trade_date'],code=symbol,open=f['open'],high=f['high'],low=f['low'],close=f['close'],
            volume=f['volume_shares'],amount=f['amount_yuan'],adjustflag='3',preclose='',isST='UNKNOWN',tradestatus='UNKNOWN') for f in facts]
        result=dict(source_id=symbol,provider='FUYAO',received_at=archive['received_at'],raw_archive=archive,
                    sha256=archive['sha256'],rows=mapped,first_date=mapped[0]['date'],last_date=mapped[-1]['date'],
                    row_count=len(mapped),adjustment='RAW',price_unit='CNY' if stock else 'INDEX_POINT',volume_unit='SHARE',
                    historical_pit=False,request_start=run['start_date'],request_end=run['as_of'],source_attempts=attempts)
        if stock and not cancel.is_set() and time.monotonic()<deadline:
            try:
                supplement=fallback(4)
                by_day={r['date']:r for r in supplement['rows']}
                result['execution_supplement']={k:v for k,v in supplement.items() if k!='rows'}
                result['execution_supplement']['fields']=['preclose','isST','tradestatus']
                differences=[]
                for row in mapped:
                    previous=by_day.get(row['date'])
                    if previous and all(abs(Decimal(row[f])-Decimal(previous[f]))<=Decimal('.01') for f in ['open','high','low','close']):
                        row.update({k:previous[k] for k in ['preclose','isST','tradestatus']})
                    else:differences.append(row['date'])
                result['comparison']=dict(different_or_missing_days=differences,independence='UNPROVEN',fields=['open','high','low','close'])
            except Exception:
                attempts.append(dict(provider='BAOSTOCK',status='FAILED',reason='EXECUTION_FIELDS_UNAVAILABLE'))
        return result
    except (ValueError,KeyError,TypeError,OSError,httpx.HTTPError) as error:
        attempts.append(dict(provider='FUYAO',status='FAILED',reason=str(error) if isinstance(error,ValueError) and str(error).startswith('FUYAO_') else 'FUYAO_UNAVAILABLE'))
        if cancel.is_set() or time.monotonic()>=deadline or received_bytes>=2*1024*1024:
            raise ValueError('CANCELLED_OR_SOURCE_TECHNICAL_LIMIT') from None
        result=fallback(5-used_calls)
        result['source_attempts']=attempts
        return result
