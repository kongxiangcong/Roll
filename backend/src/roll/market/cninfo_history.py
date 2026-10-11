"""One fixed CNINFO historical keyword index, never complete action authority."""
import json
import re
from datetime import date,datetime
from pathlib import Path
from urllib.parse import urlparse

REFERENCE=Path(__file__).parent/'reference/cninfo-history'
URL='https://www.cninfo.com.cn/new/hisAnnouncement/query'
KEYWORDS=['停牌','复牌','回购','注销','权益分派','利润分配方案实施','送股','配股']


def candidates(raw,manifest,available_at):
    """Expose raw counts and locators; opaque index dates cannot establish PIT."""
    if manifest['instrument']!='SSE:600362' or len(manifest['queries'])!=8:
        raise ValueError('CNINFO_FIXED_QUERY_SCOPE_INVALID')
    audits=[];by_id={}
    for index,source in enumerate(manifest['queries']):
        form=source['request_form']
        expected={'stock':'600362,gssh0600362','column':'sse','tabName':'fulltext',
            'seDate':'2013-01-01~2025-12-31','searchkey':KEYWORDS[index],
            'sortName':'time','sortType':'asc','pageNum':'1','pageSize':'30'}
        if form!=expected or source['url']!=URL or source['http_status']!=200:
            raise ValueError('CNINFO_FIXED_QUERY_SCOPE_INVALID')
        requested=datetime.fromisoformat(source['requested_at']);received=datetime.fromisoformat(source['received_at'])
        if not requested<=received<=datetime.fromisoformat(available_at):
            raise ValueError('CNINFO_DEPENDENCY_AFTER_NORMALIZATION')
        value=json.loads(raw[source['sha256']])
        total=value.get('totalAnnouncement');record_total=value.get('totalRecordNum');pages=value.get('totalpages')
        if any(type(n) is not int or n<0 for n in (total,record_total,pages)) or type(value.get('hasMore')) is not bool:
            raise ValueError('CNINFO_INDEX_COUNT_SCHEMA_INVALID')
        rows=value.get('announcements')
        if rows is None and total==0:rows=[]
        if not isinstance(rows,list):raise ValueError('CNINFO_INDEX_ROWS_SCHEMA_INVALID')
        gaps=['CNINFO_PAGE_COUNT_SEMANTICS_UNPROVEN']
        if len(rows)!=total or record_total!=total:gaps.append('CNINFO_TOTAL_RETURNED_MISMATCH')
        audit={'query_id':source['query_id'],'raw_hash':source['sha256'],'source_url':source['url'],
            'request_form':form,'search_key':form['searchkey'],'requested_start_date':'2013-01-01',
            'requested_end_date':'2025-12-31','requested_page':1,'requested_page_size':30,
            'returned_count':len(rows),'declared_total':total,'declared_record_total':record_total,
            'returned_count_matches_total':len(rows)==total==record_total,'reported_total_pages':pages,
            'has_more_reported':value['hasMore'],'finite_query_completed':False,'no_event_authority':False,
            'request_date_filter_semantics':'UNPROVEN','received_at':source['received_at'],
            'available_at':available_at,'gaps':gaps}
        ids=[]
        for ordinal,row in enumerate(rows):
            if not isinstance(row,dict) or (row.get('secCode'),row.get('orgId'))!=('600362','gssh0600362'):
                raise ValueError('CNINFO_INDEX_SECURITY_MISMATCH')
            aid=row.get('announcementId');path=row.get('adjunctUrl');title=row.get('announcementTitle')
            if not isinstance(aid,str) or not aid.isdigit() or not isinstance(title,str):
                raise ValueError('CNINFO_CANDIDATE_IDENTITY_INVALID')
            match=re.fullmatch(r'finalpage/(\d{4}-\d{2}-\d{2})/'+re.escape(aid)+r'\.PDF',path or '')
            if not match or row.get('adjunctType')!='PDF':raise ValueError('CNINFO_PDF_LOCATOR_INVALID')
            path_day=date.fromisoformat(match[1]).isoformat()
            variant={'raw_hash':source['sha256'],'query_id':source['query_id'],'row_ordinal':ordinal,
                'received_at':source['received_at'],'reported_row':row}
            if aid not in by_id:
                by_id[aid]={'instrument':'SSE:600362','org_id':'gssh0600362','announcement_id':aid,
                    'title':title,'announcement_time_reported':row.get('announcementTime'),
                    'index_time_precision':'UNKNOWN','published_at':None,'source_path_date':path_day,
                    'pdf_url':'https://static.cninfo.com.cn/'+path,'adjunct_size_reported':row.get('adjunctSize'),
                    'adjunct_size_unit':'UNKNOWN','associate_announcement_reported':row.get('associateAnnouncement'),
                    'available_at':available_at,'historical_pit_claim':False,'lifecycle_state':'UNKNOWN',
                    'revision_chain':None,'cancellation_authority':False,'raw_variants':[]}
            by_id[aid]['raw_variants'].append(variant);ids.append(aid)
        audit['unique_announcement_count']=len(set(ids))
        audit['duplicate_announcement_count']=len(ids)-len(set(ids))
        audits.append(audit)
    return {'candidates':list(by_id.values()),'query_audits':audits,
        'returned_row_count':sum(a['returned_count'] for a in audits),'unique_candidate_count':len(by_id),
        'current_coverage_verified':False,'older_pending_obligations_complete':False,'no_event_authority':False,
        'gaps':sorted(set(['CNINFO_KEYWORD_INDEX_NOT_COMPLETE_ACTION_INVENTORY',
            'CNINFO_INDEX_PUBLICATION_PRECISION_AND_REVISION_CHAIN_UNPROVEN',
            'CNINFO_HISTORICAL_REQUEST_NOT_CURRENT_COVERAGE',
            *[g for a in audits for g in a['gaps']]])),
        'evidence_kind':'REAL_ARCHIVED_SOURCE_ASSESSMENT','historical_pit_claim':False,'network_calls':0}


