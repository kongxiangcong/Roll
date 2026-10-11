"""Pinned SSE new-stock interval query; scheduled rows never certify actual resumption."""
import hashlib
import json
import re
import os
from datetime import date,datetime
from urllib.parse import parse_qs,urlparse
from uuid import uuid4
import httpx
from fastapi import HTTPException
from roll.accounts.ledger import encode,now
from roll.market.rules import SHANGHAI
from roll.market import sse_suspension
from roll.agents.codex_process import owner_alive,process_creation

SOURCE='sse-stock-suspension-interval'
SQL='GW_PL_JYTS_TFPXX'
DAY_SQL='GW_PL_JYTS_TFPXX_TRADEDAY'
EMPTY_SHA='15a1180483592fa133cc4da6907ad84428fe0bb56ffd672241c456d14a715066'


def fingerprint():
    from roll.market.post_close_packet import code
    return code()


def schema():
    contract=sse_suspension.schema()
    block=contract['js_bytes'].decode('utf-8').split('var suspension_stock = {',1)[1].split('var suspension_fund',1)[0]
    if not all(term in block for term in [SQL,DAY_SQL,"'commonSoaQuery.do'",'bizDate:',
        'beforeTradeDay','productCode:','startStopDate:','endStopDate:',
        '"pageHelp.pageSize": 25','"pageHelp.pageNo": 1','v.productCode','v.startStopDate','v.endStopDate',
        'v.controlType','v.stopTime','v.stopReason','v.endStopReason','v.type']):
        raise ValueError('SSE_STOCK_SCHEMA_UNPROVEN')
    sources={s['role']:s for s in json.loads(contract['mapping_bytes'])['sources']}
    source=sources['suspension_inconsistent'];body=(sse_suspension.REFERENCE/source['path']).read_bytes()
    if source['sha256']!=EMPTY_SHA or len(body)!=source['bytes'] or hashlib.sha256(body).hexdigest()!=EMPTY_SHA:
        raise ValueError('SSE_STOCK_EMPTY_REFERENCE_ORIGINAL_CORRUPT')
    url=urlparse(source['url']);params={k:v[0] for k,v in parse_qs(url.query).items()}
    if url.hostname!='query.sse.com.cn' or url.path!='/commonSoaQuery.do' or params['sqlId']!=SQL:
        raise ValueError('SSE_STOCK_PRIMARY_URL_UNPROVEN')
    value=json.loads(body)
    audit={'raw_hash':EMPTY_SHA,'query_js_hash':sse_suspension.JS_SHA,'source_url':source['url'],
        'received_at':source['received_at'],'requested_start':params['startStopDate'],
        'requested_end':params['endStopDate'],'declared_total':value['pageHelp']['total'],
        'returned_count':len(value['result']),'request_page_size':int(params['pageHelp.pageSize']),
        'response_page_size':value['pageHelp']['pageSize'],'no_event_authority':False,
        'current_coverage_verified':False,'historical_pit_claim':False,
        'gaps':['SSE_STOCK_REFERENCE_EMPTY_TOTAL_MISMATCH','SSE_STOCK_REFERENCE_PAGE_SIZE_MISMATCH']}
    return {**contract,'url':url._replace(query='').geturl(),'empty_bytes':body,'empty_source':source,'reference_empty_audit':audit}


