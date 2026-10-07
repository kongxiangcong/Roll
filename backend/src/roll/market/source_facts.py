"""Empirical, pinned provider mappings; source dates are never invented instants."""
import json
import re
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from pypdf import PdfReader
from roll.market.rules import SHANGHAI

REGISTRY=[
    {'id':'eastmoney-daily','groups':['DAILY'],'host':'push2his.eastmoney.com','depth':'explicit bounded day interval; fqt=0/1 separate versions','unit_scope':'HAND conversion currently evidenced only confirmed SSE MAIN ordinary STOCK; remaining scopes UNKNOWN'},
    {'id':'tencent-quote','groups':['QUOTE','STATUS'],'host':'qt.gtimg.cn','depth':'last reported quote; upstream timestamp can be stale','unit_scope':'reported volume retained; packed amount field35 yuan; no volume conversion outside evidenced scope'},
    {'id':'tencent-index-daily','groups':['DAILY'],'host':'web.ifzq.gtimg.cn','depth':'fixed background indices only; bounded maximum 800 bars; historical amount generally absent','unit_scope':'index aggregate volume unit UNKNOWN'},
    {'id':'tencent-daily','groups':['DAILY'],'host':'web.ifzq.gtimg.cn','depth':'explicit request selection; maximum 800 bars; raw/day and qfqday strictly distinct; historical amount generally absent','unit_scope':'currently verified only confirmed SSE MAIN STOCK; other scopes UNKNOWN'},
    {'id':'eastmoney-actions','groups':['ADJUSTMENTS'],'host':'datacenter-web.eastmoney.com','depth':'latest 5 report-period records, one page; announcement does not prove account receipt','unit_scope':'per-ten-share dividend source field; no cash-ledger authority'},
    {'id':'eastmoney-performance','groups':['PERFORMANCE'],'host':'datacenter-web.eastmoney.com','depth':'latest 3 report-period records, one page; original report separately archived','unit_scope':'reported yuan and yuan/share; exact numeric JSON token Decimal'},
    {'id':'eastmoney-announcements','groups':['ANNOUNCEMENTS','PERFORMANCE','MAJOR_EVENTS','ADJUSTMENTS'],'host':'np-anotice-stock.eastmoney.com','depth':'latest 30 metadata records, one page; at most one original per requested group','unit_scope':'supplier column code and explicit major-event/distribution title; no guessed company status'},
    {'id':'eastmoney-original','groups':['ANNOUNCEMENTS','PERFORMANCE','MAJOR_EVENTS','ADJUSTMENTS'],'host':'np-cnotice-stock.eastmoney.com','depth':'client_source=web; article JSON and linked PDF; bounded first 3 pages of text','unit_scope':'disclosure date separate from provider display/index time'},
]
for entry in REGISTRY:
    entry.update(adapter_version='07-market-v1',authentication='PUBLIC_NO_CREDENTIAL',
        permission_basis='Unauthenticated public request actually tested; no commercial redistribution license asserted',
        historical_revision_proof='NOT_AVAILABLE',retries=0,source_selection='PREDECLARED_PRIMARY_NOT_AUTOMATIC_FALLBACK')


def source_json(content):
    return json.loads(content,parse_float=Decimal)


def source_date(value):
    if value is None or value=='':return None
    # Supplier date fields serialize synthetic midnight; retain only declared date precision.
    return datetime.strptime(str(value)[:10],'%Y-%m-%d').date().isoformat()


def supplier_time(value):
    if not value:return None
    text=str(value)
    match=re.fullmatch(r'(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})(?::(\d{3}))?',text)
    if not match:return None
    return datetime.fromisoformat(match[1]+'T'+match[2]+('.'+match[3] if match[3] else '')).replace(tzinfo=SHANGHAI).isoformat()


def authority(archive,instrument,group):
    return {'instrument':instrument,'group':group,'source_id':archive['source_id'],'source_url':archive['source_url'],
        'raw_hash':archive['sha256'],'revision_id':archive['sha256'],'received_at':archive['received_at'],
        'fetched_at':archive['received_at'],'available_at':archive['received_at'],
        'available_basis':'FIRST_ACTUAL_RECEIPT_IN_THIS_RUNTIME','published_at':None,
        'historical_limitations':['PROVIDER_CURRENT_REVISION_NOT_PROVEN_POINT_IN_TIME'],
        'evidence_kind':archive['evidence_kind'],'quality':'BASIC_CHECKED_SINGLE_SOURCE'}


