"""One pinned SSE date-query schema; returned schedules never certify normality."""
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs,urlparse

SOURCE='sse-suspension-date'
REFERENCE=Path(__file__).parent/'reference/sse-history'
JS_SHA='32fc98ea41e599f457609247ba68defb82e6d855aa2551da6923dbf7e44153a7'
SQL='COMMON_SSE_XXPL_JYTS_TFPXX_L'


def schema():
    mapping=(REFERENCE/'sources.json').read_bytes()
    sources={s['role']:s for s in json.loads(mapping)['sources']}
    source=sources['suspension_query_js'];body=(REFERENCE/source['path']).read_bytes()
    if source['sha256']!=JS_SHA or len(body)!=source['bytes'] or hashlib.sha256(body).hexdigest()!=JS_SHA:
        raise ValueError('SSE_SUSPENSION_QUERY_JS_ORIGINAL_CORRUPT')
    js=body.decode('utf-8').split('var suspension_stock',1)[0]
    if not all(term in js for term in [SQL,'SEARCH_DATE','pageHelp.pageSize','pageHelp.pageNo','pageHelp.beginPage',
        'pageHelp.endPage','pageHelp.cacheSize','PRODUCT_CODE','STOP_DATE','STOP_TIME','STOP_REASON']):
        raise ValueError('SSE_SUSPENSION_QUERY_SCHEMA_UNPROVEN')
    original=urlparse(sources['suspension']['url']);params={k:v[0] for k,v in parse_qs(original.query).items()}
    if original.hostname!='query.sse.com.cn' or original.path!='/sseQuery/commonQuery.do' or params.get('sqlId')!=SQL:
        raise ValueError('SSE_SUSPENSION_PRIMARY_QUERY_UNPROVEN')
    return {'url':original._replace(query='').geturl(),'parameters':params,'js_source':source,
        'js_bytes':body,'mapping_bytes':mapping,'mapping_hash':hashlib.sha256(mapping).hexdigest()}


def parameters(contract,day,page_no):
    return {**contract['parameters'],'SEARCH_DATE':date.fromisoformat(day).isoformat(),
        'pageHelp.pageNo':str(page_no),'pageHelp.beginPage':str(page_no),'pageHelp.endPage':str(page_no)}


def reported_metadata(content):
    """Literal response metadata survives a refused interpretation; no coverage inference."""
    try:value=json.loads(content)
    except (ValueError,UnicodeDecodeError):return {'json_object_reported':False}
    if not isinstance(value,dict):return {'json_object_reported':False}
    page=value.get('pageHelp');page=page if isinstance(page,dict) else {}
    rows=value.get('result')
    return {'json_object_reported':True,'sql_id_reported':value.get('sqlId'),
        'declared_total':page.get('total'),'page_no':page.get('pageNo'),'page_count':page.get('pageCount'),
        'page_size':page.get('pageSize'),'begin_page':page.get('beginPage'),'end_page':page.get('endPage'),
        'response_date_reported':value.get('queryDate'),'page_search_date_reported':page.get('searchDate'),
        'returned_count':len(rows) if isinstance(rows,list) else None,
        'action_errors_reported':value.get('actionErrors'),'field_errors_reported':value.get('fieldErrors')}


