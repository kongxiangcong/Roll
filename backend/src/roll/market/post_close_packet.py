"""Bounded SSE originals and source-bound post-close input packets.

An exchange timestamp establishes what this response says, not its unit/session
coverage. Missing listing/action authority remains a field-level gap. No HTTP
command can certify completeness or create a forward sample.
"""
import hashlib
import json
import os
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from urllib.parse import parse_qs, urlparse

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from roll.accounts.ledger import encode, now
from roll.market.evidence import DataRequest
from roll.market.rules import SHANGHAI
from roll.market import cninfo_history, known_obligations, sse_suspension, sse_stock_suspension
from roll.agents.codex_process import owner_alive,process_creation

SSE_URL='http://yunhq.sse.com.cn:32041/v1/sh1/list/exchange/equity'
SSE_PARAMS={'select':'code,name,open,high,low,last,volume,amount,prev_close','begin':'0','end':'6000'}
SOURCE='sse-closing-board'
VERSION='source-bound-post-close-v1'
CASH_REFERENCE=Path(__file__).parents[1]/'research/reference/cash-rights'
HISTORY_REFERENCE=Path(__file__).parent/'reference/sse-history'
HISTORY_DAILY_SQL='COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C'


class PacketCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    basis: str=Field(min_length=1,max_length=2000)


class ObligationCommand(PacketCommand):
    protocol_id: str=Field(min_length=1,max_length=100)


def code():
    return hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')+
        (CASH_REFERENCE/'sources.json').read_bytes()+(HISTORY_REFERENCE/'sources.json').read_bytes()+
        Path(cninfo_history.__file__).read_bytes().replace(b'\r\n',b'\n')+
        Path(known_obligations.__file__).read_bytes().replace(b'\r\n',b'\n')+
        Path(sse_suspension.__file__).read_bytes().replace(b'\r\n',b'\n')+
        Path(sse_stock_suspension.__file__).read_bytes().replace(b'\r\n',b'\n')+
        (cninfo_history.REFERENCE/'sources.json').read_bytes()).hexdigest()


def historical_daily(content,units,source,unit_source,available_at):
    """Only the pinned commonQuery daily statistic; no yunhq unit substitution."""
    value=json.loads(content)
    query=parse_qs(urlparse(source['url']).query)
    if (value.get('sqlId')!=HISTORY_DAILY_SQL or value.get('actionErrors') or value.get('fieldErrors') or
        query.get('sqlId')!=[HISTORY_DAILY_SQL] or query.get('SEC_CODE')!=['600362']):
        raise ValueError('SSE_HISTORY_DAILY_QUERY_INVALID')
    day=date.fromisoformat(query['TX_DATE'][0]).isoformat()
    rows=value.get('result')
    if not isinstance(rows,list) or len(rows)!=1:raise ValueError('SSE_HISTORY_DAILY_ROW_MISSING_OR_DUPLICATED')
    row=rows[0]
    if row.get('SEC_CODE')!='600362' or row.get('TX_DATE')!=day.replace('-','') or row.get('DATE_TYPE')!='D':
        raise ValueError('SSE_HISTORY_DAILY_IDENTITY_DATE_MISMATCH')
    js=units.decode('utf-8')
    # Both labels must occur in this statistic's getTurnover branch, not market-wide billion units.
    block=js.split('getTurnover: function () {',1)[1].split('getTurnover',1)[0]
    if (f'sqlId: "{HISTORY_DAILY_SQL}"' not in js or 'stockUnit: "万股"' not in js or
        '成交金额(万元)' not in block or 'renum(data.TRADE_VOL, 2)' not in block or
        'data.TRADE_AMT' not in block or '_openPriceTitle = "开盘价(元)"' not in block):
        raise ValueError('SSE_HISTORY_STATISTIC_UNIT_SOURCE_UNPROVEN')
    vals={k:number(row[field],positive=True) for k,field in [
        ('open','OPEN_PRICE'),('high','HIGH_PRICE'),('low','LOW_PRICE'),('close','CLOSE_PRICE')]}
    o,h,l,c=[Decimal(vals[k]) for k in ['open','high','low','close']]
    if not l<=min(o,c)<=max(o,c)<=h:raise ValueError('SSE_HISTORY_DAILY_OHLC_INVALID')
    volume,amount=number(row['TRADE_VOL']),number(row['TRADE_AMT'])
    if (Decimal(volume)==0)!=(Decimal(amount)==0):raise ValueError('SSE_HISTORY_DAILY_ZERO_QUANTITY_CONFLICT')
    return {'instrument':'SSE:600362','group':'HISTORICAL_DAILY_ASSESSMENT','trade_date':day,**vals,
        'source_id':'sse-historical-daily-statistic','raw_hash':source['sha256'],
        'source_url':source['url'],'unit_source_hash':unit_source['sha256'],
        'basis_raw_hashes':[source['sha256'],unit_source['sha256']],
        'volume_reported':volume,'amount_reported':amount,'source_volume_unit':'10000_SHARES',
        'source_amount_unit':'10000_CNY','volume_shares':format(Decimal(volume)*10000,'f'),
        'amount_yuan':format(Decimal(amount)*10000,'f'),'amount_precision_yuan':'100',
        'received_at':source['received_at'],'unit_source_received_at':unit_source['received_at'],
        'available_at':available_at,'published_at':None,'revision_chain':None,
        'historical_pit_claim':False,'model_daily_input_allowed':False,'current_board_unit_authority':False,
        'unit_source_locator':'stockUnit + turnoverParams.sqlId + getTurnover A-share branch',
        'completion_state':'REPORTED_HISTORICAL_STATISTIC_NOT_CURRENT_COMPLETE_INPUT',
        'turnover_scope':'HISTORICAL_QUERY_STATISTIC_ONLY','parser_fingerprint':code()}


def historical_suspension(content,query_js,source,js_source,available_at):
    value=json.loads(content)
    query=parse_qs(urlparse(source['url']).query)
    sql='COMMON_SSE_XXPL_JYTS_TFPXX_L'
    if (value.get('sqlId')!=sql or query.get('sqlId')!=[sql] or value.get('actionErrors') or
        value.get('fieldErrors') or sql not in query_js.decode('utf-8')):
        raise ValueError('SSE_HISTORY_SUSPENSION_QUERY_UNPROVEN')
    queried=date.fromisoformat(query['SEARCH_DATE'][0])
    rows=value.get('result');page=value.get('pageHelp',{})
    total=page.get('total')
    if not isinstance(rows,list) or type(total) is not int or total<0:raise ValueError('SSE_HISTORY_SUSPENSION_PAGE_INVALID')
    completed=(value.get('isPagination')=='true' and rows==page.get('data') and len(rows)==total and
        page.get('pageNo')==1 and page.get('beginPage')==1 and page.get('pageCount')==1)
    audit={'source_role':'suspension','raw_hash':source['sha256'],'query_js_hash':js_source['sha256'],
        'source_url':source['url'],'query_date':queried.isoformat(),'returned_count':len(rows),'declared_total':total,
        'page_no':page.get('pageNo'),'page_count':page.get('pageCount'),'page_size':page.get('pageSize'),
        'finite_query_completed':completed,'complete_current_status':False,'no_event_authority':False,
        'scope':'ONE_HISTORICAL_DATE_MARKET_RETURNED_EVENTS_ONLY','received_at':source['received_at'],
        'available_at':available_at,'gaps':[] if completed else ['SSE_HISTORY_SUSPENSION_TOTAL_RETURNED_MISMATCH']}
    selected=[r for r in rows if isinstance(r,dict) and r.get('PRODUCT_CODE')=='600362']
    if len(selected)>1:raise ValueError('SSE_HISTORY_SUSPENSION_SECURITY_DUPLICATED')
    events=[]
    for row in selected:
        start=date.fromisoformat(row['SHOW_START_DATE']);end=date.fromisoformat(row['SHOW_END_DATE'])
        if start>end or not start<=queried<=end:raise ValueError('SSE_HISTORY_SUSPENSION_DATE_RANGE_INVALID')
        if row.get('CONTROLTYPE')!='TR' or '停牌' not in row.get('STOP_TIME',''):
            raise ValueError('SSE_HISTORY_SUSPENSION_KIND_UNSUPPORTED')
        events.append({'instrument':'SSE:600362','group':'HISTORICAL_SUSPENSION_ASSESSMENT',
            'source_id':'sse-historical-suspension','raw_hash':source['sha256'],'query_raw_hash':source['sha256'],
            'query_js_hash':js_source['sha256'],'basis_raw_hashes':[source['sha256'],js_source['sha256']],
            'reported_start_date':start.isoformat(),'reported_end_date':end.isoformat(),
            'stop_time_reported':row['STOP_TIME'],'stop_date_reported':row['STOP_DATE'],
            'control_type_reported':row['CONTROLTYPE'],'bulletin_type_reported':row['BULLETIN_TYPE'],
            'reason':row['STOP_REASON'],'resume_date':None,'published_at':None,'source_url':source['url'],
            'received_at':source['received_at'],'available_at':available_at,'date_precision':'DATE',
            'historical_pit_claim':False,'complete_status_verified':False,'current_status_authority':False,
            'source_locator':'result[PRODUCT_CODE=600362]','parser_fingerprint':code()})
    return events,audit


