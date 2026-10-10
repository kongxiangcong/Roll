"""Fuyao public REST mapping; current provider version is never historical PIT proof."""
from datetime import datetime, timezone
from decimal import Decimal
from roll.market.rules import SHANGHAI
from roll.market.source_facts import authority, source_json

BASE='https://fuyao.aicubes.cn'
PRICES_DOC=BASE+'/docs/api-reference/prices/'


def symbol(instrument):
    exchange,code=instrument.split(':')
    return code+'.'+{'SSE':'SH','SZSE':'SZ'}[exchange]


def millis(day, end=False):
    return int(datetime.fromisoformat(day+('T23:59:59.999' if end else 'T00:00:00')).replace(tzinfo=SHANGHAI).timestamp()*1000)


def timestamp(value):
    if value is None:return None
    return datetime.fromtimestamp(int(value)/1000,timezone.utc).isoformat()


def envelope(content):
    value=source_json(content)
    if type(value.get('code')) is not int:raise ValueError('FUYAO_BUSINESS_CODE_INVALID')
    if value['code']!=0:
        # Provider messages are untrusted and may contain reflected sensitive material.
        raise ValueError('FUYAO_BUSINESS_ERROR_'+str(value.get('code')))
    data=value.get('data')
    if not isinstance(data,dict) or not isinstance(data.get('item'),list):raise ValueError('FUYAO_DATA_SHAPE_INVALID')
    return data


def daily(content, archive, instrument, request, adjustment, decimal_value):
    data=envelope(content)
    index=request['purpose']=='BACKGROUND'
    if (data.get('thscode') is not None or not index) and data.get('thscode')!=symbol(instrument):raise ValueError('FUYAO_SOURCE_OBJECT_MISMATCH')
    if data.get('interval','1d')!='1d':raise ValueError('FUYAO_SOURCE_INTERVAL_MISMATCH')
    expected='none' if adjustment=='RAW' else 'forward'
    if not index and data.get('adjust')!=expected:raise ValueError('FUYAO_SOURCE_ADJUSTMENT_MISMATCH')
    if index and data.get('adjust') is not None:raise ValueError('FUYAO_INDEX_ADJUSTMENT_INVALID')
    facts=[];seen=set()
    for row in data['item']:
        day=datetime.fromtimestamp(int(row['date_ms'])/1000,SHANGHAI).date().isoformat()
        if not request['start_date']<=day<=request['end_date']:continue
        if day in seen:raise ValueError('FUYAO_DUPLICATE_DAILY_DATE')
        seen.add(day)
        values={name:decimal_value(row.get(source),price=name in {'open','close','high','low'}) for name,source in
            [('open','open_price'),('close','close_price'),('high','high_price'),('low','low_price'),('volume_shares','volume'),('amount_yuan','turnover')]}
        errors=['MISSING_OR_PLACEHOLDER_'+k.upper() for k,v in values.items() if v is None]
        if not errors:
            o,c,h,l=(Decimal(values[k]) for k in ['open','close','high','low'])
            v,a=Decimal(values['volume_shares']),Decimal(values['amount_yuan'])
            if not l<=min(o,c)<=max(o,c)<=h:errors.append('INVALID_OHLC_RANGE')
            if v>0 and a==0:errors.append('AMOUNT_PLACEHOLDER_OR_INCONSISTENT')
            if not index and adjustment=='RAW' and v>0 and a>0 and not l-Decimal('.01')<=a/v<=h+Decimal('.01'):errors.append('UNIT_AMOUNT_OHLC_MISMATCH')
        completion='COMPLETE_REPORTED_HISTORICAL' if day<datetime.fromisoformat(archive['received_at']).astimezone(SHANGHAI).date().isoformat() else 'UNCONFIRMED_CURRENT_DAY'
        facts.append({**authority(archive,instrument,'DAILY'),**values,'trade_date':day,'time_precision':'DATE',
            'adjustment':adjustment,'adjustment_version':archive['sha256'] if adjustment!='RAW' else None,
            'volume_unit':'SHARE','source_volume_unit':'SHARE','volume_reported':values['volume_shares'],'unit_basis':PRICES_DOC,
            'currency':'CNY','completion_state':completion,'errors':errors,'limitations':['INDEX_POINTS_NOT_SHARE_PRICE'] if index else [],
            'zero_volume_state':'ZERO_REPORTED' if values['volume_shares']=='0' else 'NONZERO_OR_MISSING',
            'source_series_ready_at':timestamp(data.get('timestamp')),'model_daily_input_allowed':not index and not errors and completion=='COMPLETE_REPORTED_HISTORICAL'})
    facts.sort(key=lambda f:f['trade_date'])
    return facts,{'instrument':instrument,'group':'DAILY','returned_rows':len(facts),'provider_returned_rows':len(data['item']),
        'first_date':facts[0]['trade_date'] if facts else None,'last_date':facts[-1]['trade_date'] if facts else None,
        'request_start':request['start_date'],'request_end':request['end_date'],'adjustment':adjustment,'raw_hash':archive['sha256'],
        'full_history_verified':False,'truncation':'REQUEST_BOUNDED; NO_SOURCE_TOTAL_OR_COMPLETENESS_PROOF',
        'status':'ACQUIRED' if facts else 'NO_ROWS_RETURNED'}