def source_date(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{8}|\d{4}-\d{2}-\d{2}',value):
        raise ValueError('SSE_STOCK_DATE_FORMAT_UNPROVEN')
    return date.fromisoformat(value)


def trade_day(content,host_day):
    value=json.loads(content)
    if not isinstance(value,dict) or value.get('sqlId')!=DAY_SQL or value.get('actionErrors') or value.get('fieldErrors'):
        raise ValueError('SSE_STOCK_TRADE_DAY_SCHEMA_UNPROVEN')
    rows=value.get('result')
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):
        raise ValueError('SSE_STOCK_TRADE_DAY_MISSING_OR_AMBIGUOUS_NO_FALLBACK')
    reported=source_date(rows[0].get('beforeTradeDay'));end=date.fromisoformat(host_day)
    if reported>end:raise ValueError('SSE_STOCK_TRADE_DAY_AFTER_HOST_DATE')
    try:limit=end.replace(year=end.year-3)
    except ValueError:limit=end.replace(year=end.year-3,day=28)
    if reported<limit:raise ValueError('SSE_STOCK_INTERVAL_EXCEEDS_PINNED_CLIENT_THREE_YEARS')
    return reported.isoformat()


def interval_parameters(start,end,n):
    return {'sqlId':SQL,'isPagination':'true','productCode':'600362','keyWords':'',
        'startStopDate':start.replace('-',''),'endStopDate':end.replace('-',''),
        'pageHelp.pageSize':'25','pageHelp.pageNo':str(n)}


def capture_plan(contract,receipt):
    return {'capture_id':receipt['receipt_id'],'collection_plan_id':receipt['plan_id'],
        'created_at':receipt['started_at'],'host_date':receipt['host_date'],'source_id':SOURCE,
        'source_url':contract['url'],'query_js_hash':sse_suspension.JS_SHA,
        'mapping_hash':contract['mapping_hash'],'reference_empty_hash':EMPTY_SHA,
        'parser_fingerprint':receipt['parser_fingerprint'],'request_budget_calls':3,'interval_page_budget':2,
        'trade_day_parameters':{'sqlId':DAY_SQL,'bizDate':receipt['host_date'].replace('-','')},
        'interval_policy':'ONLY_REPORTED_BEFORE_TRADE_DAY_THROUGH_HOST_DATE_MAX_THREE_YEARS',
        'interval_security':'600362','interval_page_size':25,'method':'GET','timeout_seconds':15,
        'max_decoded_bytes_per_response':8*1024*1024,'no_fallback':True,'no_retries':True,
        'system_usable':False,'actual_forward_start':False}


