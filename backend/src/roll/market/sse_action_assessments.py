"""Explicit finite observations of the two saved company action first pages.

Reported dividend rows are candidates; source ordinals are not event/version IDs.
No lifecycle, payment, current absence or complete inventory inference.
"""
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.market.sse_company_actions import PARAMS,fingerprint as collector_fingerprint

REFERENCE=Path(__file__).parent/'reference/sse-company-action-contract'
MAP_SHA='86fba6946b48e649a89d3cbae25661126b991f216029dec30ffc365916a8e489'
GAPS=['ACTION_QUERY_DATE_SCOPE_UNPROVEN','ACTION_DIVIDEND_SOURCE_INVENTORY_UNPROVEN',
      'ACTION_SEND_SHARE_EMPTY_SCOPE_NOT_NEGATIVE_COVERAGE','ACTION_CATEGORY_VERSION_CANCELLATION_INVENTORY_UNPROVEN',
      'ACTION_AUTHORITATIVE_EVENT_IDS_UNPROVEN','ACTION_PAYMENT_ENTITLEMENT_FULFILLMENT_UNPROVEN',
      'ACTION_ALL_OLDER_OBLIGATIONS_UNPROVEN']

class ActionAssessmentCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source_receipt_id:str=Field(min_length=1)
    basis:str=Field(min_length=8)

class ActionPacketCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source_receipt_id:str|None=Field(...,min_length=1)
    predecessor_packet_id:str=Field(min_length=1)
    assessment_ids:list[str]
    basis:str=Field(min_length=8)

def fingerprint():
    return hashlib.sha256(b'SSE_ACTION_ASSESSMENT_V1\n'+Path(__file__).read_bytes().replace(b'\r\n',b'\n')+
                          MAP_SHA.encode()+collector_fingerprint().encode()).hexdigest()

def observed_schema():
    body=(REFERENCE/'observed-sources.json').read_bytes()
    if hashlib.sha256(body).hexdigest()!=MAP_SHA:raise ValueError('ACTION_OBSERVED_SCHEMA_MAPPING_CORRUPT')
    mapping=json.loads(body)
    for source in mapping['sources']:
        raw=(REFERENCE/source['path']).read_bytes()
        if len(raw)!=source['bytes'] or hashlib.sha256(raw).hexdigest()!=source['sha256']:
            raise ValueError('ACTION_OBSERVED_SCHEMA_ORIGINAL_CORRUPT')
    return mapping,body

def date_reported(original):
    if not isinstance(original,str) or len(original)!=8 or not original.isdigit():raise ValueError('ACTION_REPORTED_DATE_INVALID')
    return datetime.strptime(original,'%Y%m%d').date().isoformat()

