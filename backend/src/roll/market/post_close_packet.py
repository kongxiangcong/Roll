"""Bounded SSE originals and source-bound post-close input packets.

An exchange timestamp establishes what this response says, not its unit/session
coverage. Missing listing/action authority remains a field-level gap. No HTTP
command can certify completeness or create a forward sample.
"""
import hashlib
import json
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from roll.accounts.ledger import encode, now
from roll.market.evidence import DataRequest
from roll.market.rules import SHANGHAI
from roll.agents.codex_process import owner_alive,process_creation

SSE_URL='http://yunhq.sse.com.cn:32041/v1/sh1/list/exchange/equity'
SSE_PARAMS={'select':'code,name,open,high,low,last,volume,amount,prev_close','begin':'0','end':'6000'}
SOURCE='sse-closing-board'
VERSION='source-bound-post-close-v1'
CASH_REFERENCE=Path(__file__).parents[1]/'research/reference/cash-rights'


class PacketCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    basis: str=Field(min_length=1,max_length=2000)


def code():
    return hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')+
        (CASH_REFERENCE/'sources.json').read_bytes()).hexdigest()


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
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS post_close_packets(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS post_close_capture_jobs(plan_id TEXT NOT NULL,day TEXT NOT NULL,value TEXT NOT NULL,PRIMARY KEY(plan_id,day))')
            for saved in db.execute('SELECT plan_id,day,value FROM post_close_capture_jobs'):
                job=json.loads(saved[2])
                if job['state']=='CLAIMED' and not owner_alive(job):
                    job.update(state='INTERRUPTED',finished_at=now(),gaps=['PROCESS_STOPPED_BEFORE_SOURCE_JOB_COMPLETION'])
                    db.execute('UPDATE post_close_capture_jobs SET value=? WHERE plan_id=? AND day=?',(encode(job),saved[0],saved[1]))

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
            packet=self.capture(plan_id,basis)
            job.update(state='RECORDED',packet_id=packet['packet_id'],gaps=packet['gaps'],finished_at=now())
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

    def inputs(self,versions,instrument,cutoff):
        daily,statuses={},{}
        inventory=self.cash_inventory(cutoff)
        gaps=[]
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
            states=statuses.get(day,[])
            dims=['suspension','risk_warning','st_subtype','listing_stage','ex_rights','state']
            if any(any(s.get(k)!=states[0].get(k) for k in dims) for s in states[1:]):
                gaps.append('UNRESOLVED_CURRENT_STATUS_CONFLICT:'+day)
            # A caller's complete-status boolean is never source authority.
            if not states:gaps.append('CURRENT_COMPLETE_STATUS_UNPROVEN:'+day)
            for state in states:
                sources=state.get('field_evidence',{})
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
        rows,gaps,statuses=self.inputs(versions,plan['instrument'],cutoff)
        value={'packet_id':str(uuid4()),'plan_id':plan_id,'instrument':plan['instrument'],
            'created_at':now(),'knowledge_cutoff':cutoff.isoformat(),'basis':basis,'parser_fingerprint':code(),
            'rows':rows,'status_facts':statuses,'gaps':gaps,'versions':versions,
            'evidence_kind':'REAL_ACQUISITION' if versions and all(v['evidence_kind']=='REAL_ACQUISITION' for v in versions) else 'METHOD_CASE' if versions else 'NO_ACQUIRED_INPUT',
            'forward_admissible':bool(rows) and not gaps,'capability':'NOT_GRANTED','forward_started_at':None,
            'historical_pit_claim':False,'account_events_added':0}
        value['known_cash_inventory']=inventory
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
        versions=self.prospective.as_of(packet['plan_id'],cutoff)['versions']
        if versions!=packet['versions']:raise HTTPException(409,'POST_CLOSE_PACKET_VERSION_BINDING_MISMATCH')
        rows,gaps,statuses=self.inputs(versions,packet['instrument'],cutoff)
        inventory=self.cash_inventory(cutoff,verify_archives=True)
        return {'packet_id':packet_id,'matches_original':rows==packet['rows'] and gaps==packet['gaps'] and statuses==packet['status_facts'] and inventory==packet['known_cash_inventory'],
            'network_calls':0,'forward_admissible':packet['forward_admissible'],'capability':'NOT_GRANTED'}