def parse_pages(pages,start,end,known_at):
    selected=[];audits=[];total=None;count=None;gaps=['SSE_STOCK_LATEST_TRADE_DAY_AUTHORITY_UNPROVEN',
        'SSE_STOCK_ACTUAL_RESUMPTION_AND_COMPLETE_STATUS_UNPROVEN']
    for n,item in enumerate(pages,1):
        value=json.loads(item['content']);request=item['parameters'];archive=item['archive']
        if request!=interval_parameters(start,end,n):raise ValueError('SSE_STOCK_REQUEST_INTERVAL_OR_SECURITY_MISMATCH')
        if not isinstance(value,dict) or value.get('sqlId')!=SQL or value.get('actionErrors') or value.get('fieldErrors'):
            raise ValueError('SSE_STOCK_INTERVAL_SCHEMA_UNPROVEN')
        rows=value.get('result');page=value.get('pageHelp')
        if value.get('isPagination')!='true' or not isinstance(rows,list) or not isinstance(page,dict) or rows!=page.get('data'):
            raise ValueError('SSE_STOCK_INTERVAL_PAGE_DATA_UNPROVEN')
        if any(type(page.get(k)) is not int or page[k]<0 for k in ['total','pageCount','pageNo','pageSize']):
            raise ValueError('SSE_STOCK_PAGE_FIELDS_UNPROVEN')
        if page['pageNo']!=n or page['pageSize']!=25 or len(rows)>25 or page['total']<len(rows):
            raise ValueError('SSE_STOCK_PAGE_REQUEST_RESPONSE_MISMATCH')
        if total is not None and (total!=page['total'] or count!=page['pageCount']):
            raise ValueError('SSE_STOCK_PAGINATION_CHANGED_BETWEEN_PAGES')
        total=page['total'];count=page['pageCount']
        # This endpoint's blank date echoes cannot prove the requested interval was selected.
        gaps.append('SSE_STOCK_RESPONSE_INTERVAL_ECHO_UNPROVEN')
        audits.append({'page_no':n,'raw_hash':archive['sha256'],'returned_count':len(rows),
            'declared_total':total,'reported_page_count':count,'reported_page_size':page['pageSize']})
        for index,row in enumerate(rows):
            if not isinstance(row,dict) or row.get('productCode')!='600362':raise ValueError('SSE_STOCK_RESPONSE_SECURITY_MISMATCH')
            first=source_date(row.get('startStopDate'));last_raw=row.get('endStopDate')
            last=source_date(last_raw) if last_raw not in {'',None,'-'} else None
            if first>date.fromisoformat(end) or last and (last<first or last<date.fromisoformat(start)):
                raise ValueError('SSE_STOCK_REPORTED_INTERVAL_MISMATCH')
            if not all(isinstance(row.get(k),str) for k in ['controlType','stopTime','stopReason','endStopReason','type']):
                raise ValueError('SSE_STOCK_REPORTED_EVENT_FIELDS_UNPROVEN')
            selected.append({'instrument':'SSE:600362','group':'STATUS','source_id':SOURCE,
                'trade_date':end,'raw_hash':archive['sha256'],'query_js_hash':sse_suspension.JS_SHA,
                'source_url':archive['source_url'],'source_page_no':n,'row_ordinal':index,
                'reported_start_date':first.isoformat(),'reported_end_date':last.isoformat() if last else None,
                'reported_start_original':row['startStopDate'],'reported_end_original':last_raw,
                'start_date_precision':'DATE','end_date_precision':'DATE' if last else 'UNKNOWN',
                'resume_date':None,'suspension':None,'state':'REPORTED_SCHEDULE_ACTUAL_STATUS_UNKNOWN',
                'risk_warning':None,'st_subtype':None,'listing_stage':None,'ex_rights':None,
                'control_type_reported':row['controlType'],'stop_time_reported':row['stopTime'],
                'stop_reason_reported':row['stopReason'],'end_stop_reason_reported':row['endStopReason'],
                'event_type_reported':row['type'],'complete_status_verified':False,'system_usable':False,
                'published_at':None,'received_at':archive['received_at'],'available_at':archive['received_at'],
                'known_at':known_at,'historical_pit_claim':False,'basis_raw_hashes':[archive['sha256'],sse_suspension.JS_SHA]})
    keys=[(e['reported_start_original'],e['reported_end_original'],e['control_type_reported'],e['stop_time_reported'],e['event_type_reported']) for e in selected]
    if len(keys)!=len(set(keys)):raise ValueError('SSE_STOCK_REPORTED_EVENT_DUPLICATED')
    returned=sum(a['returned_count'] for a in audits);matched=bool(total and total==returned and count==len(pages))
    if not total or not selected:gaps.append('SSE_STOCK_EMPTY_NOT_NORMAL_OR_NO_EVENT_AUTHORITY')
    if not matched:gaps.append('SSE_STOCK_FINITE_RETURNED_SET_UNPROVEN')
    if count and count>len(pages):gaps.append('SSE_STOCK_PAGE_BUDGET_EXHAUSTED')
    return {'events':selected,'page_audits':audits,'returned_count':returned,'declared_total':total,
        'reported_page_count':count,'returned_count_matches_positive_total':matched,'gaps':sorted(set(gaps))}