def parse_page(body,role,raw_hash,source,stamp):
    value=json.loads(body)
    if not isinstance(value,dict) or value.get('sqlId')!=PARAMS[role]['sqlId'] or value.get('isPagination')!='true':
        raise ValueError('ACTION_ROLE_RESPONSE_CONTRACT_MISMATCH')
    if value.get('actionErrors')!=[] or value.get('fieldErrors')!={}:raise ValueError('ACTION_RESPONSE_REPORTED_ERRORS')
    page=value.get('pageHelp');rows=value.get('result')
    if not isinstance(page,dict) or not isinstance(rows,list) or page.get('data')!=rows:
        raise ValueError('ACTION_RESULT_PAGE_DATA_CONFLICT')
    for key in ['total','pageCount','pageNo','pageSize','beginPage','endPage','cacheSize']:
        if type(page.get(key)) is not int or page[key]<0:raise ValueError('ACTION_PAGINATION_INTEGER_UNPROVEN:'+key)
    if any(page[key]!=expected for key,expected in [('pageNo',1),('pageSize',5),('beginPage',1),('endPage',1),('cacheSize',1)]):
        raise ValueError('ACTION_REQUEST_PAGE_MISMATCH')
    if len(rows)>5 or page['total']<len(rows) or page['pageCount']!=(page['total']+4)//5:
        raise ValueError('ACTION_PAGINATION_COUNT_CONFLICT')
    audit={'raw_hash':raw_hash,'returned_count':len(rows),'total_reported':page['total'],
        'page_count_reported':page['pageCount'],'page_no_reported':page['pageNo'],'page_size_reported':page['pageSize'],
        'missing_reported_rows':page['total']-len(rows),'query_date_original':value.get('queryDate'),
        'search_date_original':page.get('searchDate'),'start_date_original':page.get('startDate'),
        'end_date_original':page.get('endDate'),'query_date_scope':'UNKNOWN','complete_action_coverage':False,
        'pagination_state':'EMPTY_FINITE_RESPONSE_SCOPE_UNKNOWN' if not rows else 'FIRST_PAGE_INCOMPLETE' if page['total']>len(rows) else 'FINITE_PAGE_ONLY_SCOPE_UNKNOWN',
        'row_schema_observed':role=='dividend','negative_coverage':False}
    if role=='send_share' and rows:raise ValueError('ACTION_SEND_SHARE_NONEMPTY_SCHEMA_UNOBSERVED')
    candidates=[]
    for index,row in enumerate(rows):
        if not isinstance(row,dict) or row.get('COMPANY_CODE')!='600362' or row.get('A_STOCK_CODE')!='600362':
            raise ValueError('ACTION_DIVIDEND_SECURITY_MISMATCH')
        amount=row.get('A_BEFR_TAX_DIV')
        if not isinstance(amount,str) or not Decimal(amount).is_finite() or Decimal(amount)<0:
            raise ValueError('ACTION_REPORTED_AMOUNT_INVALID')
        candidates.append({'kind':'REPORTED_DIVIDEND_CANDIDATE','company_code':row['COMPANY_CODE'],
            'stock_code':row['A_STOCK_CODE'],'reported_fields':row,'raw_hash':raw_hash,'source_row_pointer':'/result/'+str(index),
            'candidate_id':raw_hash+':/result/'+str(index),'reported_ordinal_original':row.get('NUM'),
            'authoritative_event_id':None,'authoritative_version_id':None,'publication_time':None,'first_available_at':None,
            'source_receipt_id':source['receipt_id'],'source_known_at':source['normalized_known_at'],'normalized_known_at':stamp,
            'record_date_original':row.get('A_REG_DATE'),'record_date_reported':date_reported(row.get('A_REG_DATE')),
            'dividend_date_original':row.get('A_DIV_DATE'),'dividend_date_reported':date_reported(row.get('A_DIV_DATE')),
            'reported_date_precision':'DATE','reported_date_timezone':'UNKNOWN','effective_at':None,
            'cash_before_tax_original':amount,'cash_before_tax_exact':format(Decimal(amount),'f'),
            'cash_per_share_unit':'UNKNOWN','lifecycle_state':'UNKNOWN','payment_fulfilled':None,
            'cancelled':None,'postponed':None,'owned_entitlement':None,'actual_account_event':False})
    return audit,candidates