def parse_pages(pages,instrument,query_day,known_at):
    queried=date.fromisoformat(query_day);selected=[];audits=[];gaps=[];total=None;page_count=None
    for ordinal,item in enumerate(pages,1):
        value=json.loads(item['content']);request=item['parameters'];archive=item['archive']
        if request.get('SEARCH_DATE')!=query_day or request.get('sqlId')!=SQL:
            raise ValueError('SSE_SUSPENSION_REQUEST_DATE_OR_SCHEMA_MISMATCH')
        if not isinstance(value,dict) or value.get('sqlId')!=SQL or value.get('actionErrors') or value.get('fieldErrors') or value.get('isPagination')!='true':
            raise ValueError('SSE_SUSPENSION_RESPONSE_SCHEMA_UNPROVEN')
        rows=value.get('result');page=value.get('pageHelp')
        if not isinstance(rows,list) or not isinstance(page,dict) or rows!=page.get('data'):
            raise ValueError('SSE_SUSPENSION_RESULT_PAGE_DATA_MISMATCH')
        if any(type(page.get(k)) is not int or page[k]<0 for k in ['total','pageCount','pageNo','pageSize','beginPage','endPage']):
            raise ValueError('SSE_SUSPENSION_PAGE_FIELDS_UNPROVEN')
        if (page['pageNo']!=ordinal or int(request['pageHelp.pageNo'])!=ordinal or
            page['beginPage']!=ordinal or page['endPage']!=ordinal or page['pageSize']!=int(request['pageHelp.pageSize']) or
            len(rows)>page['pageSize'] or page['total']<len(rows)):
            raise ValueError('SSE_SUSPENSION_PAGE_REQUEST_RESPONSE_MISMATCH')
        if total is not None and (total!=page['total'] or page_count!=page['pageCount']):
            raise ValueError('SSE_SUSPENSION_PAGINATION_CHANGED_BETWEEN_PAGES')
        total=page['total'];page_count=page['pageCount']
        echo=value.get('queryDate') or page.get('searchDate')
        if echo:
            try:echo_day=date.fromisoformat(echo).isoformat()
            except (ValueError,TypeError):raise ValueError('SSE_SUSPENSION_RESPONSE_DATE_ECHO_INVALID')
            if echo_day!=query_day:raise ValueError('SSE_SUSPENSION_RESPONSE_DATE_MISMATCH')
        else:gaps.append('SSE_SUSPENSION_RESPONSE_DATE_ECHO_UNPROVEN')
        audits.append({'page_no':ordinal,'raw_hash':archive['sha256'],'returned_count':len(rows),
            'declared_total':total,'page_count_reported':page_count,'page_size_reported':page['pageSize'],
            'response_date_reported':echo,'response_date_verified':bool(echo),
            'source_received_at':archive['received_at']})
        for index,row in enumerate(rows):
            if not isinstance(row,dict) or not isinstance(row.get('PRODUCT_CODE'),str) or not re.fullmatch(r'\d{6}',row['PRODUCT_CODE']):
                raise ValueError('SSE_SUSPENSION_ROW_SECURITY_UNPROVEN')
            if row['PRODUCT_CODE']!=instrument.split(':')[1]:continue
            start=date.fromisoformat(row['SHOW_START_DATE']);end=date.fromisoformat(row['SHOW_END_DATE'])
            if not start<=queried<=end:raise ValueError('SSE_SUSPENSION_MATCHED_SECURITY_DATE_RANGE_INVALID')
            if row.get('CONTROLTYPE')!='TR' or '停牌' not in row.get('STOP_TIME',''):
                raise ValueError('SSE_SUSPENSION_MATCHED_EVENT_KIND_UNPROVEN')
            selected.append({'instrument':instrument,'group':'STATUS','source_id':SOURCE,'trade_date':query_day,
                'raw_hash':archive['sha256'],'query_js_hash':JS_SHA,'source_url':archive['source_url'],
                'row_ordinal':index,'source_page_no':ordinal,'reported_start_date':start.isoformat(),
                'reported_end_date':end.isoformat(),'date_precision':'DATE','resume_date':None,
                'stop_date_reported':row.get('STOP_DATE'),'stop_time_reported':row['STOP_TIME'],
                'reason':row.get('STOP_REASON'),'control_type_reported':row['CONTROLTYPE'],
                'bulletin_type_reported':row.get('BULLETIN_TYPE'),'suspension':True,
                'state':'REPORTED_SUSPENSION_PARTIAL','risk_warning':None,'st_subtype':None,
                'listing_stage':None,'ex_rights':None,'complete_status_verified':False,'system_usable':False,
                'published_at':None,'received_at':archive['received_at'],'available_at':archive['received_at'],
                'known_at':known_at,'historical_pit_claim':False,
                'date_basis':'REQUEST_AND_REPORTED_EVENT_INTERVAL_NOT_ACTUAL_RESUMPTION',
                'basis_raw_hashes':[archive['sha256'],JS_SHA],
                'field_evidence':{'suspension':{'raw_hash':archive['sha256'],'query_js_hash':JS_SHA,
                    'source_locator':f'result[{index}] PRODUCT_CODE/SHOW_START_DATE/SHOW_END_DATE/STOP_TIME'}}})
    if len(selected)>1:raise ValueError('SSE_SUSPENSION_MATCHED_SECURITY_DUPLICATED')
    returned=sum(a['returned_count'] for a in audits)
    matches=bool(total and returned==total and len(pages)==page_count)
    if not total:gaps.append('SSE_SUSPENSION_EMPTY_OR_ZERO_TOTAL_NOT_NORMAL_AUTHORITY')
    if not matches:gaps.append('SSE_SUSPENSION_FINITE_RETURNED_SET_UNPROVEN')
    if page_count and page_count>len(pages):gaps.append('SSE_SUSPENSION_PAGE_BUDGET_EXHAUSTED')
    if not selected:gaps.append('SSE_SUSPENSION_SECURITY_NOT_RETURNED_NOT_NORMAL_AUTHORITY')
    gaps.append('SSE_SUSPENSION_FULL_STATUS_AND_RESUMPTION_UNPROVEN')
    return {'events':selected,'page_audits':audits,'returned_count':returned,'declared_total':total,
        'reported_page_count':page_count,'returned_count_matches_positive_total':matches,
        'gaps':sorted(set(gaps)),'complete_status_verified':False,'no_event_authority':False,'system_usable':False}