def adjustments(content,archive,instrument,request,decimal_value):
    data=envelope(content)
    if data.get('thscode')!=symbol(instrument):raise ValueError('FUYAO_SOURCE_OBJECT_MISMATCH')
    facts=[]
    for row in data['item']:
        if row.get('ticker')!=instrument.split(':')[1]:raise ValueError('FUYAO_ACTION_OBJECT_MISMATCH')
        day=datetime.fromtimestamp(int(row['ex_date_ms'])/1000,SHANGHAI).date().isoformat()
        if not request['start_date']<=day<=request['end_date']:continue
        cash=decimal_value(row.get('dividend_per_share'));bonus=decimal_value(row.get('per_share_bonus'))
        facts.append({**authority(archive,instrument,'ADJUSTMENTS'),'ex_date':day,'event_date':day,
            'time_precision':'DATE','disclosure_date':None,'record_date':None,'cash_per_share':cash,
            'dividend_yuan_per_share':cash,'cash_per_share_unit':'CNY_PRETAX_PER_SHARE','stock_dividend_ratio':bonus,
            'allotment_ratio':decimal_value(row.get('allotment_ratio')),'allotment_price':decimal_value(row.get('allotment_price')),
            'action_state':'PROVIDER_REPORTED_EX_EVENT','historical_complete_actions_verified':False,
            'limitations':['NO_DISCLOSURE_TIMESTAMP_OR_RECORD_DATE','NO_HISTORY_COMPLETENESS_OR_PIT_CERTIFICATION',
                'PUBLIC_EVENT_FIELDS_DO_NOT_PROVE_ALL_RIGHTS_ISSUES'],'formal_judgment':'DISABLED'})
    return facts,{'instrument':instrument,'group':'ADJUSTMENTS','returned_rows':len(facts),
        'provider_returned_rows':len(data['item']),'raw_hash':archive['sha256'],'full_history_verified':False,
        'truncation':'REQUEST_BOUNDED; NO_SOURCE_TOTAL_OR_COMPLETENESS_PROOF'}


def quote(content,archive,instrument,decimal_value):
    data=envelope(content)
    rows=data['item']
    if len(rows)!=1 or rows[0].get('thscode')!=symbol(instrument):raise ValueError('FUYAO_SOURCE_OBJECT_MISMATCH')
    row=rows[0]
    return {**authority(archive,instrument,'QUOTE'),'last':decimal_value(row.get('last_price'),True),
        'volume_shares':decimal_value(row.get('volume')),'volume_reported':decimal_value(row.get('volume')),
        'amount_yuan':decimal_value(row.get('turnover')),'currency':'CNY','volume_unit':'SHARE','source_volume_unit':'SHARE','unit_basis':PRICES_DOC,
        'adjustment':'RAW','upstream_at':None,'trade_date':None,'time_precision':'UNKNOWN','age_seconds':None,
        'source_snapshot_ready_at':timestamp(data.get('timestamp')),'source_snapshot_time_basis':'LATEST_VALID_UPSTREAM_TIME_IN_RESPONSE_NOT_PER_INSTRUMENT',
        'reported_limit_up':None,'reported_limit_down':None,'current_monitoring_input_allowed':False,
        'limitations':['QUOTE_PER_INSTRUMENT_TIME_UNKNOWN'],'formal_judgment':'DISABLED'}