class StockSuspensions:
    def __init__(self,prospective):
        self.prospective=prospective;self.ledger=prospective.ledger;self.evidence=prospective.evidence
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS stock_suspension_receipts(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS stock_suspension_jobs(plan_id TEXT NOT NULL,day TEXT NOT NULL,value TEXT NOT NULL,PRIMARY KEY(plan_id,day))')
            for saved in db.execute('SELECT plan_id,day,value FROM stock_suspension_jobs'):
                job=json.loads(saved[2])
                if job['state']=='CLAIMED' and not owner_alive(job):
                    job.update(state='INTERRUPTED',finished_at=now(),gaps=['SSE_STOCK_WORKER_INTERRUPTED_NO_IMPLICIT_RETRY'])
                    db.execute('UPDATE stock_suspension_jobs SET value=? WHERE plan_id=? AND day=?',(encode(job),saved[0],saved[1]))

    def jobs(self,plan_id):
        self.prospective.plan(plan_id)
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM stock_suspension_jobs WHERE plan_id=? ORDER BY rowid',(plan_id,))]

    def capture_once(self,plan_id,basis):
        self.prospective.plan(plan_id);day=datetime.fromisoformat(now()).astimezone(SHANGHAI).date().isoformat()
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT value FROM stock_suspension_jobs WHERE plan_id=? AND day=?',(plan_id,day)).fetchone()
            if old:return json.loads(old[0])
            job={'plan_id':plan_id,'day':day,'source_id':SOURCE,'state':'CLAIMED','basis':basis,
                'started_at':now(),'request_budget_calls':3,'actual_forward_start':False,
                'host_owner':{'pid':os.getpid(),'creation_ticks':process_creation(os.getpid())}}
            db.execute('INSERT INTO stock_suspension_jobs VALUES(?,?,?)',(plan_id,day,encode(job)));db.commit()
        try:
            receipt=self.capture(plan_id,basis)
            job.update(state='RECORDED',receipt_id=receipt['receipt_id'],gaps=receipt['gaps'],finished_at=now())
        except HTTPException as error:job.update(state='REFUSED',gaps=[str(error.detail)],finished_at=now())
        with self.ledger.connection() as db:db.execute('UPDATE stock_suspension_jobs SET value=? WHERE plan_id=? AND day=?',(encode(job),plan_id,day))
        return job

    def fetch(self,client,contract,params,receipt):
        receipt['network_calls']+=1
        with client.stream('GET',contract['url'],params=params,headers={'Referer':'https://www.sse.com.cn/'}) as response:
            body=bytearray();truncated=False;stream_error=None
            try:
                for part in response.iter_bytes():
                    remaining=8*1024*1024-len(body);body.extend(part[:remaining])
                    if len(part)>remaining:truncated=True;break
            except httpx.HTTPError as error:stream_error=error
            complete=not truncated and stream_error is None
            archive=self.evidence.archive(bytes(body),'SSE_STOCK_RAW_RESPONSE',source_id=SOURCE,
                source_url=str(response.url),received_at=now(),status_code=response.status_code,
                parameters=params,evidence_kind=receipt['evidence_kind'],original_complete=complete,
                content_type=response.headers.get('content-type'),stream_error=type(stream_error).__name__ if stream_error else None)
            saved={'parameters':params,'archive':archive,'original_complete':complete,
                'reported_metadata':sse_suspension.reported_metadata(bytes(body))}
            if params['sqlId']==DAY_SQL:receipt['trade_day_page']=saved
            else:receipt['pages'].append(saved)
            if stream_error:raise stream_error
            if truncated:raise ValueError('SSE_STOCK_BYTE_LIMIT_PREFIX_ONLY')
            response.raise_for_status()
            return {'content':bytes(body),**saved}

    def capture(self,plan_id,basis):
        plan=self.prospective.plan(plan_id)
        if plan['instrument']!='SSE:600362':raise HTTPException(403,'SSE stock interval only adapts SSE:600362')
        try:contract=schema()
        except (ValueError,KeyError,TypeError,IndexError) as error:raise HTTPException(409,str(error))
        started=now();day=datetime.fromisoformat(started).astimezone(SHANGHAI).date().isoformat()
        if datetime.fromisoformat(started)<datetime.fromisoformat(plan['started_at']):
            raise HTTPException(409,'SSE_STOCK_CAPTURE_BEFORE_COLLECTION_PLAN')
        if any(datetime.fromisoformat(s['received_at'])>datetime.fromisoformat(started) for s in [contract['js_source'],contract['empty_source']]):
            raise HTTPException(409,'SSE_STOCK_SCHEMA_AFTER_CAPTURE')
        for body,kind in [(contract['js_bytes'],'SSE_STOCK_QUERY_JS'),(contract['mapping_bytes'],'SSE_STOCK_MAPPING'),(contract['empty_bytes'],'SSE_STOCK_EMPTY_REFERENCE')]:
            self.evidence.archive(body,kind)
        receipt={'receipt_id':str(uuid4()),'plan_id':plan_id,'instrument':plan['instrument'],'host_date':day,
            'basis':basis,'started_at':started,'source_id':SOURCE,'parser_fingerprint':fingerprint(),
            'query_js_hash':sse_suspension.JS_SHA,'schema_mapping_hash':contract['mapping_hash'],
            'reference_empty_audit':contract['reference_empty_audit'],'request_budget_calls':3,'request_budget_pages':2,
            'evidence_kind':'METHOD_CASE' if self.evidence.transport is not None else 'REAL_SOURCE_ASSESSMENT',
            'network_calls':0,'trade_day_page':None,'pages':[],'errors':[],'reported_before_trade_day':None,
            'latest_trade_day_verified':False,'system_usable':False,'complete_status_verified':False,
            'no_event_authority':False,'actual_forward_start':False,'forward_started_at':None,'capability':'NOT_GRANTED'}
        receipt['capture_plan']=capture_plan(contract,receipt)
        receipt['capture_plan_archive']=self.evidence.archive(encode(receipt['capture_plan']).encode(),'SSE_STOCK_FINITE_CAPTURE_PLAN',
            created_at=started,evidence_kind=receipt['evidence_kind'])
        pages=[]
        try:
            blocked=self.prospective.sources.access(SOURCE,plan['instrument'])
            if blocked:raise ValueError(blocked)
            with httpx.Client(transport=self.evidence.transport,follow_redirects=False,timeout=15) as client:
                raw_day=self.fetch(client,contract,{'sqlId':DAY_SQL,'bizDate':day.replace('-','')},receipt)
                start=trade_day(raw_day['content'],day);receipt['reported_before_trade_day']=start
                receipt['requested_interval']={'start_date':start,'end_date':day,'basis':'REPORTED_BEFORE_TRADE_DAY_THROUGH_ACTUAL_HOST_DATE'}
                for n in range(1,3):
                    pages.append(self.fetch(client,contract,interval_parameters(start,day,n),receipt))
                    parsed=parse_pages(pages,start,day,now())
                    if not parsed['declared_total'] or parsed['reported_page_count']<=n:break
        except (httpx.HTTPError,ValueError,KeyError,TypeError) as error:
            receipt['errors'].append(str(error)[:160] if isinstance(error,ValueError) else type(error).__name__)
        receipt['finished_at']=now();receipt['normalized_known_at']=receipt['finished_at']
        if receipt['errors']:
            parsed={'events':[],'page_audits':[],'returned_count':None,'declared_total':None,'reported_page_count':None,
                'returned_count_matches_positive_total':False,'gaps':['SSE_STOCK_CAPTURE_OR_PARSE_REFUSED']+receipt['errors']}
        else:parsed=parse_pages(pages,receipt['reported_before_trade_day'],day,receipt['normalized_known_at'])
        receipt.update(parsed,status='REFUSED' if receipt['errors'] else 'REPORTED_PARTIAL')
        receipt['archive']=self.evidence.archive(encode(receipt).encode(),'SSE_STOCK_RECEIPT',evidence_kind=receipt['evidence_kind'])
        with self.ledger.connection() as db:db.execute('INSERT INTO stock_suspension_receipts VALUES(?,?,?)',(receipt['receipt_id'],plan_id,encode(receipt)))
        self.prospective.sources.outcome(SOURCE,not receipt['errors'],receipt['status'],receipt['receipt_id'])
        return receipt

    def receipts(self,plan_id,cutoff=None,ids=None):
        self.prospective.plan(plan_id);cutoff=cutoff or datetime.fromisoformat(now())
        with self.ledger.connection() as db:
            saved=[json.loads(r[0]) for r in db.execute('SELECT value FROM stock_suspension_receipts WHERE plan_id=? ORDER BY rowid',(plan_id,))]
        selected=[s for s in saved if datetime.fromisoformat(s['normalized_known_at'])<=cutoff]
        if ids is not None:
            available={s['receipt_id']:s for s in selected}
            if len(set(ids))!=len(ids) or any(i not in available for i in ids):raise HTTPException(409,'SSE_STOCK_RECEIPT_MISSING')
            selected=[available[i] for i in ids]
        for receipt in selected:
            original=json.loads(self.evidence.raw(receipt['archive']['sha256']).read_bytes())
            if original!={k:v for k,v in receipt.items() if k!='archive'}:raise HTTPException(409,'SSE_STOCK_RECEIPT_ORIGINAL_MISMATCH')
            if receipt['parser_fingerprint']!=fingerprint():raise HTTPException(409,'POST_CLOSE_PARSER_CHANGED_SUCCESSOR_REQUIRED')
            try:contract=schema()
            except (ValueError,KeyError,TypeError,IndexError) as error:raise HTTPException(409,str(error))
            if receipt['schema_mapping_hash']!=contract['mapping_hash'] or receipt['query_js_hash']!=sse_suspension.JS_SHA or receipt['reference_empty_audit']!=contract['reference_empty_audit']:
                raise HTTPException(409,'SSE_STOCK_SCHEMA_DEPENDENCY_MISMATCH')
            planned=json.loads(self.evidence.raw(receipt['capture_plan_archive']['sha256']).read_bytes())
            if planned!=receipt['capture_plan'] or planned!=capture_plan(contract,receipt):
                raise HTTPException(409,'SSE_STOCK_CAPTURE_PLAN_ORIGINAL_MISMATCH')
            for digest in [sse_suspension.JS_SHA,contract['mapping_hash'],EMPTY_SHA]:self.evidence.raw(digest)
            day=receipt['host_date'];pages=[];start=None
            for saved in ([receipt['trade_day_page']] if receipt['trade_day_page'] else [])+receipt['pages']:
                body=self.evidence.raw(saved['archive']['sha256']).read_bytes();url=urlparse(saved['archive']['source_url'])
                params={k:v[0] for k,v in parse_qs(url.query,keep_blank_values=True).items()}
                if params!=saved['parameters'] or url._replace(query='').geturl()!=contract['url'] or saved['reported_metadata']!=sse_suspension.reported_metadata(body):
                    raise HTTPException(409,'SSE_STOCK_REQUEST_METADATA_ORIGINAL_MISMATCH')
                if saved['parameters']['sqlId']==DAY_SQL:
                    if saved['parameters']!={'sqlId':DAY_SQL,'bizDate':day.replace('-','')}:raise HTTPException(409,'SSE_STOCK_TRADE_DAY_REQUEST_MISMATCH')
                    if not receipt['errors']:start=trade_day(body,day)
                else:pages.append({'content':body,**saved})
            if not receipt['errors']:
                try:parsed=parse_pages(pages,start,day,receipt['normalized_known_at'])
                except (ValueError,KeyError,TypeError):raise HTTPException(409,'SSE_STOCK_ORIGINAL_PARSE_FAILED')
                if start!=receipt['reported_before_trade_day'] or any(receipt[k]!=v for k,v in parsed.items()):
                    raise HTTPException(409,'SSE_STOCK_NORMALIZED_ORIGINAL_MISMATCH')
        return selected