def quote(content,archive,instrument,decimal_value):
    if content.lstrip().startswith(b'{'):
        # Explicit source-contract method cases are accepted only through the injected
        # test transport. A live endpoint JSON response cannot establish these states.
        sample=source_json(content)
        if archive['evidence_kind']!='METHOD_CASE' or sample.get('instrument')!=instrument or sample.get('method_case_status') not in {'NORMAL','SUSPENDED','RISK_WARNING','EX_RIGHTS','UNKNOWN'}:
            raise ValueError('LIVE_QUOTE_CANNOT_USE_METHOD_STATUS_CASE')
        upstream=datetime.fromisoformat(sample['upstream_at'])
        if upstream.tzinfo is None:raise ValueError('METHOD_STATUS_TIME_REQUIRES_ZONE')
        return {**authority(archive,instrument,'QUOTE'),'upstream_at':upstream.isoformat(),'time_precision':'SECOND',
            'trade_date':upstream.astimezone(SHANGHAI).date().isoformat(),'method_status':sample['method_case_status'],
            'status_basis':sample['basis'],'last':decimal_value(sample.get('last'),True),'volume_reported':decimal_value(sample.get('volume_reported')),
            'amount_yuan':decimal_value(sample.get('amount_yuan')),'reported_limit_up':decimal_value(sample.get('reported_limit_up'),True),
            'reported_limit_down':decimal_value(sample.get('reported_limit_down'),True),'volume_unit':'UNKNOWN',
            'age_seconds':max(0,(datetime.fromisoformat(archive['received_at'])-upstream).total_seconds()),'formal_judgment':'DISABLED'}
    text=content.decode('gbk')
    fields=text.split('="',1)[1].rsplit('"',1)[0].split('~')
    if len(fields)<49 or fields[2]!=instrument.split(':')[1]:raise ValueError('QUOTE_OBJECT_OR_FIELDS_MISMATCH')
    upstream=datetime.strptime(fields[30],'%Y%m%d%H%M%S').replace(tzinfo=SHANGHAI)
    packed=fields[35].split('/')
    return {**authority(archive,instrument,'QUOTE'),'upstream_at':upstream.isoformat(),'time_precision':'SECOND',
        'trade_date':upstream.date().isoformat(),'last':decimal_value(fields[3],True),'previous_close':decimal_value(fields[4],True),
        'open':decimal_value(fields[5],True),'high':decimal_value(fields[33],True),'low':decimal_value(fields[34],True),
        'volume_reported':decimal_value(fields[6]),'volume_unit':'UNKNOWN','volume_shares':None,
        'amount_yuan':decimal_value(packed[2]) if len(packed)==3 else None,
        'reported_limit_up':decimal_value(fields[47],True),'reported_limit_down':decimal_value(fields[48],True),
        'state':'REPORTED_QUOTE','current_status':'UNKNOWN','limitations':['QUOTE_DOES_NOT_CONFIRM_SUSPENSION_OR_RISK_WARNING'],
        'age_seconds':max(0,(datetime.fromisoformat(archive['received_at'])-upstream).total_seconds()),'formal_judgment':'DISABLED'}


