"""BaoStock 0.9.4 boundary: received wire authority precedes source field mapping."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zlib
from datetime import date, datetime
from decimal import Decimal
from roll.market.rules import SHANGHAI
from roll.market.source_facts import authority

HOST='vip-api.baostock.com'
PUBLIC_HOST='public-api.baostock.com'
PORT=10030
FIELDS='date,code,open,high,low,close,preclose,volume,amount,adjustflag,tradestatus,isST'
DOC='https://www.baostock.com/mainContent?file=stockKData.md'


def symbol(instrument):
    exchange,code=instrument.split(':')
    return {'SSE':'sh','SZSE':'sz'}[exchange]+'.'+code


def reflected(content):
    secrets=[v for k,v in os.environ.items() if v and any(t in k.upper() for t in ('API_KEY','TOKEN','SECRET','PASSWORD'))]
    texts=[content.decode('utf-8',errors='replace')]
    try:texts.append(json.dumps(json.loads(content),ensure_ascii=False))
    except (ValueError,UnicodeError):pass
    return any(secret in text for secret in secrets for text in texts)


def acquire(command,deadline,cancel_event,max_bytes,max_calls,worker=None):
    auth_mode=command.get('auth_mode','API_KEY')
    if auth_mode not in {'API_KEY','PUBLIC'}:raise ValueError('BAOSTOCK_AUTH_MODE_INVALID')
    credential=os.environ.get('BAOSTOCK_API_KEY') if auth_mode=='API_KEY' else None
    if auth_mode=='API_KEY' and not credential:raise ValueError('BAOSTOCK_CREDENTIAL_NOT_CONFIGURED')
    if max_calls<2:raise ValueError('BAOSTOCK_CALL_BUDGET_EXHAUSTED')
    worker=worker or Path(__file__).with_name('baostock_process.py')
    command={**command,'auth_mode':auth_mode,'max_bytes':max_bytes,'max_calls':max_calls,'timeout_seconds':max(.1,deadline-time.monotonic())}
    # The key is inherited by the isolated SDK child, never placed in argv/stdin/archive metadata.
    environment={k:v for k,v in os.environ.items() if not any(t in k.upper() for t in ('API_KEY','TOKEN','SECRET','PASSWORD'))}
    if credential:environment['BAOSTOCK_API_KEY']=credential
    with tempfile.TemporaryDirectory(prefix='roll-baostock-') as directory:
        output=Path(directory)/'response.json'
        with output.open('wb') as stream:
            process=subprocess.Popen([sys.executable,'-B',str(worker)],stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.DEVNULL,
                env=environment,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            try:
                process.stdin.write(json.dumps(command).encode());process.stdin.close()
                while process.poll() is None:
                    if (cancel_event and cancel_event.is_set()) or time.monotonic()>=deadline:
                        raise ValueError('BAOSTOCK_CANCELLED_OR_DEADLINE')
                    if output.stat().st_size>max_bytes*2+65536:raise ValueError('BAOSTOCK_OUTPUT_LIMIT')
                    time.sleep(.02)
                if process.returncode:raise ValueError('BAOSTOCK_PROCESS_FAILED')
                content=output.read_bytes()
                if len(content)>max_bytes*2+65536:raise ValueError('BAOSTOCK_OUTPUT_LIMIT')
            finally:
                if process.poll() is None:process.kill()
                process.wait(timeout=5)
    if reflected(content):raise ValueError('BAOSTOCK_SECRET_REFLECTED_RESPONSE_REJECTED')
    result=json.loads(content)
    if not isinstance(result,dict):raise ValueError('BAOSTOCK_RESULT_INVALID')
    code=str(result.get('error_code','UNKNOWN'))
    if code!='0':raise ValueError('BAOSTOCK_SOURCE_ERROR_'+(code if code.isdigit() else 'UNKNOWN'))
    wire=base64.b64decode(result.pop('wire_b64'),validate=True)
    for frame in wire.split(b'<![CDATA[]]>\n'):
        if not frame:continue
        head=frame[:21].split(b'\x01')
        if len(head)==3 and head[1] in {b'96',b'99',b'9B',b'9D'}:
            decoder=zlib.decompressobj()
            try:plain=decoder.decompress(frame[21:],max_bytes+1)
            except zlib.error:raise ValueError('BAOSTOCK_COMPRESSED_RESPONSE_INVALID') from None
            if len(plain)>max_bytes or decoder.unconsumed_tail:raise ValueError('BAOSTOCK_DECODED_BYTE_LIMIT')
            if reflected(plain):raise ValueError('BAOSTOCK_SECRET_REFLECTED_RESPONSE_REJECTED')
        if reflected(frame):raise ValueError('BAOSTOCK_SECRET_REFLECTED_RESPONSE_REJECTED')
    if len(wire)>max_bytes or result['received_bytes']>max_bytes:raise ValueError('BAOSTOCK_BYTE_BUDGET_EXHAUSTED')
    if not 1<=result['calls']<=max_calls:raise ValueError('BAOSTOCK_CALL_BUDGET_EXHAUSTED')
    return wire,result


def rows(payload):
    fields=payload['fields']
    if not isinstance(fields,list) or len(fields)!=len(set(fields)):raise ValueError('BAOSTOCK_FIELDS_INVALID')
    result=[]
    for row in payload['rows']:
        if len(row)!=len(fields):raise ValueError('BAOSTOCK_ROW_WIDTH_INVALID')
        result.append(dict(zip(fields,row)))
    return result


def coverage(archive,instrument,group,count,request):
    return {'instrument':instrument,'group':group,'returned_rows':count,'raw_hash':archive['sha256'],
        'request_start':request['start_date'],'request_end':request['end_date'],'full_history_verified':False,
        'truncation':'BOUNDED_QUERY_NOT_HISTORICAL_COMPLETENESS_OR_PIT_CERTIFICATION'}


def daily(payload,archive,instrument,request,decimal_value,include_daily=True,include_status=False):
    facts=[];seen=set()
    for row in rows(payload):
        if row['code']!=symbol(instrument):raise ValueError('BAOSTOCK_SOURCE_OBJECT_MISMATCH')
        if row['adjustflag']!='3':raise ValueError('BAOSTOCK_SOURCE_ADJUSTMENT_MISMATCH')
        day=date.fromisoformat(row['date']).isoformat()
        if not request['start_date']<=day<=request['end_date']:continue
        if day in seen:raise ValueError('BAOSTOCK_DUPLICATE_DAILY_DATE')
        seen.add(day)
        trade,st=row.get('tradestatus'),row.get('isST')
        if trade not in {'0','1'} or st not in {'0','1'}:raise ValueError('BAOSTOCK_STATUS_FLAG_INVALID')
        values={k:decimal_value(row.get(source),price=k in {'open','high','low','close'}) for k,source in
            [('open','open'),('high','high'),('low','low'),('close','close'),('volume_shares','volume'),('amount_yuan','amount')]}
        errors=['MISSING_OR_PLACEHOLDER_'+k.upper() for k,v in values.items() if v is None]
        if not errors:
            o,h,l,c=(Decimal(values[k]) for k in ['open','high','low','close'])
            if not l<=min(o,c)<=max(o,c)<=h:errors.append('INVALID_OHLC_RANGE')
            v,a=Decimal(values['volume_shares']),Decimal(values['amount_yuan'])
            if v>0 and (a==0 or not l-Decimal('.01')<=a/v<=h+Decimal('.01')):errors.append('UNIT_AMOUNT_OHLC_MISMATCH')
            if trade=='0' and (v!=0 or a!=0):errors.append('SUSPENDED_NONZERO_TURNOVER')
        complete='COMPLETE_REPORTED_HISTORICAL' if day<datetime.fromisoformat(archive['received_at']).astimezone(SHANGHAI).date().isoformat() else 'UNCONFIRMED_CURRENT_DAY'
        if include_daily:
            facts.append({**authority(archive,instrument,'DAILY'),**values,'trade_date':day,'time_precision':'DATE','adjustment':'RAW',
                'adjustment_version':None,'volume_unit':'SHARE','source_volume_unit':'SHARE','volume_reported':values['volume_shares'],
                'currency':'CNY','unit_basis':DOC,'preclose_reported':decimal_value(row.get('preclose'),True),
                'preclose_basis':'PROVIDER_REFERENCE_MAY_BE_EX_RIGHTS_NOT_PREVIOUS_RAW_CLOSE','completion_state':complete,
                'reported_tradestatus':trade,'reported_is_st':st,'errors':errors,'model_daily_input_allowed':not errors and trade=='1' and complete=='COMPLETE_REPORTED_HISTORICAL'})
        if include_status:
            facts.append({**authority(archive,instrument,'STATUS'),'trade_date':day,'time_precision':'DATE',
                'state':'SUSPENDED_REPORTED' if trade=='0' else 'RISK_WARNING_REPORTED' if st=='1' else 'NORMAL_REPORTED',
                'reported_tradestatus':trade,'reported_is_st':st,'suspension':'SUSPENDED_REPORTED' if trade=='0' else 'TRADING_REPORTED',
                'risk_warning':'ST_REPORTED' if st=='1' else 'NON_ST_REPORTED','listing_stage':'UNKNOWN','current_ex_rights':'UNKNOWN',
                'reported_limit_up':None,'reported_limit_down':None,'historical_complete_status_verified':False,'model_input_allowed':False,
                'limitations':['TRADING_AND_ST_FLAGS_NOT_COMPLETE_SPECIAL_STATUS_OR_PRICE_LIMIT_PROOF']})
    return facts,[coverage(archive,instrument,g,len(seen),request) for g,selected in [('DAILY',include_daily),('STATUS',include_status)] if selected]


def calendar(payload,archive,instrument,request):
    facts=[];seen=set()
    for row in rows(payload):
        day=date.fromisoformat(row['calendar_date']).isoformat()
        if not request['start_date']<=day<=request['end_date']:continue
        if day in seen:raise ValueError('BAOSTOCK_DUPLICATE_CALENDAR_DATE')
        seen.add(day)
        if row['is_trading_day'] not in {'0','1'}:raise ValueError('BAOSTOCK_CALENDAR_FLAG_INVALID')
        facts.append({**authority(archive,instrument,'CALENDAR'),'calendar_date':day,'trade_date':day,'time_precision':'DATE',
            'is_trading_day':row['is_trading_day']=='1','calendar_scope':'PROVIDER_A_SHARE_CALENDAR','official_exchange_calendar_verified':False})
    return facts,coverage(archive,instrument,'CALENDAR',len(facts),request)


def adjustments(payload,archive,instrument,request,decimal_value):
    facts=[];seen=set()
    for row in rows(payload):
        if row['code']!=symbol(instrument):raise ValueError('BAOSTOCK_SOURCE_OBJECT_MISMATCH')
        def day(field):return date.fromisoformat(row[field]).isoformat() if row.get(field) else None
        ex=day('dividOperateDate')
        if ex is None or not request['start_date']<=ex<=request['end_date']:continue
        key=tuple(sorted(row.items()))
        if key in seen:raise ValueError('BAOSTOCK_DUPLICATE_ACTION')
        seen.add(key)
        record,payment=day('dividRegistDate'),day('dividPayDate')
        if (record and record>ex) or (payment and payment<ex):raise ValueError('BAOSTOCK_ACTION_DATE_ORDER_INVALID')
        cash=decimal_value(row.get('dividCashPsBeforeTax'))
        facts.append({**authority(archive,instrument,'ADJUSTMENTS'),'ex_date':ex,'event_date':ex,'time_precision':'DATE',
            'disclosure_date':day('dividPlanDate'),'record_date':day('dividRegistDate'),'payment_date':day('dividPayDate'),
            'stock_listing_date':day('dividStockMarketDate'),'cash_per_share':cash,'dividend_yuan_per_share':cash,
            'cash_per_share_unit':'CNY_PRETAX_PER_SHARE','stock_dividend_ratio':decimal_value(row.get('dividStocksPs')),
            'reserve_to_stock_ratio':decimal_value(row.get('dividReserveToStockPs')),'allotment_ratio':None,'allotment_price':None,
            'action_state':'PROVIDER_REPORTED_EX_EVENT','historical_complete_actions_verified':False,
            'limitations':['DATE_ONLY_NOT_FIRST_DISCLOSURE_INSTANT','NO_COMPLETE_RIGHTS_ISSUE_OR_ACTION_HISTORY_PROOF','NOT_ACCOUNT_RECEIPT_OR_TAX_AUTHORITY']})
    return facts,coverage(archive,instrument,'ADJUSTMENTS',len(facts),request)
