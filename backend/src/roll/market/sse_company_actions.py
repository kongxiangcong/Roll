"""Two exact first-page company action queries, raw-only immutable receipts.

The fixed client is a documentary request contract, not a lifecycle response schema.
No automatic polling, page continuation, event/payment or full coverage inference.
"""
import hashlib
import json
import os
import asyncio
from datetime import datetime
from pathlib import Path
from uuid import uuid4
import httpx
from fastapi import HTTPException
from roll.accounts.ledger import encode, now
from roll.agents.codex_process import owner_alive, process_creation
from roll.market.rules import SHANGHAI
from roll.market.sse_company_contract import schema, HTML_SHA, JS_SHA

SOURCE='sse-company-action-pages'
PREPARED_SHA='424fe512ec29f76c415beba626c176fed8261d8ebdb22da25d9fac5d922f29cd'
PREPARED=Path(__file__).parent/'reference/sse-company-action-contract/prepared-plan.json'
URL='https://query.sse.com.cn/commonQuery.do'
SHARED={'isPagination':'true','pageHelp.pageSize':'5','pageHelp.pageNo':'1','pageHelp.beginPage':'1',
        'pageHelp.cacheSize':'1','pageHelp.endPage':'1','COMPANY_CODE':'600362','IS_STAR':'0'}
PARAMS={'dividend':{**SHARED,'sqlId':'COMMON_SSE_CP_GPJCTPZ_GPLB_LRFP_FH_L','CONDITION_ZBA':'1','CONDITION_ZBB':''},
        'send_share':{**SHARED,'sqlId':'COMMON_SSE_CP_GPJCTPZ_GPLB_LRFP_SG_L'}}
GAPS=['ACTION_RAW_ONLY_RESPONSE_SCHEMA_NOT_ASSESSED','ACTION_QUERY_DATE_SCOPE_UNPROVEN',
      'ACTION_CURRENT_COMPLETE_CATEGORY_VERSION_COVERAGE_UNPROVEN','ACTION_PAYMENT_AND_OLDER_OBLIGATIONS_UNPROVEN']

def fingerprint():
    return hashlib.sha256(b'SSE_ACTION_RAW_FIRST_V1\n'+Path(__file__).read_bytes().replace(b'\r\n',b'\n')+
                          PREPARED_SHA.encode()+HTML_SHA.encode()+JS_SHA.encode()).hexdigest()

def contract():
    proof=schema();body=PREPARED.read_bytes()
    if len(body)!=4464 or hashlib.sha256(body).hexdigest()!=PREPARED_SHA:raise ValueError('ACTION_PREPARED_PLAN_CORRUPT')
    prepared=json.loads(body);js=proof['bodies']['company_js'].decode('utf-8')
    html=proof['bodies']['company_html'].decode('utf-8')
    if 'var sseQueryURL = "//query.sse.com.cn/";' not in html or 'commonQueryUrl: sseQueryURL + "commonQuery.do?jsonCallBack=?"' not in js:
        raise ValueError('ACTION_ROOT_CLIENT_PATH_UNPROVEN')
    if [(r['role'],r['url'],r['parameters']) for r in prepared['requests']] != [(role,URL,params) for role,params in PARAMS.items()]:
        raise ValueError('ACTION_EXACT_REQUEST_CONTRACT_MISMATCH')
    for key,role in [('abprofitParams','dividend'),('agprofitParams','send_share')]:
        block=js.split('  '+key+': {',1)[1].split('\n  },',1)[0]
        if PARAMS[role]['sqlId'] not in block or '"pageHelp.pageSize": 5' not in block or 'isPagination: true' not in block:
            raise ValueError('ACTION_DOCUMENT_REQUEST_UNPROVEN')
        if '_this.'+key+'.COMPANY_CODE = _this.stockCode;' not in js:raise ValueError('ACTION_COMPANY_SUBSTITUTION_UNPROVEN')
    return {**proof,'prepared':prepared,'prepared_body':body}

def capture_plan(receipt):
    return {'capture_id':receipt['receipt_id'],'collection_plan_id':receipt['plan_id'],'source_id':SOURCE,
            'created_at':receipt['started_at'],'host_date':receipt['host_date'],
            'prepared_plan_hash':PREPARED_SHA,'html_hash':HTML_SHA,'js_hash':JS_SHA,
            'mapping_hash':receipt['mapping_hash'],'implementation_fingerprint':receipt['implementation_fingerprint'],
            'requests':[{'role':role,'method':'GET','url':URL,'parameters':params} for role,params in PARAMS.items()],
            'declared_client_transport':'POST_JSONP_CALLBACK','actual_variant':'GET_JSON_WITHOUT_CALLBACK',
            'client_transport_equivalence_claim':False,'query_date_scope':'UNKNOWN',
            'request_budget_calls':2,'page_budget_per_role':1,'further_pages_allowed':False,
            'timeout_seconds':15,'max_bytes':8*1024*1024,'follow_redirects':False,'retries':0,'fallbacks':0,
            'system_usable':False}