def index_daily(content,archive,instrument,request,symbol,decimal_value,adjustment='RAW'):
    raw=source_json(content)
    if raw.get('code')!=0 or not raw.get('data',{}).get(symbol):raise ValueError('PROVIDER_BUSINESS_ERROR_OR_EMPTY')
    data=raw['data'][symbol];facts=[];qt=data.get('qt',{}).get(symbol,[])
    key='day' if adjustment=='RAW' else 'qfqday'
    if key not in data:raise ValueError('REQUESTED_RAW_OR_ADJUSTED_SERIES_MISSING_NO_SILENT_SWITCH')
    identity=request.get('identity_context',{}).get(instrument,{})
    unit_verified=identity.get('exchange')=='SSE' and identity.get('board')=='MAIN' and identity.get('instrument_type')=='STOCK'
    for row in data[key]:
        if len(row)<6:raise ValueError('MISSING_INDEX_DAILY_FIELDS')
        day=source_date(row[0])
        if not request['start_date']<=day<=request['end_date']:continue
        values={n:decimal_value(v,True) for n,v in zip(['open','close','high','low'],row[1:5])}
        volume=decimal_value(row[5]);amount=None
        if adjustment=='RAW' and len(qt)>35 and qt[30][:8]==day.replace('-',''):
            # Quote amount can fill only the same session with matching OHLC and volume.
            same=all(decimal_value(qt[i],True) is not None and values[n] is not None and Decimal(decimal_value(qt[i],True))==Decimal(values[n])
                for i,n in [(3,'close'),(5,'open'),(33,'high'),(34,'low')])
            packed=qt[35].split('/')
            if same and volume is not None and decimal_value(qt[6]) is not None and Decimal(decimal_value(qt[6]))==Decimal(volume) and len(packed)==3:amount=decimal_value(packed[2])
        errors=['MISSING_OR_PLACEHOLDER_'+n.upper() for n,v in values.items() if v is None]
        if not errors:
            o,c,h,l=(Decimal(values[n]) for n in ['open','close','high','low'])
            if not l<=min(o,c)<=max(o,c)<=h:errors.append('INVALID_OHLC_RANGE')
            if unit_verified and volume is not None and Decimal(volume)>0 and amount is not None:
                vwap=Decimal(amount)/(Decimal(volume)*100)
                if not l-Decimal('.01')<=vwap<=h+Decimal('.01'):errors.append('UNIT_AMOUNT_OHLC_MISMATCH')
        completion='COMPLETE_REPORTED_HISTORICAL' if day<datetime.fromisoformat(archive['received_at']).astimezone(SHANGHAI).date().isoformat() else 'UNCONFIRMED_CURRENT_DAY'
        limitations=([] if unit_verified else ['INDEX_AGGREGATE_VOLUME_UNIT_UNVERIFIED' if request['purpose']=='BACKGROUND' else 'VOLUME_UNIT_UNVERIFIED_FOR_THIS_SCOPE'])+([] if amount is not None else ['HISTORICAL_AMOUNT_NOT_RETURNED'])
        facts.append({**authority(archive,instrument,'DAILY'),**values,'trade_date':day,'time_precision':'DATE','volume_reported':volume,
            'volume_shares':format(Decimal(volume)*100,'f') if unit_verified and volume is not None else None,
            'volume_unit':'SHARE' if unit_verified else 'UNKNOWN','source_volume_unit':'HAND' if unit_verified else 'UNKNOWN','amount_yuan':amount,
            'conversion_basis':'SSE MAIN STOCK Tencent reported hands cross-check with same-session quote packed amount and raw OHLC' if unit_verified else None,
            'amount_basis':'MATCHING_SAME_SESSION_EMBEDDED_QUOTE_FIELD35' if amount is not None else None,
            'adjustment':adjustment,'adjustment_version':archive['sha256'] if adjustment!='RAW' else None,'completion_state':completion,'errors':errors,
            'model_daily_input_allowed':not errors and not limitations and completion.startswith('COMPLETE'),'limitations':limitations,
            'volume_state':'MISSING' if volume is None else 'ZERO_REPORTED' if Decimal(volume)==0 else 'REPORTED'})
    return facts,{'instrument':instrument,'group':'DAILY','source_id':archive['source_id'],'returned_rows':len(facts),
        'first_date':facts[0]['trade_date'] if facts else None,'last_date':facts[-1]['trade_date'] if facts else None,
        'full_history_verified':False,'truncation':'REQUEST_BOUNDED_MAXIMUM_800_ROWS; NO_HISTORICAL_AMOUNT',
        'adjustment':adjustment,'raw_hash':archive['sha256'],'volume_unit_verified':unit_verified,
        'model_daily_input_allowed':False,'adjustment_fallback_allowed':False}


def financial(content,archive,instrument,group,request,decimal_value):
    raw=source_json(content)
    if raw.get('code')!=0 or raw.get('success') is not True or not raw.get('result'):raise ValueError('PROVIDER_BUSINESS_ERROR_OR_EMPTY')
    result=raw['result'];facts=[]
    for row in result.get('data',[]):
        if row.get('SECURITY_CODE')!=instrument.split(':')[1]:raise ValueError('SOURCE_OBJECT_MISMATCH')
        disclosure=source_date(row.get('NOTICE_DATE') or row.get('PUBLISH_DATE') or row.get('PLAN_NOTICE_DATE'))
        if not disclosure or not request['start_date']<=disclosure<=request['end_date']:continue
        fact={**authority(archive,instrument,group),'time_precision':'DATE','disclosure_date':disclosure,
            'report_period':source_date(row.get('REPORTDATE') or row.get('REPORT_DATE')),
            'provider_indexed_at':supplier_time(row.get('EITIME')),'intraday_disclosure_eligibility':'UNKNOWN_DATE_ONLY',
            'original_source_fields':{k:str(v) if isinstance(v,Decimal) else v for k,v in row.items()}}
        if group=='PERFORMANCE':
            def signed_value(value):
                if value is None:return None
                number=Decimal(str(value))
                return format(number,'f') if number.is_finite() else None
            fact.update(total_operating_income_yuan=decimal_value(row.get('TOTAL_OPERATE_INCOME')),net_profit_yuan=decimal_value(row.get('PARENT_NETPROFIT')),
                eps_yuan_per_share=signed_value(row.get('EPS')),financial_unit_basis='RPT_LICO_FN_CPD source field yuan/yuan per share; no annualization')
            fact['net_profit_yuan']=signed_value(row.get('PARENT_NETPROFIT'))
        else:
            per_ten=decimal_value(row.get('PRETAX_BONUS_RMB'))
            stage=row.get('ASSIGN_PROGRESS') or row.get('PLAN_PROGRESS')
            fact.update(dividend_yuan_per_ten_shares=per_ten,dividend_yuan_per_share=format(Decimal(per_ten)/10,'f') if per_ten is not None else None,
                ex_date=source_date(row.get('EX_DIVIDEND_DATE')),record_date=source_date(row.get('EQUITY_RECORD_DATE')),
                plan_stage=stage,action_state='IMPLEMENTATION_ANNOUNCED' if stage in {'实施分配','实施方案'} else 'PRE_DISCLOSURE' if stage=='预披露' else 'PLAN_OR_STAGE_UNKNOWN',
                account_receipt_state='PENDING_RECONCILIATION' if stage in {'实施分配','实施方案'} else 'NOT_APPLICABLE_UNCONFIRMED_PLAN',
                provider_publish_date=source_date(row.get('PUBLISH_DATE')),source_notice_date=source_date(row.get('NOTICE_DATE')),
                conversion_basis='PRETAX_BONUS_RMB reported per ten shares; original distribution announcement separately checked')
        facts.append(fact)
    return facts,{'instrument':instrument,'group':group,'returned_rows':len(facts),'source_page_rows':len(result.get('data',[])),
        'source_total_rows':result.get('count'),'source_pages':result.get('pages'),'full_history_verified':False,
        'truncation':'LATEST_SINGLE_PAGE; DISCLOSURE_DATE_FILTERED; NOT_COMPLETE_HISTORY','raw_hash':archive['sha256']}