def historical_empty_audits(raw,sources,available_at):
    """Observed empty/error metadata are useful gaps, never ordinary trading proof."""
    audits=[]
    for role,sql in [('daily_empty',HISTORY_DAILY_SQL),('suspension_inconsistent','GW_PL_JYTS_TFPXX')]:
        source=sources[role];value=json.loads(raw[role]);query=parse_qs(urlparse(source['url']).query)
        rows=value.get('result');page=value.get('pageHelp',{})
        if (value.get('sqlId')!=sql or query.get('sqlId')!=[sql] or not isinstance(rows,list) or
            value.get('actionErrors') or value.get('fieldErrors')):raise ValueError('SSE_HISTORY_EMPTY_QUERY_SCHEMA_INVALID')
        audit={'source_role':role,'source_url':source['url'],'raw_hash':source['sha256'],
            'received_at':source['received_at'],'available_at':available_at,'returned_count':len(rows),
            'declared_total':page.get('total'),'finite_query_completed':False,
            'no_event_authority':False,'complete_current_status':False,'gaps':[]}
        if role=='daily_empty':
            if query.get('SEC_CODE')!=['600362'] or rows:raise ValueError('SSE_HISTORY_EMPTY_DAILY_SCOPE_CHANGED')
            audit['query_date']=date.fromisoformat(query['TX_DATE'][0]).isoformat()
            audit['gaps']=['SSE_HISTORY_DAILY_NO_ROWS_NOT_NO_TRADE_EVIDENCE']
        else:
            if query.get('productCode')!=['600362']:raise ValueError('SSE_HISTORY_EMPTY_SUSPENSION_SCOPE_CHANGED')
            start=datetime.strptime(query['startStopDate'][0],'%Y%m%d').date()
            end=datetime.strptime(query['endStopDate'][0],'%Y%m%d').date()
            if start>end:raise ValueError('SSE_HISTORY_EMPTY_QUERY_DATE_RANGE_INVALID')
            audit.update(requested_start_date=start.isoformat(),requested_end_date=end.isoformat(),
                page_no=page.get('pageNo'),page_count=page.get('pageCount'),page_size=page.get('pageSize'),
                requested_page_size=int(query['pageHelp.pageSize'][0]),data_matches_result=page.get('data')==rows)
            if type(page.get('total')) is not int or page['total']!=len(rows):
                audit['gaps'].append('SSE_HISTORY_SUSPENSION_TOTAL_RETURNED_MISMATCH')
            if audit['page_size']!=audit['requested_page_size']:
                audit['gaps'].append('SSE_HISTORY_SUSPENSION_REQUEST_RESPONSE_PAGE_SIZE_MISMATCH')
        audits.append(audit)
    return audits


def number(value,positive=False):
    if isinstance(value,bool):raise ValueError('SSE_NUMERIC_FIELD_INVALID')
    try: result=Decimal(str(value))
    except (InvalidOperation,ValueError):raise ValueError('SSE_NUMERIC_FIELD_INVALID')
    if not result.is_finite() or result<0 or positive and result==0:
        raise ValueError('SSE_NUMERIC_FIELD_INVALID')
    return format(result,'f')


def differs(left,right,field):
    if field in {'open','high','low','close','volume_shares','amount_yuan','amount_precision_yuan'} and left is not None and right is not None:
        try:return Decimal(number(left))!=Decimal(number(right))
        except ValueError:return True
    return left!=right


def closing_facts(content,archive,instrument,day):
    """Pinned field order, exact one security/date, never zero-fill bad values."""
    value=json.loads(content,parse_float=Decimal)
    if not isinstance(value,dict) or str(value.get('date'))!=day.replace('-',''):
        raise ValueError('SSE_CLOSING_DATE_MISMATCH')
    tick=value.get('time')
    if type(tick) is not int:raise ValueError('SSE_SOURCE_TIME_MISSING')
    try: source_time=datetime.strptime(str(tick).zfill(6),'%H%M%S').time()
    except ValueError:raise ValueError('SSE_SOURCE_TIME_INVALID')
    if tick<150000:raise ValueError('SSE_SESSION_NOT_CLOSED')
    upstream=datetime.fromisoformat(day+'T'+source_time.isoformat()+'+08:00')
    if upstream>datetime.fromisoformat(archive['received_at']):raise ValueError('SSE_SOURCE_TIME_AFTER_RECEIPT')
    if not isinstance(value.get('list'),list):raise ValueError('SSE_BOARD_ROWS_INVALID')
    rows=[r for r in value['list'] if isinstance(r,list) and r and r[0]==instrument.split(':')[1]]
    if len(rows)!=1 or len(rows[0])!=9:raise ValueError('SSE_SECURITY_ROW_MISSING_OR_DUPLICATED')
    row=rows[0]
    if not isinstance(row[1],str) or not row[1].strip():raise ValueError('SSE_SECURITY_NAME_MISSING')
    vals={k:number(row[i]) for k,i in [('open',2),('high',3),('low',4),('close',5),
        ('volume_reported',6),('amount_reported',7),('exchange_reference_close',8)]}
    o,h,l,c=[Decimal(vals[k]) for k in ['open','high','low','close']]
    suspended=o==h==l==c==0 and Decimal(vals['exchange_reference_close'])>0
    if not suspended and (min(o,h,l,c)<=0 or not l<=min(o,c)<=max(o,c)<=h):
        raise ValueError('SSE_INVALID_OHLC_RANGE')
    if (Decimal(vals['volume_reported'])==0)!=(Decimal(vals['amount_reported'])==0):
        raise ValueError('SSE_ZERO_VOLUME_AMOUNT_CONFLICT')
    common={'instrument':instrument,'source_id':SOURCE,'upstream_source':'SSE','source_url':archive['source_url'],
        'trade_date':day,'raw_hash':archive['sha256'],'basis_raw_hashes':[archive['sha256']],
        'received_at':archive['received_at'],'available_at':archive['received_at'],'published_at':None,
        'upstream_at':upstream.isoformat(),'source_close_time':source_time.isoformat(),
        'available_basis':'ACTUAL_HOST_RECEIPT_NOT_BACKDATED_SOURCE_TIME','historical_pit_claim':False,
        'parser_fingerprint':code(),'errors':[]}
    daily={**common,**vals,'group':'DAILY','adjustment':'RAW','volume_unit':'UNKNOWN',
        'source_volume_unit':'UNVERIFIED_SSE_BOARD','source_amount_unit':'UNVERIFIED_SSE_BOARD',
        'volume_shares':None,'amount_yuan':None,'amount_precision_yuan':None,'turnover_scope':'UNKNOWN',
        'completion_state':'CLOSED_TIMESTAMP_REPORTED_SCOPE_UNVERIFIED','model_daily_input_allowed':False,
        'limitations':['BOARD_UNIT_AND_SESSION_TURNOVER_COVERAGE_UNVERIFIED'],'cash_events_effective':[]}
    warned='ST' in row[1].upper()
    status={**common,'group':'STATUS','state':'SUSPENDED' if suspended else 'NORMAL_PARTIAL',
        'suspension':suspended,'risk_warning':warned,'risk_warning_basis':'REPORTED_SECURITY_NAME',
        'st_subtype':'DELISTING_RISK' if row[1].startswith('*ST') else 'OTHER_RISK' if warned else None,
        'listing_stage':None,'ex_rights':None,'complete_status_verified':False,
        'field_evidence':{k:{'raw_hash':archive['sha256'],'available_at':archive['received_at'],
            'source_locator':'list['+instrument.split(':')[1]+']'} for k in ['suspension','risk_warning']},
        'limitations':['LISTING_STAGE_UNKNOWN','EX_RIGHTS_AND_ACTIVE_ACTION_COVERAGE_UNKNOWN']}
    return [daily,status]