class ActionAssessments:
    def __init__(self,pages,price_quotes):
        self.pages=pages;self.prospective=pages.prospective;self.ledger=pages.ledger;self.evidence=pages.evidence
        self.price_quotes=price_quotes
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sse_action_assessments(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS sse_action_packets(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,value TEXT NOT NULL)')

    def facts(self,source,stamp):
        mapping,body=observed_schema()
        if datetime.fromisoformat(stamp)<max(datetime.fromisoformat(s['received_at']) for s in mapping['sources']):
            raise ValueError('ACTION_SCHEMA_NOT_KNOWN_AT_ASSESSMENT')
        audits={};candidates=[]
        if set(source['responses'])!=set(PARAMS):raise ValueError('ACTION_SOURCE_ROLE_MISSING')
        for role,response in source['responses'].items():
            if response['error'] or not response['original_complete'] or response['archive']['status_code']!=200:
                raise ValueError('ACTION_SOURCE_RESPONSE_NOT_COMPLETE_SUCCESS')
            sha=response['archive']['sha256'];raw=self.evidence.raw(sha).read_bytes()
            audit,rows=parse_page(raw,role,sha,source,stamp);audits[role]=audit;candidates.extend(rows)
        return {'role_audits':audits,'candidates':candidates,'query_date_scope':'UNKNOWN',
            'complete_action_coverage':False,'pending_older_obligations_complete':False,
            'revision_cancellation_inventory_complete':False,'system_usable':False,'gaps':GAPS}

    def assess(self,plan_id,command):
        stamp=now();source=self.pages.receipts(plan_id,datetime.fromisoformat(stamp),[command.source_receipt_id])[0]
        try:
            facts=self.facts(source,stamp);mapping,body=observed_schema()
        except (ValueError,KeyError,TypeError,ArithmeticError) as error:raise HTTPException(409,str(error))
        self.evidence.archive(body,'ACTION_OBSERVED_SCHEMA_MAPPING')
        for record in mapping['sources']:self.evidence.archive((REFERENCE/record['path']).read_bytes(),'ACTION_OBSERVED_SCHEMA_ORIGINAL')
        value={'assessment_id':str(uuid4()),'plan_id':plan_id,'source_receipt_id':source['receipt_id'],
            'source_archive_hash':source['archive']['sha256'],'collector_fingerprint':source['implementation_fingerprint'],
            'parser_fingerprint':fingerprint(),'schema_mapping_hash':MAP_SHA,'basis':command.basis,
            'normalized_known_at':stamp,'evidence_kind':source['evidence_kind'],'network_calls':0,
            'forward_started_at':None,'capability':'NOT_GRANTED',**facts}
        value['archive']=self.evidence.archive(encode(value).encode(),'SSE_ACTION_ASSESSMENT',evidence_kind=value['evidence_kind'])
        with self.ledger.connection() as db:db.execute('INSERT INTO sse_action_assessments VALUES(?,?,?)',(value['assessment_id'],plan_id,encode(value)))
        return value

    def assessments(self,plan_id,cutoff=None,ids=None):
        self.prospective.plan(plan_id);cutoff=cutoff or datetime.fromisoformat(now())
        with self.ledger.connection() as db:saved=[json.loads(r[0]) for r in db.execute('SELECT value FROM sse_action_assessments WHERE plan_id=? ORDER BY rowid',(plan_id,))]
        selected=[v for v in saved if datetime.fromisoformat(v['normalized_known_at'])<=cutoff]
        if ids is not None:
            available={v['assessment_id']:v for v in selected}
            if len(set(ids))!=len(ids) or any(i not in available for i in ids):raise HTTPException(409,'ACTION_ASSESSMENT_NOT_KNOWN')
            selected=[available[i] for i in ids]
        for value in selected:
            original=json.loads(self.evidence.raw(value['archive']['sha256']).read_bytes())
            if original!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'ACTION_ASSESSMENT_ORIGINAL_MISMATCH')
            if value['parser_fingerprint']!=fingerprint() or value['schema_mapping_hash']!=MAP_SHA:
                raise HTTPException(409,'ACTION_ASSESSMENT_PARSER_CHANGED_SUCCESSOR_REQUIRED')
            source=self.pages.receipts(plan_id,cutoff,[value['source_receipt_id']])[0]
            if source['archive']['sha256']!=value['source_archive_hash'] or source['implementation_fingerprint']!=value['collector_fingerprint']:
                raise HTTPException(409,'ACTION_ASSESSMENT_SOURCE_BINDING_MISMATCH')
            try:facts=self.facts(source,value['normalized_known_at'])
            except (ValueError,KeyError,TypeError,ArithmeticError) as error:raise HTTPException(409,str(error))
            if any(value[key]!=item for key,item in facts.items()):raise HTTPException(409,'ACTION_ASSESSMENT_NORMALIZED_ORIGINAL_MISMATCH')
            for sha in [MAP_SHA,*[s['sha256'] for s in observed_schema()[0]['sources']]]:self.evidence.raw(sha)
        return selected

    def current(self,plan_id):
        values=self.assessments(plan_id)
        return {'assessment_id':values[-1]['assessment_id'] if values else None,'assessments':values,
            'current_complete_action_coverage':False,'pending_older_obligations_complete':False,
            'system_usable':False,'forward_started_at':None,'capability':'NOT_GRANTED',
            'gaps':GAPS if values else ['EXPLICIT_ACTION_ASSESSMENT_MISSING',*GAPS]}

    def predecessor(self,plan_id,packet_id):
        if self.price_quotes.saved_packet(packet_id):return self.price_quotes.packet(plan_id,packet_id)
        return self.price_quotes.predecessor(plan_id,packet_id)

    def packet_inputs(self,plan_id,predecessor_id,source_id,assessment_ids,cutoff):
        predecessor=self.predecessor(plan_id,predecessor_id)
        if datetime.fromisoformat(predecessor['knowledge_cutoff'])>cutoff:raise HTTPException(409,'ACTION_PREDECESSOR_NOT_KNOWN')
        assessments=self.assessments(plan_id,cutoff,assessment_ids)
        if any(a['source_receipt_id']!=source_id for a in assessments):raise HTTPException(409,'ACTION_PACKET_ASSESSMENT_SOURCE_MISMATCH')
        sources=self.pages.receipts(plan_id,cutoff,[] if source_id is None else [source_id])
        return predecessor,assessments,sources

    def build(self,plan_id,command):
        cutoff=datetime.fromisoformat(now())
        predecessor,assessments,sources=self.packet_inputs(plan_id,command.predecessor_packet_id,
            command.source_receipt_id,command.assessment_ids,cutoff)
        value={'packet_type':'ACTION_SUCCESSOR','packet_id':str(uuid4()),'plan_id':plan_id,
            'predecessor_packet_id':command.predecessor_packet_id,'predecessor':predecessor,
            'source_receipt_ids':[s['receipt_id'] for s in sources],'source_receipts':sources,
            'assessment_ids':command.assessment_ids,'assessments':assessments,
            'action_candidates':[r for a in assessments for r in a['candidates']],
            'role_audits':[a['role_audits'] for a in assessments],'knowledge_cutoff':cutoff.isoformat(),
            'created_at':now(),'basis':command.basis,'parser_fingerprint':fingerprint(),'network_calls':0,
            'query_date_scope':'UNKNOWN','complete_action_coverage':False,'pending_older_obligations_complete':False,
            'system_usable':False,'model_daily_input_allowed':False,'forward_admissible':False,
            'forward_started_at':None,'capability':'NOT_GRANTED','account_events_added':0,
            'gaps':GAPS if assessments else ['EXPLICIT_ACTION_ASSESSMENT_MISSING',*GAPS]}
        value['archive']=self.evidence.archive(encode(value).encode(),'SSE_ACTION_SUCCESSOR_PACKET',
            evidence_kind='UNQUALIFIED_DERIVED_PACKET' if not assessments else
                'METHOD_CASE' if any(a['evidence_kind']=='METHOD_CASE' for a in assessments) else 'REAL_SOURCE_ASSESSMENT')
        with self.ledger.connection() as db:db.execute('INSERT INTO sse_action_packets VALUES(?,?,?)',(value['packet_id'],plan_id,encode(value)))
        return value

    def saved_packet(self,packet_id):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM sse_action_packets WHERE id=?',(packet_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def replay(self,packet_id):
        value=self.saved_packet(packet_id)
        if not value:raise HTTPException(404,'ACTION_SUCCESSOR_PACKET_MISSING')
        original=json.loads(self.evidence.raw(value['archive']['sha256']).read_bytes())
        if original!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'ACTION_PACKET_ORIGINAL_MISMATCH')
        if value['parser_fingerprint']!=fingerprint():raise HTTPException(409,'ACTION_PACKET_PARSER_CHANGED_SUCCESSOR_REQUIRED')
        ids=value['source_receipt_ids']
        if len(ids)>1:raise HTTPException(409,'ACTION_PACKET_SOURCE_ID_MISMATCH')
        predecessor,assessments,sources=self.packet_inputs(value['plan_id'],value['predecessor_packet_id'],
            ids[0] if ids else None,value['assessment_ids'],datetime.fromisoformat(value['knowledge_cutoff']))
        matches=(predecessor==value['predecessor'] and assessments==value['assessments'] and sources==value['source_receipts']
            and [r for a in assessments for r in a['candidates']]==value['action_candidates']
            and [a['role_audits'] for a in assessments]==value['role_audits'])
        return {'packet_id':packet_id,'packet_type':'ACTION_SUCCESSOR','matches_original':matches,
            'network_calls':0,'forward_admissible':False,'complete_action_coverage':False,'capability':'NOT_GRANTED'}

    def packet(self,plan_id,packet_id):
        value=self.saved_packet(packet_id)
        if not value or value['plan_id']!=plan_id:raise HTTPException(404,'ACTION_SUCCESSOR_PACKET_MISSING')
        if not self.replay(packet_id)['matches_original']:raise HTTPException(409,'ACTION_PACKET_REPLAY_MISMATCH')
        return value