def announcement_candidates(content,instrument,request):
    raw=source_json(content)
    if raw.get('success')!=1 or not raw.get('data'):raise ValueError('PROVIDER_BUSINESS_ERROR_OR_EMPTY')
    selected={};eligible=[]
    for row in raw['data'].get('list',[]):
        if not any(c.get('stock_code')==instrument.split(':')[1] for c in row.get('codes',[])):raise ValueError('ANNOUNCEMENT_OBJECT_MISMATCH')
        disclosure=source_date(row.get('notice_date'))
        if not disclosure or not request['start_date']<=disclosure<=request['end_date']:continue
        eligible.append(row)
        columns=[c.get('column_code','') for c in row.get('columns',[])]
        if 'ANNOUNCEMENTS' in request['groups']:selected.setdefault('ANNOUNCEMENTS',row)
        if 'PERFORMANCE' in request['groups'] and any(c.endswith('001002001') or c in {'001001001002001','001001001001001'} for c in columns):selected.setdefault('PERFORMANCE',row)
        if 'MAJOR_EVENTS' in request['groups'] and '重大事项' in row.get('title',''):selected.setdefault('MAJOR_EVENTS',row)
        if 'ADJUSTMENTS' in request['groups'] and '权益分派实施公告' in row.get('title',''):selected.setdefault('ADJUSTMENTS',row)
    return selected,{'returned_metadata_rows':len(raw['data'].get('list',[])),'eligible_metadata_rows':len(eligible),
        'source_total_rows':raw['data'].get('total_hits'),'full_history_verified':False,'truncation':'LATEST_30_METADATA; ONE_ORIGINAL_PER_REQUESTED_GROUP'}


def original(content,archive,instrument,group,row,document,document_content):
    raw=source_json(content)
    data=raw.get('data')
    if raw.get('success')!=1 or not data or data.get('art_code')!=row['art_code']:raise ValueError('ORIGINAL_DOCUMENT_MISMATCH')
    if not document_content.startswith(b'%PDF'):raise ValueError('ORIGINAL_DOCUMENT_NOT_PDF')
    reader=PdfReader(BytesIO(document_content));text='\n'.join((p.extract_text() or '') for p in reader.pages[:3])
    return {**authority(archive,instrument,group),'art_code':row['art_code'],'title':row.get('title'),
        'disclosure_date':source_date(row.get('notice_date')),'time_precision':'DATE',
        'provider_display_at':supplier_time(row.get('display_time')),'provider_indexed_at':supplier_time(row.get('eiTime')),
        'provider_time_basis':'SUPPLIER_DISPLAY_AND_INDEX_CLOCK; NOT_PROOF_OF_EXCHANGE_PUBLICATION',
        'document_hash':document['sha256'],'document_url':document['source_url'],'document_pages':len(reader.pages),
        'content_excerpt':(data.get('notice_content') or '')[:1200],'pdf_excerpt':text[:1200],
        'extraction_scope':'FIRST_3_PAGES_AND_1200_CHARS; FULL_ORIGINAL_ARCHIVED','category_basis':row.get('columns',[]),
        'intraday_disclosure_eligibility':'UNKNOWN_DATE_ONLY','formal_judgment':'DISABLED'}