def cash_links(payload,inventory):
    """Exact ID and PDF URL only; the existing PDF mapping owns lifecycle facts."""
    by_id={c['announcement_id']:c for c in payload['candidates']}
    links=[];unreturned=[];mismatched=[];clues=[]
    for event in inventory['events']:
        aid=event['event_identity'];candidate=by_id.get(aid);source=event['source']
        if candidate is None:unreturned.append(aid);continue
        # PDF extension case does not change an ID/path; domain and dated path must both agree.
        reported=urlparse(candidate['pdf_url']);mapped=urlparse(source['url'])
        if reported.hostname!=mapped.hostname or reported.path.lower()!=mapped.path.lower():
            mismatched.append(aid);continue
        links.append({'announcement_id':aid,'link_basis':'EXACT_ANNOUNCEMENT_ID_AND_PDF_LOCATOR',
            'pdf_source_url':source['url'],'pdf_raw_hash':source['sha256'],'pdf_bytes':source['bytes'],
            'pdf_field_source_locator':event['field_source_locator'],'cash_mapping_hash':inventory['mapping_hash'],
            'candidate_raw_locators':[{k:v[k] for k in ('raw_hash','query_id','row_ordinal')} for v in candidate['raw_variants']],
            'lifecycle_stage':event['lifecycle_stage'],'revision_coverage_verified':False,'actual_account_receipt':None})
    for candidate in payload['candidates']:
        for variant in candidate['raw_variants']:
            row=variant['reported_row'];association=row.get('associateAnnouncement')
            terms=[term for term in ('修订','更正','取消','撤销','终止') if term in row['announcementTitle']]
            if association or terms:clues.append({'announcement_id':candidate['announcement_id'],
                'raw_hash':variant['raw_hash'],'row_ordinal':variant['row_ordinal'],
                'associate_announcement_reported':association,'title_terms_reported':terms,
                'associated_candidate_returned':association in by_id if isinstance(association,str) else False,
                'lifecycle_interpretation':'UNKNOWN'})
    gaps=[]
    if unreturned:gaps.append('CNINFO_KNOWN_CASH_NOTICE_NOT_RETURNED_BY_KEYWORD_INDEX')
    if mismatched:gaps.append('CNINFO_KNOWN_CASH_PDF_LOCATOR_MISMATCH')
    return {'known_cash_links':links,'known_cash_unreturned_ids':sorted(unreturned),
        'known_cash_locator_mismatched_ids':sorted(mismatched),'cash_mapping_hash':inventory['mapping_hash'],
        'revision_cancellation_audit':{'coverage':'UNKNOWN','title_or_association_confirms_lifecycle':False,
            'clues':clues,'all_candidate_lifecycles_resolved':False},
        'unknown_action_categories':inventory['unknown_categories'],'additional_gaps':gaps}
