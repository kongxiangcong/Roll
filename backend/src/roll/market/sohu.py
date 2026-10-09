"""Supplier historical table mapping, RAW only; receipt is never historical PIT proof."""
import json
import re
from datetime import date,datetime
from decimal import Decimal
from roll.market.rules import SHANGHAI
from roll.market.source_facts import authority

BASE='https://q.stock.sohu.com/hisHq'
UNIT_BASIS={'url':'https://q.stock.sohu.com/cn/600362/lshq.shtml',
    'page_sha256':'2bb1545bebd5b5fd6b42ca188c01f102288e4d548c083ab9120535c4335202f4',
    'parser_url':'https://static.k.sohu.com/static/finance/pc/qstock/v0.0.10/js/main/hq_sec-1.4.min.js?202607090945',
    'parser_sha256':'8c57fcfd2fda59415f77a0bdfb683c68c3f568fb33eb6392bddaaf4b004ead35',
    'mapping':'hq date/open/close/change/change_percent/low/high/volume HAND/amount TEN_THOUSAND_CNY/turnover_percent; optional after-hours HAND',
    'scope':'Confirmed SSE MAIN ordinary STOCK only; other scopes volume UNKNOWN'}


def daily(content,archive,instrument,request,decimal_value):
    payload=json.loads(content.decode('gbk'),parse_float=Decimal)
    if not isinstance(payload,list) or len(payload)!=1 or not isinstance(payload[0],dict):raise ValueError('SOHU_ENVELOPE_INVALID')
    source=payload[0]
    if type(source.get('status')) is not int or source['status']!=0:raise ValueError('SOHU_BUSINESS_STATUS_ERROR')
    if source.get('code')!='cn_'+instrument.split(':')[1]:raise ValueError('SOHU_SOURCE_OBJECT_MISMATCH')
    rows=source.get('hq')
    if not isinstance(rows,list):raise ValueError('SOHU_DAILY_ROWS_INVALID')
    identity=request.get('identity_context',{}).get(instrument,{})
    unit_verified=identity.get('exchange')=='SSE' and identity.get('board')=='MAIN' and identity.get('instrument_type')=='STOCK'
    facts=[];seen=set()
    for row in rows:
        if not isinstance(row,list) or len(row) not in {10,11} or any(not isinstance(v,str) for v in row):raise ValueError('SOHU_DAILY_ROW_INVALID')
        # The supplier reports bounded decimal text, never expressions or commands.
        for column in [1,2,5,6,7,8]:
            value=row[column]
            if value not in {'','-','--','null'} and (len(value)>64 or re.fullmatch(r'-?\d+(?:\.\d+)?',value) is None):raise ValueError('SOHU_NUMERIC_FIELD_INVALID')
        day=date.fromisoformat(row[0]).isoformat()
        if day!=row[0] or not request['start_date']<=day<=request['end_date']:raise ValueError('SOHU_DATE_OUTSIDE_REQUEST')
        if day in seen:raise ValueError('SOHU_DUPLICATE_DAILY_DATE')
        seen.add(day)
        values={name:decimal_value(row[column],price=True) for name,column in [('open',1),('close',2),('low',5),('high',6)]}
        volume=decimal_value(row[7]);amount_reported=decimal_value(row[8])
        shares=format(Decimal(volume)*100,'f') if unit_verified and volume is not None else None
        amount=format(Decimal(amount_reported)*10000,'f') if amount_reported is not None else None
        errors=['MISSING_OR_PLACEHOLDER_'+k.upper() for k,v in {**values,'volume_reported':volume,'amount_yuan':amount}.items() if v is None]
        if not errors:
            o,c,l,h=(Decimal(values[k]) for k in ['open','close','low','high'])
            if not l<=min(o,c)<=max(o,c)<=h:errors.append('INVALID_OHLC_RANGE')
            if Decimal(volume)>0 and Decimal(amount)==0:errors.append('AMOUNT_PLACEHOLDER_OR_INCONSISTENT')
            # Amount is rounded to 0.01万元; preserve that 100 CNY supplier precision.
            if shares is not None and Decimal(shares)>0 and Decimal(amount)>0:
                tolerance=Decimal('100')/Decimal(shares)+Decimal('.01')
                if not l-tolerance<=Decimal(amount)/Decimal(shares)<=h+tolerance:errors.append('UNIT_AMOUNT_OHLC_MISMATCH')
        completion='COMPLETE_REPORTED_HISTORICAL' if day<datetime.fromisoformat(archive['received_at']).astimezone(SHANGHAI).date().isoformat() else 'UNCONFIRMED_CURRENT_DAY'
        limitations=[] if unit_verified else ['VOLUME_UNIT_UNVERIFIED_FOR_THIS_SCOPE']
        facts.append({**authority(archive,instrument,'DAILY'),**values,'trade_date':day,'time_precision':'DATE',
            'adjustment':'RAW','adjustment_version':None,'currency':'CNY','volume_reported':volume,'volume_shares':shares,
            'volume_unit':'SHARE' if unit_verified else 'UNKNOWN','source_volume_unit':'HAND',
            'amount_reported':amount_reported,'source_amount_unit':'TEN_THOUSAND_CNY','amount_yuan':amount,
            'amount_precision_yuan':'100','unit_basis':UNIT_BASIS,'completion_state':completion,'errors':errors,'limitations':limitations,
            'quality':'INVALID' if errors else 'BASIC_CHECKED_SINGLE_SOURCE',
            'volume_state':'MISSING' if volume is None else 'ZERO_REPORTED' if Decimal(volume)==0 else 'REPORTED',
            'model_daily_input_allowed':not errors and not limitations and completion=='COMPLETE_REPORTED_HISTORICAL'})
    facts.sort(key=lambda f:f['trade_date'])
    return facts,{'instrument':instrument,'group':'DAILY','source_id':archive['source_id'],'returned_rows':len(facts),
        'provider_returned_rows':len(rows),'first_date':facts[0]['trade_date'] if facts else None,'last_date':facts[-1]['trade_date'] if facts else None,
        'request_start':request['start_date'],'request_end':request['end_date'],'adjustment':'RAW','raw_hash':archive['sha256'],
        'full_history_verified':False,'truncation':'SINGLE_BOUNDED_QUERY; NO_TOTAL_OR_CALENDAR_COMPLETENESS_PROOF',
        'status':'ACQUIRED' if facts else 'NO_ROWS_RETURNED'}