class PostClosePackets:
    def __init__(self,prospective):
        self.prospective=prospective
        self.evidence,self.ledger=prospective.evidence,prospective.ledger
        self.stock_suspensions=sse_stock_suspension.StockSuspensions(prospective)
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS post_close_packets(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS post_close_capture_jobs(plan_id TEXT NOT NULL,day TEXT NOT NULL,value TEXT NOT NULL,PRIMARY KEY(plan_id,day))')
            db.execute('CREATE TABLE IF NOT EXISTS post_close_source_assessments(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS post_close_obligation_audits(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,protocol_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS post_close_suspension_receipts(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,day TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS post_close_suspension_jobs(plan_id TEXT NOT NULL,day TEXT NOT NULL,value TEXT NOT NULL,PRIMARY KEY(plan_id,day))')
            for saved in db.execute('SELECT plan_id,day,value FROM post_close_suspension_jobs'):
                job=json.loads(saved[2])
                if job['state']=='CLAIMED' and not owner_alive(job):
                    job.update(state='INTERRUPTED',finished_at=now(),gaps=['SSE_SUSPENSION_WORKER_STOPPED_NO_IMPLICIT_RETRY'])
                    db.execute('UPDATE post_close_suspension_jobs SET value=? WHERE plan_id=? AND day=?',(encode(job),saved[0],saved[1]))
            for saved in db.execute('SELECT plan_id,day,value FROM post_close_capture_jobs'):
                job=json.loads(saved[2])
                if job['state']=='CLAIMED' and not owner_alive(job):
                    job.update(state='INTERRUPTED',finished_at=now(),gaps=['PROCESS_STOPPED_BEFORE_SOURCE_JOB_COMPLETION'])
                    db.execute('UPDATE post_close_capture_jobs SET value=? WHERE plan_id=? AND day=?',(encode(job),saved[0],saved[1]))

    def history_payload(self,available_at,register=False):
        body=(HISTORY_REFERENCE/'sources.json').read_bytes()
        manifest=json.loads(body)
        sources={s['role']:s for s in manifest['sources']}
        raw={}
        for role,source in sources.items():
            content=(HISTORY_REFERENCE/source['path']).read_bytes() if register else self.evidence.raw(source['sha256']).read_bytes()
            if len(content)!=source['bytes'] or hashlib.sha256(content).hexdigest()!=source['sha256']:
                raise HTTPException(409,'SSE_HISTORY_REFERENCE_ORIGINAL_CORRUPT')
            if datetime.fromisoformat(source['received_at'])>datetime.fromisoformat(available_at):
                raise HTTPException(409,'SSE_HISTORY_DEPENDENCY_AFTER_NORMALIZATION')
            if register:self.evidence.archive(content,'SSE_HISTORY_SOURCE_ORIGINAL',source_id='sse-history-assessment',
                source_url=source['url'],received_at=source['received_at'],evidence_kind='REAL_ARCHIVED_SOURCE_ASSESSMENT')
            raw[role]=content
        mapping_hash=hashlib.sha256(body).hexdigest()
        if register:self.evidence.archive(body,'SSE_HISTORY_SOURCE_MAPPING')
        else:self.evidence.raw(mapping_hash)
        try:
            bar=historical_daily(raw['daily'],raw['daily_units'],sources['daily'],sources['daily_units'],available_at)
            events,audit=historical_suspension(raw['suspension'],raw['suspension_query_js'],
                sources['suspension'],sources['suspension_query_js'],available_at)
            audits=[audit,*historical_empty_audits(raw,sources,available_at)]
        except (ValueError,KeyError,IndexError,TypeError) as error:raise HTTPException(409,str(error))
        return {'daily_facts':[bar],'suspension_facts':events,'query_audits':audits,
            'source_hashes':[s['sha256'] for s in manifest['sources']],'mapping_hash':mapping_hash,
            'current_coverage_verified':False,'gaps':['HISTORICAL_PUBLICATION_AND_REVISION_CHAIN_UNPROVEN',
                'HISTORICAL_SOURCES_CANNOT_CERTIFY_CURRENT_BOARD_UNITS_OR_STATUS',
                *sorted(set(g for audit in audits for g in audit['gaps']))],
            'evidence_kind':'REAL_ARCHIVED_SOURCE_ASSESSMENT','historical_pit_claim':False,'network_calls':0}

    def assess_history(self,plan_id,basis):
        plan=self.prospective.plan(plan_id)
        if plan['instrument']!='SSE:600362':raise HTTPException(403,'SSE历史原件仅适配 SSE:600362')
        available_at=now()
        value={'assessment_id':str(uuid4()),'plan_id':plan_id,'instrument':plan['instrument'],
            'basis':basis,'normalized_known_at':available_at,'parser_fingerprint':code(),
            **self.history_payload(available_at,register=True)}
        value['archive']=self.evidence.archive(encode(value).encode(),'SSE_HISTORY_SOURCE_ASSESSMENT',
            evidence_kind=value['evidence_kind'])
        with self.ledger.connection() as db:db.execute('INSERT INTO post_close_source_assessments VALUES(?,?,?)',
            (value['assessment_id'],plan_id,encode(value)))
        return value

    def history(self,plan_id,cutoff,ids=None):
        self.prospective.plan(plan_id)
        with self.ledger.connection() as db:
            saved=[json.loads(r[0]) for r in db.execute('SELECT value FROM post_close_source_assessments WHERE plan_id=? ORDER BY rowid',(plan_id,))]
        selected=[s for s in saved if datetime.fromisoformat(s['normalized_known_at'])<=cutoff]
        if ids is not None:
            by_id={s['assessment_id']:s for s in selected}
            if len(set(ids))!=len(ids) or any(i not in by_id for i in ids):raise HTTPException(409,'SSE_HISTORY_ASSESSMENT_MISSING')
            selected=[by_id[i] for i in ids]
        for value in selected:
            original=json.loads(self.evidence.raw(value['archive']['sha256']).read_bytes())
            if original!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'SSE_HISTORY_ASSESSMENT_ARCHIVE_MISMATCH')
            if value['parser_fingerprint']!=code():raise HTTPException(409,'POST_CLOSE_PARSER_CHANGED_SUCCESSOR_REQUIRED')
            family=value.get('source_family','SSE_HISTORY')
            if family not in {'SSE_HISTORY','CNINFO_HISTORY'}:raise HTTPException(409,'POST_CLOSE_HISTORY_FAMILY_UNKNOWN')
            computed=(self.cninfo_payload(value['normalized_known_at']) if family=='CNINFO_HISTORY'
                else self.history_payload(value['normalized_known_at']))
            if any(value[k]!=v for k,v in computed.items()):raise HTTPException(409,'SSE_HISTORY_NORMALIZED_ORIGINAL_MISMATCH')
        return selected

    def cninfo_payload(self,available_at,register=False):
        body=(cninfo_history.REFERENCE/'sources.json').read_bytes();manifest=json.loads(body)
        raw={}
        for source in manifest['queries']:
            sha=source['sha256']
            if source['file']!=sha+'.raw':raise HTTPException(409,'CNINFO_REFERENCE_LOCATOR_INVALID')
            content=(cninfo_history.REFERENCE/source['file']).read_bytes() if register else self.evidence.raw(sha).read_bytes()
            if len(content)!=source['bytes'] or hashlib.sha256(content).hexdigest()!=sha:
                raise HTTPException(409,'CNINFO_REFERENCE_ORIGINAL_CORRUPT')
            if register:self.evidence.archive(content,'CNINFO_HISTORY_INDEX_ORIGINAL',source_id='cninfo-history-candidates',
                source_url=source['url'],received_at=source['received_at'],evidence_kind='REAL_ARCHIVED_SOURCE_ASSESSMENT')
            raw[sha]=content
        mapping_hash=hashlib.sha256(body).hexdigest()
        if register:self.evidence.archive(body,'CNINFO_HISTORY_QUERY_MAPPING')
        else:self.evidence.raw(mapping_hash)
        try:
            payload=cninfo_history.candidates(raw,manifest,available_at)
            inventory=self.cash_inventory(datetime.fromisoformat(available_at),register=register,verify_archives=not register)
            links=cninfo_history.cash_links(payload,inventory)
            payload['gaps']=sorted(set(payload['gaps']+links.pop('additional_gaps')))
            payload.update(links)
        except (ValueError,KeyError,TypeError) as error:raise HTTPException(409,str(error))
        return {**payload,'source_hashes':list(raw),'mapping_hash':mapping_hash,'source_family':'CNINFO_HISTORY'}

    def assess_cninfo_history(self,plan_id,basis):
        plan=self.prospective.plan(plan_id)
        if plan['instrument']!='SSE:600362':raise HTTPException(403,'CNINFO历史原件仅适配 SSE:600362')
        available_at=now()
        value={'assessment_id':str(uuid4()),'plan_id':plan_id,'instrument':plan['instrument'],'basis':basis,
            'normalized_known_at':available_at,'parser_fingerprint':code(),**self.cninfo_payload(available_at,register=True)}
        value['archive']=self.evidence.archive(encode(value).encode(),'CNINFO_HISTORY_SOURCE_ASSESSMENT',
            evidence_kind=value['evidence_kind'])
        with self.ledger.connection() as db:db.execute('INSERT INTO post_close_source_assessments VALUES(?,?,?)',
            (value['assessment_id'],plan_id,encode(value)))
        return value

    def source_gaps(self,plan_id):
        plan=self.prospective.plan(plan_id)
        cutoff=datetime.fromisoformat(now())
        audits=self.obligations(plan_id,cutoff)
        suspension=self.suspension_receipts(plan_id,cutoff)
        stock=self.stock_suspensions.receipts(plan_id,cutoff)
        rows,gaps,_=self.inputs(self.prospective.as_of(plan_id,cutoff)['versions'],plan['instrument'],cutoff,
            self.acquisitions(plan_id,cutoff),audits,suspension,stock)
        history=self.history(plan_id,cutoff)
        return {'plan_id':plan_id,'instrument':plan['instrument'],'gaps':gaps,
            'source_gaps':['CURRENT_BOARD_UNIT_SOURCE_UNVERIFIED','CURRENT_STATUS_LISTING_RELISTING_SOURCE_UNADAPTED',
                'CURRENT_RISK_WARNING_SUBTYPE_COMPLETE_SOURCE_UNADAPTED','CURRENT_ACTION_INTERVAL_AND_FULL_OLDER_OBLIGATION_COVERAGE_UNADAPTED'],
            'historical_source_assessments':history,'historical_source_gaps':sorted(set(g for s in history for g in s['gaps'])),
            'known_obligation_audits':audits,'known_obligation_gaps':sorted(set(g for a in audits for g in a['gaps'])),
            'suspension_receipts':suspension,'suspension_source_gaps':sorted(set(g for s in suspension for g in s['gaps'])),
            'stock_suspension_receipts':stock,'stock_suspension_jobs':self.stock_suspensions.jobs(plan_id),
            'stock_suspension_source_gaps':sorted(set(g for s in stock for g in s['gaps'])),
            'network_calls':0,
            'forward_admissible':bool(rows) and not gaps,'forward_started_at':None,'capability':'NOT_GRANTED'}

    def obligation_protocol(self,protocol_id,instrument):
        protocol=self.prospective.registry.get(protocol_id)
        design=protocol.get('design',{});horizon=design.get('horizon_sessions')
        if instrument not in protocol['scope'].get('instruments',[]) or type(horizon) is not int or horizon!=20:
            raise HTTPException(422,'KNOWN_OBLIGATION_AUDIT_REGISTERED_INSTRUMENT_AND_20_SESSION_DESIGN_REQUIRED')
        dataset=self.prospective.registry.dataset(protocol['dataset_id'])
        return {'protocol_id':protocol_id,'protocol_fingerprint':protocol['protocol_fingerprint'],
            'instrument':instrument,'design_hash':hashlib.sha256(encode(design).encode()).hexdigest(),
            'horizon_sessions':horizon,'protocol_evidence_kind':dataset['source_evidence_kind'],
            'scope':'REGISTERED_DESIGN_REFERENCE_NOT_NEW_CONFIRMATORY_CHECKPOINT'}

    def obligation_window(self,context,cutoff,register=False):
        local=cutoff.astimezone(SHANGHAI);start=local.date();day=start
        sessions=0;calendar=[];sources={};gaps=[];end=None
        for _ in range(366):
            info=self.evidence.market.rules.calendar('SSE',day)
            source=info.get('source')
            if source:
                sha=source['sha256'];path=self.evidence.directory/source['archive_path']
                body=path.read_bytes() if register else self.evidence.raw(sha).read_bytes()
                if len(body)!=source['bytes'] or hashlib.sha256(body).hexdigest()!=sha:
                    raise HTTPException(409,'OBLIGATION_CALENDAR_ORIGINAL_CORRUPT')
                if datetime.fromisoformat(source['fetched_at'])>cutoff:
                    raise HTTPException(409,'OBLIGATION_CALENDAR_AFTER_CUTOFF')
                if register and sha not in sources:self.evidence.archive(body,'KNOWN_OBLIGATION_CALENDAR_REFERENCE',
                    path.suffix.lstrip('.'),source_id=source['id'],source_url=source['url'],received_at=source['fetched_at'])
                sources[sha]=source
            calendar.append({'date':day.isoformat(),'is_trading_day':info['is_trading_day'],
                'calendar_version':info.get('calendar_version'),'source_hash':source['sha256'] if source else None})
            if info['is_trading_day'] is None:
                gaps.append('PROTOCOL_REFERENCE_WINDOW_CALENDAR_UNKNOWN');break
            if day>start and info['is_trading_day'] is True:sessions+=1
            if sessions==context['horizon_sessions']:end=day.isoformat();break
            day+=timedelta(days=1)
        if not end and not gaps:gaps.append('PROTOCOL_REFERENCE_WINDOW_HORIZON_NOT_COVERED')
        return {'protocol_id':context['protocol_id'],'design_hash':context['design_hash'],
            'horizon_sessions':context['horizon_sessions'],'start_date':start.isoformat(),'end_date':end,
            'reference_checkpoint_id':'POST_CLOSE_1505_SHANGHAI','reference_checkpoint_at':start.isoformat()+'T15:05:00+08:00',
            'reference_checkpoint_reached':local.time().isoformat()>='15:05:00',
            'reference_checkpoint_is_trading_day':calendar[0]['is_trading_day'],
            'calendar_source_hashes':list(sources),'calendar_sources':list(sources.values()),
            'calendar_dates':calendar,'covered_future_sessions':sessions,'gaps':gaps,
            'scope':'PROTOCOL_EVALUATION_EXECUTION_REFERENCE_WINDOW_NOT_FORWARD_START_OR_STATISTICAL_LOOK'}

    def obligation_payload(self,protocol_id,instrument,cutoff,register=False):
        context=self.obligation_protocol(protocol_id,instrument)
        body=encode(context).encode();context_sha=hashlib.sha256(body).hexdigest()
        if register:self.evidence.archive(body,'KNOWN_OBLIGATION_PROTOCOL_REFERENCE')
        else:self.evidence.raw(context_sha)
        window=self.obligation_window(context,cutoff,register)
        inventory=self.cash_inventory(cutoff,register=register,verify_archives=not register)
        try:payload=known_obligations.notice_audit(inventory,window,cutoff.astimezone(SHANGHAI).isoformat())
        except (ValueError,KeyError,TypeError) as error:raise HTTPException(409,str(error))
        return {**payload,'protocol_context':context,'protocol_reference_hash':context_sha,
            'protocol_effective_window':window,'knowledge_cutoff':cutoff.isoformat(),
            'gaps':payload['gaps']+window['gaps'],'evidence_kind':'METHOD_CASE' if context['protocol_evidence_kind']=='METHOD_CASE' else 'REAL_ARCHIVED_SOURCE_ASSESSMENT'}

    def assess_obligations(self,plan_id,command):
        plan=self.prospective.plan(plan_id)
        if plan['instrument']!='SSE:600362':raise HTTPException(403,'已知现金义务审计仅适配SSE:600362')
        cutoff=datetime.fromisoformat(now())
        value={'audit_id':str(uuid4()),'plan_id':plan_id,'protocol_id':command.protocol_id,
            'instrument':plan['instrument'],'basis':command.basis,'normalized_known_at':cutoff.isoformat(),
            'parser_fingerprint':code(),**self.obligation_payload(command.protocol_id,plan['instrument'],cutoff,True)}
        value['archive']=self.evidence.archive(encode(value).encode(),'KNOWN_OBLIGATION_AUDIT',evidence_kind=value['evidence_kind'])
        with self.ledger.connection() as db:db.execute('INSERT INTO post_close_obligation_audits VALUES(?,?,?,?)',
            (value['audit_id'],plan_id,command.protocol_id,encode(value)))
        return value

    def obligations(self,plan_id,cutoff=None,protocol_id=None,ids=None,checkpoint_day=None):
        cutoff=cutoff or datetime.fromisoformat(now())
        self.prospective.plan(plan_id)
        with self.ledger.connection() as db:
            saved=[json.loads(r[0]) for r in db.execute('SELECT value FROM post_close_obligation_audits WHERE plan_id=? ORDER BY rowid',(plan_id,))]
        selected=[s for s in saved if datetime.fromisoformat(s['normalized_known_at'])<=cutoff and
            (protocol_id is None or s['protocol_id']==protocol_id) and
            (checkpoint_day is None or s['protocol_effective_window']['start_date']==checkpoint_day)]
        if ids is not None:
            by_id={s['audit_id']:s for s in selected}
            if len(set(ids))!=len(ids) or any(i not in by_id for i in ids):raise HTTPException(409,'KNOWN_OBLIGATION_AUDIT_MISSING')
            selected=[by_id[i] for i in ids]
        for value in selected:
            original=json.loads(self.evidence.raw(value['archive']['sha256']).read_bytes())
            if original!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'KNOWN_OBLIGATION_AUDIT_ARCHIVE_MISMATCH')
            if value['parser_fingerprint']!=code():raise HTTPException(409,'POST_CLOSE_PARSER_CHANGED_SUCCESSOR_REQUIRED')
            computed=self.obligation_payload(value['protocol_id'],value['instrument'],datetime.fromisoformat(value['knowledge_cutoff']))
            if any(value[k]!=v for k,v in computed.items()):raise HTTPException(409,'KNOWN_OBLIGATION_NORMALIZED_ORIGINAL_MISMATCH')
        return selected

    def capture_suspension(self,plan_id,basis):
        plan=self.prospective.plan(plan_id)
        if plan['instrument']!='SSE:600362':raise HTTPException(403,'SSE停牌指定日期原件仅适配SSE:600362')
        started=now();day=datetime.fromisoformat(started).astimezone(SHANGHAI).date().isoformat()
        try:contract=sse_suspension.schema()
        except (ValueError,KeyError,TypeError) as error:raise HTTPException(409,str(error))
        if datetime.fromisoformat(contract['js_source']['received_at'])>datetime.fromisoformat(started):
            raise HTTPException(409,'SSE_SUSPENSION_QUERY_JS_AFTER_CAPTURE')
        self.evidence.archive(contract['js_bytes'],'SSE_SUSPENSION_QUERY_JS',source_url=contract['js_source']['url'],
            received_at=contract['js_source']['received_at'])
        self.evidence.archive(contract['mapping_bytes'],'SSE_SUSPENSION_SCHEMA_MAPPING')
        value={'receipt_id':str(uuid4()),'plan_id':plan_id,'instrument':plan['instrument'],'query_date':day,
            'basis':basis,'started_at':started,'source_id':sse_suspension.SOURCE,'request_budget_pages':2,
            'parser_fingerprint':code(),'query_js_hash':sse_suspension.JS_SHA,'schema_mapping_hash':contract['mapping_hash'],
            'evidence_kind':'METHOD_CASE' if self.evidence.evidence_kind=='METHOD_CASE' else 'REAL_SOURCE_ASSESSMENT',
            'network_calls':0,'pages':[],'errors':[],'system_usable':False,'complete_status_verified':False,
            'no_event_authority':False,'actual_forward_start':False,'forward_started_at':None,'capability':'NOT_GRANTED'}
        raw=[]
        try:
            blocked=self.prospective.sources.access(sse_suspension.SOURCE,plan['instrument'])
            if blocked:raise ValueError(blocked)
            with httpx.Client(transport=self.evidence.transport,follow_redirects=False,timeout=15) as client:
                for page_no in range(1,3):
                    params=sse_suspension.parameters(contract,day,page_no)
                    value['network_calls']+=1
                    with client.stream('GET',contract['url'],params=params,headers={'Referer':'https://www.sse.com.cn/'}) as response:
                        body=bytearray();truncated=False
                        for part in response.iter_bytes():
                            remaining=8*1024*1024-len(body);body.extend(part[:remaining])
                            if len(part)>remaining:truncated=True;break
                        received=now()
                        archive=self.evidence.archive(bytes(body),'SSE_SUSPENSION_RAW_RESPONSE',source_id=sse_suspension.SOURCE,
                            source_url=str(response.url),received_at=received,status_code=response.status_code,
                            content_type=response.headers.get('content-type'),parameters=params,receipt_id=value['receipt_id'],
                            evidence_kind=value['evidence_kind'],original_complete=not truncated)
                        value['pages'].append({'parameters':params,'archive':archive,
                            'original_complete':not truncated,'reported_metadata':sse_suspension.reported_metadata(bytes(body))})
                        if truncated:raise ValueError('SSE_SUSPENSION_DECODED_BYTE_LIMIT_PREFIX_ONLY')
                        response.raise_for_status()
                    raw.append({'content':bytes(body),'parameters':params,'archive':archive})
                    parsed=sse_suspension.parse_pages(raw,plan['instrument'],day,received)
                    if not parsed['declared_total'] or parsed['reported_page_count']<=page_no:break
        except (httpx.HTTPError,ValueError,KeyError,TypeError) as error:
            value['errors'].append(str(error)[:160] if isinstance(error,ValueError) else type(error).__name__)
        value['finished_at']=now();value['normalized_known_at']=value['finished_at']
        if value['errors']:
            parsed={'events':[],'page_audits':[],'returned_count':None,'declared_total':None,
                'reported_page_count':None,'returned_count_matches_positive_total':False,
                'gaps':['SSE_SUSPENSION_CAPTURE_OR_PARSE_REFUSED']+value['errors']}
        else:parsed=sse_suspension.parse_pages(raw,plan['instrument'],day,value['normalized_known_at'])
        value.update(parsed,status='REFUSED' if value['errors'] else 'REPORTED_PARTIAL')
        value['archive']=self.evidence.archive(encode(value).encode(),'SSE_SUSPENSION_RECEIPT',evidence_kind=value['evidence_kind'])
        with self.ledger.connection() as db:db.execute('INSERT INTO post_close_suspension_receipts VALUES(?,?,?,?)',
            (value['receipt_id'],plan_id,day,encode(value)))
        self.prospective.sources.outcome(sse_suspension.SOURCE,not value['errors'],value['status'],value['receipt_id'])
        return value

    def suspension_receipts(self,plan_id,cutoff=None,ids=None):
        self.prospective.plan(plan_id);cutoff=cutoff or datetime.fromisoformat(now())
        with self.ledger.connection() as db:
            saved=[json.loads(r[0]) for r in db.execute('SELECT value FROM post_close_suspension_receipts WHERE plan_id=? ORDER BY rowid',(plan_id,))]
        selected=[s for s in saved if datetime.fromisoformat(s['normalized_known_at'])<=cutoff]
        if ids is not None:
            available={s['receipt_id']:s for s in selected}
            if len(set(ids))!=len(ids) or any(i not in available for i in ids):raise HTTPException(409,'SSE_SUSPENSION_RECEIPT_MISSING')
            selected=[available[i] for i in ids]
        for value in selected:
            original=json.loads(self.evidence.raw(value['archive']['sha256']).read_bytes())
            if original!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'SSE_SUSPENSION_RECEIPT_ORIGINAL_MISMATCH')
            if value['parser_fingerprint']!=code():raise HTTPException(409,'POST_CLOSE_PARSER_CHANGED_SUCCESSOR_REQUIRED')
            try:contract=sse_suspension.schema()
            except (ValueError,KeyError,TypeError) as error:raise HTTPException(409,str(error))
            if value['query_js_hash']!=sse_suspension.JS_SHA or value['schema_mapping_hash']!=contract['mapping_hash']:
                raise HTTPException(409,'SSE_SUSPENSION_SCHEMA_DEPENDENCY_MISMATCH')
            self.evidence.raw(value['query_js_hash']);self.evidence.raw(value['schema_mapping_hash'])
            raw=[{'content':self.evidence.raw(p['archive']['sha256']).read_bytes(),**p} for p in value['pages']]
            for ordinal,page in enumerate(raw,1):
                source_url=urlparse(page['archive']['source_url'])
                if (page['reported_metadata']!=sse_suspension.reported_metadata(page['content']) or
                    page['parameters']!=sse_suspension.parameters(contract,value['query_date'],ordinal) or
                    source_url._replace(query='').geturl()!=contract['url'] or
                    {k:v[0] for k,v in parse_qs(source_url.query).items()}!=page['parameters']):
                    raise HTTPException(409,'SSE_SUSPENSION_REQUEST_OR_REPORTED_METADATA_MISMATCH')
            if not value['errors']:
                try:parsed=sse_suspension.parse_pages(raw,value['instrument'],value['query_date'],value['normalized_known_at'])
                except (ValueError,KeyError,TypeError):raise HTTPException(409,'SSE_SUSPENSION_ORIGINAL_PARSE_FAILED')
                if any(value[k]!=v for k,v in parsed.items()):raise HTTPException(409,'SSE_SUSPENSION_NORMALIZED_ORIGINAL_MISMATCH')
        return selected

    def suspension_jobs(self,plan_id):
        self.prospective.plan(plan_id)
        with self.ledger.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT value FROM post_close_suspension_jobs WHERE plan_id=? ORDER BY rowid',(plan_id,))]

    def capture_suspension_once(self,plan_id,basis):
        self.prospective.plan(plan_id);day=datetime.fromisoformat(now()).astimezone(SHANGHAI).date().isoformat()
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT value FROM post_close_suspension_jobs WHERE plan_id=? AND day=?',(plan_id,day)).fetchone()
            if old:return json.loads(old[0])
            job={'plan_id':plan_id,'day':day,'source_id':sse_suspension.SOURCE,'state':'CLAIMED',
                'basis':basis,'started_at':now(),'actual_forward_start':False,'request_budget_pages':2,
                'host_owner':{'pid':os.getpid(),'creation_ticks':process_creation(os.getpid())}}
            db.execute('INSERT INTO post_close_suspension_jobs VALUES(?,?,?)',(plan_id,day,encode(job)))
            db.commit()
        try:
            receipt=self.capture_suspension(plan_id,basis)
            job.update(state='RECORDED',receipt_id=receipt['receipt_id'],gaps=receipt['gaps'],finished_at=now())
        except HTTPException as error:job.update(state='REFUSED',gaps=[str(error.detail)],finished_at=now())
        with self.ledger.connection() as db:db.execute('UPDATE post_close_suspension_jobs SET value=? WHERE plan_id=? AND day=?',
            (encode(job),plan_id,day))
        return job

    def capture_once(self,plan_id,basis='Registered forward plan; existing single worker source acquisition'):
        """One existing worker owns a persisted bounded job; failures are not hidden retries."""
        self.prospective.plan(plan_id)
        day=datetime.fromisoformat(now()).astimezone(SHANGHAI).date().isoformat()
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT value FROM post_close_capture_jobs WHERE plan_id=? AND day=?',(plan_id,day)).fetchone()
            if old:return json.loads(old[0])
            job={'plan_id':plan_id,'day':day,'started_at':now(),'state':'CLAIMED','actual_forward_start':False,
                'host_owner':{'pid':os.getpid(),'creation_ticks':process_creation(os.getpid())},'basis':basis}
            db.execute('INSERT INTO post_close_capture_jobs VALUES(?,?,?)',(plan_id,day,encode(job)))
            db.commit()
        try:
            stock_job=self.stock_suspensions.capture_once(plan_id,basis)
            job.update(stock_suspension_receipt_id=stock_job.get('receipt_id'),stock_suspension_job_state=stock_job['state'])
            status_job=self.capture_suspension_once(plan_id,basis)
            job.update(suspension_receipt_id=status_job.get('receipt_id'),suspension_job_state=status_job['state'])
            packet=self.capture(plan_id,basis)
            job.update(state='RECORDED',packet_id=packet['packet_id'],gaps=sorted(set(packet['gaps']+status_job.get('gaps',[])+stock_job.get('gaps',[]))),finished_at=now())
        except HTTPException as error:
            job.update(state='REFUSED',gaps=[str(error.detail)],finished_at=now())
        with self.ledger.connection() as db:
            db.execute('UPDATE post_close_capture_jobs SET value=? WHERE plan_id=? AND day=?',(encode(job),plan_id,day))
        return job

    def cash_inventory(self,cutoff,register=False,verify_archives=False):
        """Existing mapped implementation notices; neither current coverage nor account receipts."""
        body=(CASH_REFERENCE/'sources.json').read_bytes()
        manifest=json.loads(body)
        mapping_hash=hashlib.sha256(body).hexdigest()
        if register:self.evidence.archive(body,'CASH_SOURCE_MAPPING',source_id='cninfo-known-cash-reference')
        if verify_archives:self.evidence.raw(mapping_hash)
        events=[]
        for event in manifest['events']:
            source=event['source']
            if datetime.fromisoformat(source['received_at'])>cutoff:continue
            raw=(CASH_REFERENCE/source['file']).read_bytes()
            if len(raw)!=source['bytes'] or hashlib.sha256(raw).hexdigest()!=source['sha256']:
                raise HTTPException(409,'CASH_IMPLEMENTATION_ORIGINAL_CORRUPT')
            if register:
                self.evidence.archive(raw,'CASH_IMPLEMENTATION_ORIGINAL','pdf',source_id='cninfo-known-cash-reference',
                    source_url=source['url'],received_at=source['received_at'],evidence_kind='REAL_ARCHIVED_SOURCE_ASSESSMENT')
            if verify_archives:self.evidence.raw(source['sha256'])
            events.append({k:v for k,v in event.items() if k!='extracted_pages'}|{
                'event_identity':source['url'].rsplit('/',1)[-1].split('.')[0],
                'lifecycle_stage':'IMPLEMENTATION_NOTICE','actual_account_receipt':None,
                'available_at':source['received_at'],'field_mapping_hash':mapping_hash,
                'field_source_locator':source['fact_pdf_pages'],
                'coverage_claim':'KNOWN_PUBLISHED_CASH_ONLY_NOT_CURRENT_COMPLETE_ACTION_INVENTORY'})
        return {'instrument':manifest['instrument'],'events':events,'mapping_hash':mapping_hash,
            'scope':manifest['scope'],'complete_action_coverage':False,'covered_effective_interval':None,
            'pending_older_obligations_complete':False,'pagination_and_revision_coverage':'NOT_PROVEN',
            'unknown_categories':['LISTING_RELISTING','BONUS_TRANSFER_SPLIT','ALLOTMENT_LIFECYCLE',
                'CANCELLATION_SUPERSESSION','CURRENT_EX_RIGHTS','CURRENT_NO_EVENT_AUTHORITY']}

    def capture(self,plan_id,basis):
        plan=self.prospective.plan(plan_id)
        instant=datetime.fromisoformat(now()).astimezone(SHANGHAI)
        day=instant.date().isoformat()
        if plan['instrument']!='SSE:600362':raise HTTPException(403,'盘后原件采集仅适配 SSE:600362')
        request=self.evidence.request(DataRequest(instruments=[plan['instrument']],groups=['DAILY','STATUS'],
            purpose='RESEARCH',start_date=instant.date(),end_date=instant.date(),timeout_seconds=15,max_calls=1))
        request.update(collection_plan_id=plan_id,collection_engine='SSE_POST_CLOSE',collection_source_id=SOURCE)
        run={'run_id':str(uuid4()),'request_id':request['request_id'],'backend':'SSE_POST_CLOSE',
            'status':'RUNNING','started_at':now(),'evidence_kind':self.evidence.evidence_kind,
            'parser_fingerprint':code(),'tools':[],'gaps':[],'network_calls':0}
        run['host_owner']={'pid':os.getpid(),'creation_ticks':process_creation(os.getpid())}
        with self.ledger.connection() as db:
            db.execute('UPDATE data_requests SET value=? WHERE id=?',(encode(request),request['request_id']))
            db.execute('INSERT INTO retrieval_runs VALUES(?,?,?)',(run['run_id'],request['request_id'],encode(run)))
        facts,archives=[],[]
        blocked=self.prospective.sources.access(SOURCE,plan['instrument'])
        calendar=self.evidence.market.rules.calendar('SSE',instant.date(),instant)
        if calendar['is_trading_day'] is not True:blocked='NOT_A_KNOWN_TRADING_DAY'
        if instant.time().isoformat()<'15:05:00':blocked='POST_CLOSE_CHECKPOINT_NOT_REACHED'
        if blocked:run['gaps'].append({'code':blocked,'source_id':SOURCE})
        else:
            try:
                policy=self.prospective.sources.policy(SOURCE)
                run['network_calls']=1
                with httpx.Client(transport=self.evidence.transport,follow_redirects=False,timeout=15) as client:
                    with client.stream('GET',SSE_URL,params=SSE_PARAMS,headers={'Referer':'https://www.sse.com.cn/'}) as response:
                        response.raise_for_status()
                        body=bytearray()
                        for part in response.iter_bytes():
                            body.extend(part)
                            if len(body)>policy['max_bytes']:raise ValueError('SSE_DECODED_BYTE_LIMIT')
                        received=now()
                        archive=self.evidence.archive(bytes(body),'RAW_RESPONSE',source_id=SOURCE,
                            source_url=str(response.url),received_at=received,evidence_kind=self.evidence.evidence_kind,
                            status_code=response.status_code,content_type=response.headers.get('content-type'),
                            request_id=request['request_id'],run_id=run['run_id'],parameters=SSE_PARAMS)
                        archives.append(archive)
                        run['tools'].append({'source_id':SOURCE,'raw_hash':archive['sha256'],'received_at':received})
                        self.ledger.crash_point('post_close_after_raw')
                facts=closing_facts(bytes(body),archive,plan['instrument'],day)
                self.prospective.sources.outcome(SOURCE,True,'CLOSED_PARTIAL_FACTS_ACQUIRED',run['run_id'])
            except (httpx.HTTPError,ValueError,KeyError,TypeError) as error:
                run['gaps'].append({'code':str(error)[:160] if isinstance(error,ValueError) else type(error).__name__,'source_id':SOURCE})
                self.prospective.sources.outcome(SOURCE,False,type(error).__name__,run['run_id'])
        buffer=BytesIO()
        pq.write_table(pa.Table.from_pylist([{'payload':encode(f)} for f in facts],
            schema=pa.schema([pa.field('payload',pa.string())])),buffer)
        parquet=self.evidence.archive(buffer.getvalue(),'NORMALIZED_PARQUET','parquet',adapter_version=VERSION)
        snapshot={'snapshot_id':str(uuid4()),'run_id':run['run_id'],'request_id':request['request_id'],
            'facts':facts,'archives':archives,'parquet':parquet,'coverage':[{'instrument':plan['instrument'],
            'source_id':SOURCE,'trade_date':day,'complete_status':False,'complete_actions':False}],
            'observations':[],'gaps':run['gaps'],'created_at':now(),'evidence_kind':self.evidence.evidence_kind,
            'namespace':'PROSPECTIVE','adapter_version':VERSION,'parser_fingerprint':code()}
        run.update(status='PARTIAL' if facts else 'FAILED',snapshot_id=snapshot['snapshot_id'],finished_at=now(),
            basis=basis)
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO market_evidence_snapshots VALUES(?,?,?)',(snapshot['snapshot_id'],run['run_id'],encode(snapshot)))
            db.execute('UPDATE retrieval_runs SET value=? WHERE id=?',(encode(run),run['run_id']))
            self.ledger.crash_point('post_close_before_snapshot_commit')
            db.commit()
        self.prospective.record(plan_id,run['run_id'])
        return self.build(plan_id,basis)

    @staticmethod
    def verify_snapshot(evidence,run,snapshot):
        if run['parser_fingerprint']!=snapshot.get('parser_fingerprint') or snapshot.get('parser_fingerprint')!=code():
            raise HTTPException(409,'POST_CLOSE_PARSER_CHANGED_SUCCESSOR_REQUIRED')
        if snapshot['facts']:
            if len(snapshot['archives'])!=1:raise HTTPException(409,'POST_CLOSE_ORIGINAL_BINDING_MISMATCH')
            archive=snapshot['archives'][0]
            request=evidence.get('data_requests',run['request_id'])
            try: computed=closing_facts(evidence.raw(archive['sha256']).read_bytes(),archive,
                request['instruments'][0],request['end_date'])
            except (ValueError,KeyError,TypeError):raise HTTPException(409,'POST_CLOSE_ORIGINAL_PARSE_FAILED')
            if computed!=snapshot['facts']:raise HTTPException(409,'POST_CLOSE_NORMALIZED_ORIGINAL_MISMATCH')

    def acquisitions(self,plan_id,cutoff,batch_ids=None):
        """Original completed batch receipts, including failed zero-fact acquisitions."""
        plan=self.prospective.plan(plan_id)
        batches=[b for b in self.prospective.batches(plan_id) if datetime.fromisoformat(b['known_at'])<=cutoff]
        if batch_ids is not None:
            available={b['batch_id']:b for b in batches}
            if len(set(batch_ids))!=len(batch_ids) or any(i not in available for i in batch_ids):
                raise HTTPException(409,'POST_CLOSE_ORIGINAL_ACQUISITION_MISSING')
            batches=[available[i] for i in batch_ids]
        result=[]
        for batch in batches:
            run=self.evidence.get('retrieval_runs',batch['run_id'])
            request=self.evidence.get('data_requests',run['request_id'])
            if (request['instruments']!=[plan['instrument']] or request['purpose']!='RESEARCH' or
                batch['snapshot_id']!=run.get('snapshot_id') or batch['status']!=run['status'] or
                batch['gaps']!=run.get('gaps',[]) or datetime.fromisoformat(run['finished_at'])>datetime.fromisoformat(batch['known_at'])):
                raise HTTPException(409,'POST_CLOSE_ACQUISITION_RUN_BINDING_MISMATCH')
            originals=[]
            if run.get('snapshot_id'):
                self.evidence.replay(run['run_id'])
                snapshot=self.evidence.get('market_evidence_snapshots',run['snapshot_id'])
                if snapshot['run_id']!=run['run_id'] or snapshot['request_id']!=run['request_id']:
                    raise HTTPException(409,'POST_CLOSE_ACQUISITION_SNAPSHOT_BINDING_MISMATCH')
                originals=[a['sha256'] for a in snapshot['archives']]
            for tool in run.get('tools',[]):
                if tool.get('raw_hash'):
                    self.evidence.raw(tool['raw_hash'])
                    originals.append(tool['raw_hash'])
            result.append({**batch,'request_id':run['request_id'],
                'source_id':request.get('collection_source_id'),'source_day':request.get('end_date'),
                'original_raw_hashes':sorted(set(originals))})
        return result

    def inputs(self,versions,instrument,cutoff,acquisition_attempts=(),obligation_audits=(),suspension_receipts=(),stock_receipts=()):
        daily,statuses={},{}
        inventory=self.cash_inventory(cutoff)
        gaps=[]
        latest={}
        current_day=cutoff.astimezone(SHANGHAI).date().isoformat()
        applicable_audits=[a for a in obligation_audits if a['instrument']==instrument and
            a['protocol_effective_window']['start_date']==current_day]
        applicable_suspension=[s for s in suspension_receipts if s['instrument']==instrument and s['query_date']==current_day]
        applicable_stock=[s for s in stock_receipts if s['instrument']==instrument and s['host_date']==current_day]
        for receipt in applicable_stock:
            gaps.extend(receipt['gaps'])
            for event in receipt['events']:
                statuses.setdefault(current_day,[]).append({**event,'stock_receipt_id':receipt['receipt_id'],'parser_fingerprint':code()})
        for receipt in applicable_suspension:
            gaps.extend(receipt['gaps'])
            for event in receipt['events']:
                statuses.setdefault(current_day,[]).append({**event,'receipt_id':receipt['receipt_id'],'parser_fingerprint':code()})
        for attempt in acquisition_attempts:
            if attempt['source_id']==SOURCE and attempt['source_day']==current_day:
                latest[(attempt['source_id'],attempt['source_day'])]=attempt
        # Preserve old failures in the packet without making a later successful correction fail.
        for attempt in latest.values():
            if attempt['status'] in {'FAILED','INTERRUPTED'}:
                gaps.extend('SOURCE_ACQUISITION_FAILURE:'+SOURCE+':'+str(g['code']) for g in attempt['gaps'])
        for version in versions:
            fact=version['fact'];day=fact.get('trade_date')
            if fact.get('instrument')!=instrument or not day:continue
            for stamp in ['received_at','available_at']:
                try:
                    value=datetime.fromisoformat(fact[stamp])
                    if value.tzinfo is None or value>cutoff:raise ValueError()
                except (KeyError,ValueError,TypeError):gaps.append('CURRENT_DEPENDENCY_NOT_AVAILABLE:'+day)
            self.evidence.raw(fact['raw_hash'])
            if fact['group']=='DAILY':daily.setdefault(day,[]).append({**fact,'known_at':version['known_at']})
            if fact['group']=='STATUS':statuses.setdefault(day,[]).append(fact)
        rows=[]
        for day,candidates in sorted(daily.items()):
            # Source selection never clears a conflict, including quantity/amount precision/scope.
            fields=['open','high','low','close','volume_shares','amount_yuan','adjustment','volume_unit',
                'source_volume_unit','source_amount_unit','amount_precision_yuan','turnover_scope']
            if any(any(differs(c.get(k),candidates[0].get(k),k) for k in fields) for c in candidates[1:]):
                gaps.append('UNRESOLVED_CURRENT_DAILY_CONFLICT:'+day)
            row=max(candidates,key=lambda c:datetime.fromisoformat(c['known_at']))
            row={**row,'known_obligation_audit_ids':[a['audit_id'] for a in applicable_audits],
                'suspension_receipt_ids':[s['receipt_id'] for s in applicable_suspension],
                'stock_suspension_receipt_ids':[s['receipt_id'] for s in applicable_stock]}
            if any(a['resolution_unknown_count'] for a in applicable_audits):
                gaps.append('KNOWN_OLDER_OBLIGATION_RESOLUTION_UNPROVEN:'+day)
            states=statuses.get(day,[])
            dims=['suspension','risk_warning','st_subtype','listing_stage','ex_rights','state']
            if any(any(s.get(k)!=states[0].get(k) for k in dims) for s in states[1:]):
                gaps.append('UNRESOLVED_CURRENT_STATUS_CONFLICT:'+day)
            # A caller's complete-status boolean is never source authority.
            if not states:gaps.append('CURRENT_COMPLETE_STATUS_UNPROVEN:'+day)
            for state in states:
                sources=state.get('field_evidence',{})
                if state.get('source_id')==sse_stock_suspension.SOURCE:
                    if state.get('stock_receipt_id') not in [s['receipt_id'] for s in applicable_stock] or state.get('query_js_hash')!=sse_suspension.JS_SHA:
                        gaps.append('CURRENT_STATUS_FIELD_SOURCE_UNPROVEN:'+day)
                    gaps.append('CURRENT_STOCK_INTERVAL_ACTUAL_STATUS_UNPROVEN:'+day)
                    continue
                if state.get('source_id')==sse_suspension.SOURCE:
                    if (state.get('receipt_id') not in [s['receipt_id'] for s in applicable_suspension] or
                        sources.get('suspension',{}).get('raw_hash')!=state['raw_hash'] or
                        state.get('query_js_hash')!=sse_suspension.JS_SHA):
                        gaps.append('CURRENT_STATUS_FIELD_SOURCE_UNPROVEN:'+day)
                    gaps.append('CURRENT_SUSPENSION_SOURCE_OTHER_STATUS_DIMENSIONS_UNPROVEN:'+day)
                    continue
                if (state.get('source_id')!=SOURCE or state.get('parser_fingerprint')!=code() or
                    any(sources.get(k,{}).get('raw_hash')!=state['raw_hash'] for k in ['suspension','risk_warning'])):
                    gaps.append('CURRENT_STATUS_FIELD_SOURCE_UNPROVEN:'+day)
            if not states or any(s.get('listing_stage')!='ORDINARY' for s in states):gaps.append('CURRENT_LISTING_STAGE_UNPROVEN:'+day)
            if not states or any(s.get('ex_rights') is not False for s in states):gaps.append('CURRENT_EX_RIGHTS_UNPROVEN:'+day)
            if any(s.get('suspension') is not False or s.get('risk_warning') is not False for s in states):
                gaps.append('CURRENT_ORDINARY_TRADING_STATUS_UNPROVEN:'+day)
            # Currently adapted board/quote/status sources do not certify listing or active action coverage.
            if not inventory['complete_action_coverage']:gaps.append('CURRENT_ACTION_COVERAGE_UNPROVEN:'+day)
            if row.get('volume_unit')!='SHARE' or row.get('amount_yuan') is None or row.get('turnover_scope')=='UNKNOWN':
                gaps.append('CLOSING_VOLUME_AMOUNT_UNIT_AND_TURNOVER_SCOPE_UNVERIFIED:'+day)
            if row.get('completion_state')!='COMPLETE_REPORTED_HISTORICAL' or not row.get('model_daily_input_allowed'):
                gaps.append('CURRENT_DAILY_COMPLETENESS_UNPROVEN:'+day)
            for event in row.get('cash_events_effective',[]):
                source=event.get('source',{});sha=source.get('sha256')
                if sha:self.evidence.raw(sha)
                if (not sha or event.get('ex_date')!=day or not event.get('record_date') or
                    not event.get('cash_payment_date') or event.get('lifecycle_stage')!='IMPLEMENTATION_NOTICE'):
                    gaps.append('CURRENT_CASH_LIFECYCLE_UNPROVEN:'+day)
                matches=[e for e in inventory['events'] if e['source']['sha256']==sha]
                required=['instrument','record_date','ex_date','cash_payment_date','gross_cash_yuan_per_eligible_share',
                    'differentiated_ex_reference_deduction_yuan_per_listed_share','tax_withholding_at_payment_pct']
                if len(matches)!=1 or any(event.get(k)!=matches[0].get(k) for k in required) or event.get('field_mapping_hash')!=inventory['mapping_hash']:
                    gaps.append('CURRENT_CASH_SOURCE_FACT_BINDING_UNPROVEN:'+day)
                for stamp in [event.get('available_at'),source.get('received_at')]:
                    try:
                        value=datetime.fromisoformat(stamp)
                        if value.tzinfo is None or value>cutoff:raise ValueError()
                    except (ValueError,TypeError):gaps.append('CURRENT_CASH_NOT_AVAILABLE:'+day)
            rows.append({**row,'execution_evidence':{**row.get('execution_evidence',{}),
                'state':'UNKNOWN','status_raw_hashes':[s['raw_hash'] for s in states],
                'company_actions':'UNKNOWN','input_packet_version':VERSION}})
        if not rows:gaps.append('CURRENT_COMPLETE_DAILY_MISSING')
        if any(v['evidence_kind']!='REAL_ACQUISITION' for v in versions):gaps.append('SYNTHETIC_PROSPECTIVE_INPUT_CANNOT_START_REAL_CLOCK')
        return rows,sorted(set(gaps)),[s for day in sorted(statuses) for s in statuses[day]]

    def execution_context(self,instrument,rows):
        listing=self.evidence.market.listing()
        identity=next((m['identity'] for m in listing['members'] if m['instrument']==instrument),{})
        result=[]
        for row in rows:
            rule=self.evidence.market.rules.rule(identity.get('exchange'),identity.get('board'),
                identity.get('instrument_type'),on=date.fromisoformat(row['trade_date']))
            source=rule.get('source')
            if source:
                path=self.evidence.directory/source['archive_path']
                if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:
                    raise HTTPException(409,'POST_CLOSE_EXECUTION_RULE_SOURCE_CORRUPT')
            result.append({'instrument':instrument,'trade_date':row['trade_date'],
                'identity_revision':identity.get('revision'),'rule':rule,
                'source_bound_dependencies':{'daily_raw_hash':row['raw_hash'],
                    'status_raw_hashes':row['execution_evidence']['status_raw_hashes']},
                'company_action_treatment':'UNPROVEN_CURRENT_COVERAGE',
                'commission_slippage':'CONSUMER_FROZEN_SCENARIO_REQUIRED','cash_account_receipts_inferred':False})
        return result

    def build(self,plan_id,basis,cutoff=None):
        plan=self.prospective.plan(plan_id)
        cutoff=cutoff or datetime.fromisoformat(now())
        inventory=self.cash_inventory(cutoff,register=True)
        versions=self.prospective.as_of(plan_id,cutoff)['versions']
        attempts=self.acquisitions(plan_id,cutoff)
        audits=self.obligations(plan_id,cutoff,checkpoint_day=cutoff.astimezone(SHANGHAI).date().isoformat())
        suspension=self.suspension_receipts(plan_id,cutoff)
        stock=self.stock_suspensions.receipts(plan_id,cutoff)
        rows,gaps,statuses=self.inputs(versions,plan['instrument'],cutoff,attempts,audits,suspension,stock)
        value={'packet_id':str(uuid4()),'plan_id':plan_id,'instrument':plan['instrument'],
            'created_at':now(),'knowledge_cutoff':cutoff.isoformat(),'basis':basis,'parser_fingerprint':code(),
            'rows':rows,'status_facts':statuses,'gaps':gaps,'versions':versions,'acquisition_attempts':attempts,
            'evidence_kind':'REAL_ACQUISITION' if versions and all(v['evidence_kind']=='REAL_ACQUISITION' for v in versions) else 'METHOD_CASE' if versions else 'NO_ACQUIRED_INPUT',
            'forward_admissible':bool(rows) and not gaps,'capability':'NOT_GRANTED','forward_started_at':None,
            'historical_pit_claim':False,'account_events_added':0}
        value['known_cash_inventory']=inventory
        value['known_obligation_audits']=audits
        value['suspension_receipts']=suspension
        value['stock_suspension_receipts']=stock
        value['historical_source_assessments']=self.history(plan_id,cutoff)
        value['execution_context']=self.execution_context(plan['instrument'],rows)
        value['archive']=self.evidence.archive(encode(value).encode(),'POST_CLOSE_INPUT_PACKET',evidence_kind=value['evidence_kind'])
        with self.ledger.connection() as db:db.execute('INSERT INTO post_close_packets VALUES(?,?,?)',(value['packet_id'],plan_id,encode(value)))
        return value

    def replay(self,packet_id):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM post_close_packets WHERE id=?',(packet_id,)).fetchone()
        if not row:raise HTTPException(404,'盘后输入包不存在')
        packet=json.loads(row[0])
        original=json.loads(self.evidence.raw(packet['archive']['sha256']).read_bytes())
        if original!={k:v for k,v in packet.items() if k!='archive'}:raise HTTPException(409,'POST_CLOSE_PACKET_ARCHIVE_MISMATCH')
        if packet['parser_fingerprint']!=code():raise HTTPException(409,'POST_CLOSE_PARSER_CHANGED_SUCCESSOR_REQUIRED')
        for context in packet['execution_context']:
            source=context['rule'].get('source')
            if source:
                path=self.evidence.directory/source['archive_path']
                if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:
                    raise HTTPException(409,'POST_CLOSE_EXECUTION_RULE_SOURCE_CORRUPT')
        cutoff=datetime.fromisoformat(packet['knowledge_cutoff'])
        versions=self.prospective.replay_versions(packet['plan_id'],packet['versions'],cutoff)
        attempts=self.acquisitions(packet['plan_id'],cutoff,[a['batch_id'] for a in packet['acquisition_attempts']])
        if attempts!=packet['acquisition_attempts']:raise HTTPException(409,'POST_CLOSE_PACKET_ACQUISITION_BINDING_MISMATCH')
        audits=self.obligations(packet['plan_id'],cutoff,ids=[a['audit_id'] for a in packet['known_obligation_audits']],
            checkpoint_day=cutoff.astimezone(SHANGHAI).date().isoformat())
        suspension=self.suspension_receipts(packet['plan_id'],cutoff,ids=[s['receipt_id'] for s in packet['suspension_receipts']])
        stock=self.stock_suspensions.receipts(packet['plan_id'],cutoff,ids=[s['receipt_id'] for s in packet['stock_suspension_receipts']])
        rows,gaps,statuses=self.inputs(versions,packet['instrument'],cutoff,attempts,audits,suspension,stock)
        inventory=self.cash_inventory(cutoff,verify_archives=True)
        history=self.history(packet['plan_id'],cutoff,[s['assessment_id'] for s in packet['historical_source_assessments']])
        return {'packet_id':packet_id,'matches_original':rows==packet['rows'] and gaps==packet['gaps'] and statuses==packet['status_facts'] and inventory==packet['known_cash_inventory'] and history==packet['historical_source_assessments'] and audits==packet['known_obligation_audits'] and suspension==packet['suspension_receipts'] and stock==packet['stock_suspension_receipts'],
            'network_calls':0,'forward_admissible':packet['forward_admissible'],'capability':'NOT_GRANTED'}