class CompanyActionPages:
    def __init__(self,prospective):
        self.prospective,self.ledger,self.evidence=prospective,prospective.ledger,prospective.evidence
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS company_action_receipts(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS company_action_jobs(plan_id TEXT NOT NULL,day TEXT NOT NULL,value TEXT NOT NULL,PRIMARY KEY(plan_id,day))')
            for row in db.execute('SELECT plan_id,day,value FROM company_action_jobs'):
                job=json.loads(row[2])
                if job['state']=='CLAIMED' and not owner_alive(job):
                    job.update(state='INTERRUPTED_NO_RETRY',finished_at=now(),gaps=['ACTION_CAPTURE_INTERRUPTED_NO_IMPLICIT_RETRY'])
                    db.execute('UPDATE company_action_jobs SET value=? WHERE plan_id=? AND day=?',(encode(job),row[0],row[1]))

    async def fetch(self,client,role,receipt):
        receipt['network_calls']+=1
        body=bytearray();truncated=False;finished=False;cancelled=False;error=None;status=None;response_url=str(httpx.URL(URL,params=PARAMS[role]));content_type=None
        async def consume():
            nonlocal status,response_url,content_type,truncated,finished
            async with client.stream('GET',URL,params=PARAMS[role],headers={'Referer':'https://www.sse.com.cn/'}) as response:
                status=response.status_code;response_url=str(response.url);content_type=response.headers.get('content-type')
                async for part in response.aiter_bytes():
                    remaining=8*1024*1024-len(body);body.extend(part[:remaining])
                    if len(part)>remaining:truncated=True;break
                finished=not truncated
                if not truncated:response.raise_for_status()
        try:await asyncio.wait_for(consume(),timeout=15)
        except TimeoutError as caught:
            error=type(caught).__name__;cancelled=True;finished=False
        except httpx.HTTPError as caught:error=type(caught).__name__
        if truncated:error='ACTION_BYTE_LIMIT_PREFIX_ONLY'
        completeness=('UNKNOWN_AFTER_CANCELLATION' if cancelled else 'PREFIX_ONLY_BYTE_LIMIT' if truncated
                      else 'COMPLETE_BODY_RECEIVED' if finished else 'UNKNOWN_AFTER_STREAM_ERROR')
        archive=self.evidence.archive(bytes(body),'SSE_ACTION_RAW_RESPONSE',source_id=SOURCE,
            source_url=response_url,parameters=PARAMS[role],received_at=now(),status_code=status,content_type=content_type,
            original_complete=finished,original_completeness=completeness,cancelled=cancelled,
            stream_error=error,evidence_kind=receipt['evidence_kind'])
        receipt['responses'][role]={'archive':archive,'parameters':PARAMS[role],
            'original_complete':finished,'original_completeness':completeness,'cancelled':cancelled,'error':error}
        if error:receipt['errors'][role]=error

    def capture_once(self,plan_id,basis):
        plan=self.prospective.plan(plan_id);started=now();day=datetime.fromisoformat(started).astimezone(SHANGHAI).date().isoformat()
        if plan['instrument']!='SSE:600362':raise HTTPException(403,'Action client only adapts SSE:600362')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            saved=db.execute('SELECT value FROM company_action_jobs WHERE plan_id=? AND day=?',(plan_id,day)).fetchone()
            if saved:
                job=json.loads(saved[0])
                return self.receipts(plan_id,ids=[job['receipt_id']])[0] if job['state']=='RECORDED' else job
            try:proof=contract()
            except (ValueError,KeyError,TypeError,IndexError) as error:raise HTTPException(409,str(error))
            if datetime.fromisoformat(started)<max(datetime.fromisoformat(s) for s in [plan['started_at'],proof['prepared']['prepared_host_at'],*[v['received_at'] for v in proof['sources'].values()]]):
                raise HTTPException(409,'ACTION_DOCUMENT_OR_PLAN_AFTER_CAPTURE')
            job={'plan_id':plan_id,'day':day,'state':'CLAIMED','started_at':started,'request_budget_calls':2,
                 'host_owner':{'pid':os.getpid(),'creation_ticks':process_creation(os.getpid())}}
            db.execute('INSERT INTO company_action_jobs VALUES(?,?,?)',(plan_id,day,encode(job)));db.commit()
        kind='METHOD_CASE' if self.evidence.transport is not None else 'REAL_SOURCE_ASSESSMENT'
        for role,body in proof['bodies'].items():self.evidence.archive(body,'ACTION_DOCUMENT_'+role.upper())
        self.evidence.archive(proof['mapping'],'ACTION_DOCUMENT_MAPPING')
        self.evidence.archive(proof['prepared_body'],'ACTION_PREPARED_DOCUMENTARY_PLAN')
        receipt={'receipt_id':str(uuid4()),'plan_id':plan_id,'instrument':plan['instrument'],'source_id':SOURCE,
                 'basis':basis,'started_at':started,'host_date':day,'implementation_fingerprint':fingerprint(),
                 'document_sources':proof['sources'],'mapping_hash':proof['mapping_hash'],'prepared_plan_hash':PREPARED_SHA,
                 'evidence_kind':kind,'network_calls':0,'request_budget_calls':2,'responses':{},'errors':{},
                 'query_date_scope':'UNKNOWN','assessment_state':'RAW_ONLY_UNASSESSED','action_events':[],
                 'complete_action_coverage':False,'pending_older_obligations_complete':False,'system_usable':False,
                 'forward_started_at':None,'capability':'NOT_GRANTED','historical_pit_claim':False}
        receipt['capture_plan']=capture_plan(receipt)
        receipt['capture_plan_archive']=self.evidence.archive(encode(receipt['capture_plan']).encode(),'ACTION_FINITE_CAPTURE_PLAN',created_at=started,evidence_kind=kind)
        blocked=self.prospective.sources.access(SOURCE,plan['instrument'])
        if blocked:receipt['errors']['access']=blocked
        else:
            async def fetch_roles():
                async with httpx.AsyncClient(transport=self.evidence.transport,follow_redirects=False,timeout=15) as client:
                    for role in PARAMS:await self.fetch(client,role,receipt)
            asyncio.run(fetch_roles())
        receipt.update(finished_at=now(),normalized_known_at=now(),status='RAW_RECEIVED_PARTIAL' if not receipt['errors'] else 'REFUSED_RAW_PARTIAL',gaps=GAPS+list(receipt['errors'].values()))
        receipt['archive']=self.evidence.archive(encode(receipt).encode(),'ACTION_RAW_RECEIPT',evidence_kind=kind)
        job.update(state='RECORDED',receipt_id=receipt['receipt_id'],finished_at=now())
        with self.ledger.connection() as db:
            db.execute('INSERT INTO company_action_receipts VALUES(?,?,?)',(receipt['receipt_id'],plan_id,encode(receipt)))
            db.execute('UPDATE company_action_jobs SET value=? WHERE plan_id=? AND day=?',(encode(job),plan_id,day))
        self.prospective.sources.outcome(SOURCE,not receipt['errors'],receipt['status'],receipt['receipt_id'])
        return receipt

    def receipts(self,plan_id,cutoff=None,ids=None):
        self.prospective.plan(plan_id);cutoff=cutoff or datetime.fromisoformat(now())
        with self.ledger.connection() as db:
            saved=[json.loads(r[0]) for r in db.execute('SELECT value FROM company_action_receipts WHERE plan_id=? ORDER BY rowid',(plan_id,))]
        selected=[s for s in saved if datetime.fromisoformat(s['normalized_known_at'])<=cutoff]
        if ids is not None:
            available={s['receipt_id']:s for s in selected}
            if len(set(ids))!=len(ids) or any(i not in available for i in ids):raise HTTPException(409,'ACTION_RECEIPT_NOT_KNOWN')
            selected=[available[i] for i in ids]
        try:proof=contract()
        except (ValueError,KeyError,TypeError,IndexError) as error:raise HTTPException(409,str(error))
        for value in selected:
            original=json.loads(self.evidence.raw(value['archive']['sha256']).read_bytes())
            if original!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'ACTION_RECEIPT_ORIGINAL_MISMATCH')
            if value['implementation_fingerprint']!=fingerprint():raise HTTPException(409,'ACTION_COLLECTOR_CHANGED_SUCCESSOR_REQUIRED')
            if value['mapping_hash']!=proof['mapping_hash'] or value['document_sources']!=proof['sources'] or value['prepared_plan_hash']!=PREPARED_SHA:
                raise HTTPException(409,'ACTION_DOCUMENT_BINDING_MISMATCH')
            for sha in [HTML_SHA,JS_SHA,proof['mapping_hash'],PREPARED_SHA]:self.evidence.raw(sha)
            plan=json.loads(self.evidence.raw(value['capture_plan_archive']['sha256']).read_bytes())
            if plan!=value['capture_plan'] or plan!=capture_plan(value):raise HTTPException(409,'ACTION_FINITE_PLAN_MISMATCH')
            if value['network_calls']!=len(value['responses']) or value['network_calls']>2:raise HTTPException(409,'ACTION_CAPTURE_BUDGET_MISMATCH')
            for role,response in value['responses'].items():
                self.evidence.raw(response['archive']['sha256'])
                if role not in PARAMS or response['parameters']!=PARAMS[role] or response['archive']['source_url']!=str(httpx.URL(URL,params=PARAMS[role])):
                    raise HTTPException(409,'ACTION_REQUEST_BINDING_MISMATCH')
        return selected
