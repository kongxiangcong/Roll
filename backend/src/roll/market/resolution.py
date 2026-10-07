"""Bounded source resolution; acquisition stays outside short SQLite transactions."""
import hashlib
import json
import threading
import time
from datetime import datetime, timedelta, time as day_time
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from roll.accounts.ledger import encode, now
from roll.market.directory import ScopeCommand
from roll.market.evidence import DataRequest
from roll.market.rules import SHANGHAI


class ResolutionCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    usage:Literal['PRE_MARKET_RECORD','POST_MARKET_RECORD','CURRENT_MONITORING','NEW_RISK','HISTORICAL_RESEARCH']
    knowledge_cutoff:datetime|None=None
    allow_fallback:bool=True
    use_cache:bool=True
    revision_of:str|None=None
    basis_run_id:str|None=None


def key(fact):
    return (fact['instrument'],fact['group'],fact.get('trade_date'),fact.get('adjustment'),
        fact.get('art_code'),fact.get('report_period'),fact.get('ex_date'))


def missing(fact,request):
    return [field for field in request['required_fields'] if
        ('.' not in field or field.split('.',1)[0]==fact['group']) and fact.get(field.split('.')[-1]) is None]


class SourceResolutions:
    def __init__(self,evidence,clock=None):
        self.evidence=evidence
        self.ledger=evidence.ledger
        self.slot=threading.Lock()
        self.clock=clock or now
        self.clock_basis='METHOD_CLOCK' if clock else 'ACTUAL_SYSTEM_CLOCK'
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS source_resolutions(id TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS source_revisions(id TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS evidence_dependency_invalidations(id TEXT PRIMARY KEY,target_id TEXT NOT NULL,value TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS evidence_dependency_target ON evidence_dependency_invalidations(target_id)')
            db.execute('CREATE TABLE IF NOT EXISTS source_resolution_replays(id TEXT PRIMARY KEY,value TEXT NOT NULL)')
            for row in db.execute('SELECT id,value FROM source_resolutions'):
                value=json.loads(row['value'])
                if value['status']=='RUNNING':
                    value.update(status='INTERRUPTED',finished_at=now(),reason='PROCESS_RESTART_BEFORE_RESOLUTION_COMMIT')
                    db.execute('UPDATE source_resolutions SET value=? WHERE id=?',(encode(value),row['id']))

    def save(self,value):
        with self.ledger.connection() as db:
            db.execute('INSERT OR REPLACE INTO source_resolutions VALUES(?,?)',(value['resolution_id'],encode(value)))

    def get(self,resolution_id):
        value=self.evidence.get('source_resolutions',resolution_id)
        return {**value,'dependency_status':'INVALIDATED' if self.dependencies(target_id=resolution_id) else 'CURRENT'}

    def dependencies(self,resolution_id=None,target_id=None):
        with self.ledger.connection() as db:
            rows=db.execute('SELECT value FROM evidence_dependency_invalidations'+(' WHERE target_id=?' if target_id else ''),
                (target_id,) if target_id else ())
            values=[json.loads(row[0]) for row in rows]
        return [v for v in values if not resolution_id or v['prior_resolution_id']==resolution_id]

    def history(self):
        with self.ledger.connection() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT value FROM source_resolutions ORDER BY rowid DESC LIMIT 100')]

    def start(self,request_id,command):
        request=self.evidence.get('data_requests',request_id)
        self.evidence.market.check_scope(ScopeCommand(instruments=request['instruments'],purpose=request['purpose']))
        if command.knowledge_cutoff is not None and (command.knowledge_cutoff.tzinfo is None or command.knowledge_cutoff>datetime.fromisoformat(self.clock())):
            raise HTTPException(422,'消费知识截止须带时区且不晚于现在')
        value={'resolution_id':str(uuid4()),'request_id':request_id,'command':command.model_dump(mode='json'),
            'status':'RUNNING','started_at':now(),'attempts':[],'source_checks':[],'facts':[],
            'evidence_kind':self.evidence.evidence_kind,'model_qualification':'NOT_GRANTED','formal_judgment':'DISABLED',
            'requested_instruments':request['instruments'],'requested_groups':request['groups'],'technical_limits':request['technical_limits']}
        value['request_fingerprint']=hashlib.sha256(encode({k:request.get(k) for k in
            ['instruments','groups','purpose','start_date','end_date','required_fields','daily_source','quote_source','identity_context']}|
            {'evidence_kind':self.evidence.evidence_kind}).encode()).hexdigest()
        if command.revision_of:
            prior=self.get(command.revision_of)
            if prior['status']!='COMPLETED' or prior['request_fingerprint']!=value['request_fingerprint'] or command.use_cache:
                raise HTTPException(422,'修订须关联相同请求语义的已完成记录，并显式use_cache=false')
        if command.basis_run_id:
            basis=self.evidence.get('retrieval_runs',command.basis_run_id)
            if basis['request_id']!=request_id or basis['status'] not in {'COMPLETE','PARTIAL','FAILED'}:
                raise HTTPException(422,'原运行须已结束且属于此事实请求')
        if not self.slot.acquire(blocking=False):raise HTTPException(409,{'code':'SOURCE_RESOLUTION_BUSY','max_concurrency':1})
        try:
            self.save(value)
            threading.Thread(target=self.execute,args=(value,request),daemon=True,name='roll-source-resolution').start()
        except BaseException:
            self.slot.release();raise
        return value

    def execute(self,value,request):
        started=time.monotonic()
        try:
            cached=next((r for r in self.history() if r['status']=='COMPLETED' and r.get('request_fingerprint')==value['request_fingerprint']),None)
            if cached and value['command']['use_cache'] and not self.dependencies(target_id=cached['resolution_id']):
                for attempt in cached['attempts']:self.evidence.replay(attempt['run_id'])
                value.update(attempts=[{**a,'cached':True} for a in cached['attempts']],
                    source_checks=cached['source_checks'],cache={'reused_resolution_id':cached['resolution_id'],
                        'wrapped_at':now(),'age_basis':'Original fact received_at/available_at/upstream_at, never cache wrapper time'})
                value['stop_reason']='CACHE_REUSE_END'
                self.finish(value,request,cached.get('acquired_facts',cached['facts']),0,started)
                return
            value['revision_of']=value['command']['revision_of'] or (cached['resolution_id'] if cached else None)
            basis=value['command']['basis_run_id']
            primary=self.evidence.get('retrieval_runs',basis) if basis else self.evidence.retrieve(request['request_id'])
            if basis:self.evidence.replay(basis)
            value['attempts'].append({'role':'PRIMARY','request_id':request['request_id'],'run_id':primary['run_id'],'cached':bool(basis)})
            primary_snapshot=self.evidence.get('market_evidence_snapshots',primary['snapshot_id'])
            selected=[f for f in primary_snapshot['facts'] if not f.get('errors')]
            failed_groups=[group for group in request['groups'] if any(not self.group_ready(primary_snapshot['facts'],request,instrument,group)
                for instrument in request['instruments'])]
            calls=0 if basis else len(primary['tools']);self.save(value)
            alternate_groups=[g for g in failed_groups if g in {'DAILY','QUOTE'}]
            remaining=request['timeout_seconds']-(time.monotonic()-started)
            if alternate_groups and value['command']['allow_fallback'] and calls<request['max_calls'] and remaining>=1:
                command={name:request[name] for name in DataRequest.model_fields if name in request}
                command.update(groups=alternate_groups,max_calls=request['max_calls']-calls,timeout_seconds=max(1,int(remaining)),
                    required_fields=[f for f in request['required_fields'] if '.' not in f or f.split('.',1)[0] in alternate_groups],
                    daily_source='TENCENT' if request['daily_source']=='EASTMONEY' else 'EASTMONEY',
                    quote_source='SINA' if request.get('quote_source','TENCENT')=='TENCENT' else 'TENCENT')
                if request['purpose']=='BACKGROUND':command['daily_source']='TENCENT';command['groups']=[g for g in alternate_groups if g=='QUOTE']
                if command['groups']:
                    alternate_request=self.evidence.request(DataRequest(**command))
                    alternate=self.evidence.retrieve(alternate_request['request_id'])
                    value['attempts'].append({'role':'ALTERNATE','request_id':alternate_request['request_id'],'run_id':alternate['run_id']})
                    calls+=len(alternate['tools'])
                    for fact in self.evidence.get('market_evidence_snapshots',alternate['snapshot_id'])['facts']:
                        previous=next((f for f in primary_snapshot['facts'] if key(f)==key(fact)),None)
                        if previous is None and (fact['group']=='QUOTE' or fact.get('adjustment')=='FORWARD_CURRENT_VERSION'):
                            previous=next((f for f in primary_snapshot['facts'] if f['instrument']==fact['instrument'] and
                                f['group']==fact['group'] and f.get('adjustment')==fact.get('adjustment')),None)
                        check=self.compare(previous,fact,request)
                        value['source_checks'].append(check)
                        if check['decision']=='ACCEPTED':
                            selected=[f for f in selected if key(f)!=key(fact)]+[fact]
            value['stop_reason']='CALL_BUDGET_EXHAUSTED' if calls>=request['max_calls'] else 'TIME_BUDGET_EXHAUSTED' if time.monotonic()-started>=request['timeout_seconds'] else (
                'ALTERNATE_ATTEMPT_EXHAUSTED' if len(value['attempts'])>1 else 'NO_ADAPTED_ALTERNATE_OR_DISABLED' if failed_groups else 'PRIMARY_INPUTS_SUFFICIENT')
            self.finish(value,request,selected,calls,started)
        except Exception as error:
            value.update(status='FAILED',finished_at=now(),reason=type(error).__name__+': '+str(error)[:500])
            self.save(value)
        finally:self.slot.release()

    def group_ready(self,facts,request,instrument,group):
        variants=['RAW'] if request['purpose']=='BACKGROUND' else ['RAW','FORWARD_CURRENT_VERSION']
        return all(any(f['instrument']==instrument and f['group']==group and (group!='DAILY' or f.get('adjustment')==variant)
            and not missing(f,request) and not f.get('errors') for f in facts) for variant in variants if group=='DAILY') if group=='DAILY' else any(
            f['instrument']==instrument and f['group']==group and (group!='QUOTE' or f.get('last') is not None)
            and not missing(f,request) and not f.get('errors') for f in facts)

    def expected_session(self,instrument,at,usage,group):
        local=at.astimezone(SHANGHAI);exchange=instrument.split(':')[0]
        calendar=self.evidence.market.rules.calendar(exchange,local.date(),local)
        if calendar['coverage']=='UNKNOWN':return None
        previous=usage=='PRE_MARKET_RECORD' or group=='DAILY' and local.time().replace(tzinfo=None)<day_time(15)
        previous=previous or group=='QUOTE' and calendar['phase'] in {'PRE_OPEN','UNKNOWN'}
        for offset in range(1 if previous else 0,20):
            day=local.date()-timedelta(days=offset)
            trading=self.evidence.market.rules.calendar(exchange,day)['is_trading_day']
            if trading is None:return None
            if trading:return day.isoformat()
        return None

    def finish(self,value,request,acquired,calls,started):
        cutoff=value['command']['knowledge_cutoff'] or self.clock()
        at=datetime.fromisoformat(cutoff);usage=value['command']['usage']
        selected=[f for f in acquired if datetime.fromisoformat(f['available_at'])<=at and
            (f['group'] not in {'DAILY','QUOTE'} or request['start_date']<=f.get('trade_date','')<=request['end_date']) and
            (not f.get('upstream_at') or datetime.fromisoformat(f['upstream_at'])<=datetime.fromisoformat(request['cutoff']))]
        gaps=[];freshness=[]
        for attempt in value['attempts']:
            for gap in self.evidence.get('retrieval_runs',attempt['run_id'])['gaps']:
                resolved=gap['code']!='CURRENT_STATUS_UNKNOWN' and any(f['instrument']==gap['instrument'] and f['group']==gap['group'] for f in selected)
                gaps.append({**gap,'run_id':attempt['run_id'],'resolved':resolved})
        for fact in acquired:
            if fact['group'] in {'DAILY','QUOTE'} and not request['start_date']<=fact.get('trade_date','')<=request['end_date']:
                gaps.append({'instrument':fact['instrument'],'group':fact['group'],'code':'REPORTED_SESSION_OUTSIDE_REQUEST',
                    'reported_session':fact.get('trade_date'),'resolved':False})
            if datetime.fromisoformat(fact['available_at'])>at:
                gaps.append({'instrument':fact['instrument'],'group':fact['group'],'code':'NOT_AVAILABLE_AT_CONSUMER_CUTOFF','resolved':False})
        for fact in selected:
            fields=missing(fact,request)
            if fields:gaps.append({'instrument':fact['instrument'],'group':fact['group'],'code':'REQUIRED_FIELDS_MISSING','fields':fields,'resolved':False})
        for check in value['source_checks']:
            if check['decision']=='BLOCKED':
                gaps.append({'instrument':check['instrument'],'group':check['group'],'code':'SOURCE_SWITCH_NOT_COMPARABLE','reasons':check['reasons'],'resolved':False})
        for instrument in request['instruments']:
            for group in request['groups']:
                facts=[f for f in selected if f['instrument']==instrument and f['group']==group]
                if not facts:gaps.append({'instrument':instrument,'group':group,'code':'NO_REQUIRED_FACT_AT_CONSUMER_CUTOFF','resolved':False})
                if group not in {'DAILY','QUOTE'}:continue
                expected=request['end_date'] if usage=='HISTORICAL_RESEARCH' else self.expected_session(instrument,at,usage,group)
                latest=max((f.get('trade_date') for f in facts if f.get('trade_date')),default=None)
                current=expected is not None and latest==expected
                freshness.append({'instrument':instrument,'group':group,'expected_session':expected,'latest_reported_session':latest,
                    'state':'HISTORICAL_WINDOW' if usage=='HISTORICAL_RESEARCH' else 'SESSION_CURRENT' if current else 'SESSION_STALE_OR_UNKNOWN',
                    'upstream_at':[f.get('upstream_at') for f in facts if f.get('upstream_at')],
                    'received_at':[f['received_at'] for f in facts],'knowledge_cutoff':cutoff,
                    'policy':'USE_AND_EXCHANGE_SESSION; NO_UNIVERSAL_MINUTE_THRESHOLD'})
                if usage!='HISTORICAL_RESEARCH' and not current:
                    gaps.append({'instrument':instrument,'group':group,'code':'STALE_FOR_CURRENT_SESSION' if expected else 'SESSION_CALENDAR_UNKNOWN','resolved':False})
        daily=[f for f in selected if f['group']=='DAILY']
        complete=bool(daily) and all(f.get('model_daily_input_allowed') for f in daily) and all(
            self.group_ready(selected,request,instrument,'DAILY') for instrument in request['instruments'])
        if 'DAILY' in request['groups'] and not complete:
            gaps.append({'instrument':'REQUESTED_SCOPE','group':'DAILY','code':'COMPLETE_DAILY_REQUIRED_INPUTS_NOT_SATISFIED','resolved':False})
        unresolved=any(not g['resolved'] for g in gaps)
        state='DEGRADED' if unresolved else 'HEALTHY'
        monitoring='HEALTHY' if all(any(f['instrument']==instrument and f['group']=='QUOTE' and f.get('last') is not None
            and not missing(f,request) and not f.get('errors') and f.get('trade_date')==self.expected_session(instrument,at,'CURRENT_MONITORING','QUOTE')
            for f in selected) for instrument in request['instruments']) else 'MONITORING_UNAVAILABLE'
        if usage=='CURRENT_MONITORING' and monitoring!='HEALTHY':state=monitoring
        if usage=='NEW_RISK':
            state='BLOCKED_NEW_RISK'
            gaps.append({'instrument':'REQUESTED_SCOPE','group':'QUOTE','code':'ACTION_FRESHNESS_CONDITIONS_AND_QUALIFICATION_NOT_GRANTED','resolved':False})
        value.update(status='COMPLETED',finished_at=now(),facts=selected,acquired_facts=acquired,
            knowledge_cutoff=cutoff,knowledge_clock_basis=self.clock_basis,gaps=gaps,freshness=freshness,
            network_calls=calls,elapsed_seconds=round(time.monotonic()-started,3),state=state,
            capabilities={'observation':'DEGRADED' if unresolved else 'HEALTHY',
                'required_inputs':'BLOCKED_NEW_RISK' if any(g['code'] in {'REQUIRED_FIELDS_MISSING','NO_REQUIRED_FACT_AT_CONSUMER_CUTOFF'} and not g['resolved'] for g in gaps) else 'SATISFIED',
                'complete_daily_model':'NOT_REQUESTED' if 'DAILY' not in request['groups'] else 'HEALTHY' if complete else 'BLOCKED_NEW_RISK',
                'current_monitoring':monitoring,'new_risk':'BLOCKED_NEW_RISK'})
        self.activate(value)

    def semantic_fingerprint(self,fact):
        fields=['open','close','last','high','low','previous_close','volume_shares','volume_unit','source_volume_unit','amount_yuan',
            'adjustment','adjustment_version','completion_state','errors','limitations','state','current_status','reported_limit_up','reported_limit_down',
            'upstream_at','time_precision','disclosure_date','published_at','report_period','art_code','title','document_hash',
            'dividend_yuan_per_share','ex_date','record_date','action_state','total_operating_income_yuan','net_profit_yuan','eps_yuan_per_share']
        return hashlib.sha256(encode({name:fact.get(name) for name in fields}).encode()).hexdigest()

    def activate(self,value):
        invalidations=[];revision=None
        if value.get('revision_of'):
            prior=self.evidence.get('source_resolutions',value['revision_of'])
            before={key(f):f for f in prior.get('acquired_facts',prior['facts'])};after={key(f):f for f in value['acquired_facts']}
            changed=[k for k in before.keys()&after.keys() if self.semantic_fingerprint(before[k])!=self.semantic_fingerprint(after[k])]
            additions=[k for k in after.keys()-before.keys()]
            revision={'revision_id':str(uuid4()),'prior_resolution_id':prior['resolution_id'],'new_resolution_id':value['resolution_id'],
                'recorded_at':now(),'changed_fact_keys':[list(k) for k in changed],'added_fact_keys':[list(k) for k in additions],
                'missing_in_new_run':[list(k) for k in before.keys()-after.keys()],
                'reason':'FACT_VALUE_OR_SEMANTICS_REVISED' if changed else 'SUPPLEMENTAL_EVIDENCE' if additions else 'NEW_RUN_NO_NORMALIZED_FACT_CHANGE',
                'available_basis':'NEW_ACTUAL_RECEIPT; NO_RETROACTIVE_KNOWLEDGE','source_run_ids':[a['run_id'] for a in value['attempts']]}
            value['revision']=revision
            if changed or additions:
                invalidations.append({**revision,'invalidation_id':str(uuid4()),'target_type':'RESOLUTION_ASSESSMENT','target_id':prior['resolution_id']})
            changed_hashes={before[k]['raw_hash'] for k in changed}
            for attempt in prior['attempts']:
                run=self.evidence.get('retrieval_runs',attempt['run_id'])
                snapshot=self.evidence.get('market_evidence_snapshots',run['snapshot_id'])
                for observation in snapshot['observations']:
                    if changed_hashes&set(observation['basis_raw_hashes']):
                        invalidations.append({**revision,'invalidation_id':str(uuid4()),'target_type':'OBSERVATION',
                            'target_id':observation['observation_id'],'basis_raw_hashes':observation['basis_raw_hashes']})
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                db.execute('INSERT OR REPLACE INTO source_resolutions VALUES(?,?)',(value['resolution_id'],encode(value)))
                if revision:db.execute('INSERT INTO source_revisions VALUES(?,?)',(revision['revision_id'],encode(revision)))
                for invalidation in invalidations:
                    db.execute('INSERT INTO evidence_dependency_invalidations VALUES(?,?,?)',
                        (invalidation['invalidation_id'],invalidation['target_id'],encode(invalidation)))
                db.commit()
            except BaseException:db.rollback();raise

    def replay(self,resolution_id):
        original=self.evidence.get('source_resolutions',resolution_id)
        if original['status']!='COMPLETED':raise HTTPException(409,'仅完成的原记录可结构化重放')
        archived=[];observations=[]
        for attempt in original['attempts']:
            source=self.evidence.replay(attempt['run_id'])
            archived.extend(source['facts']);observations.extend(source['observations'])
        if any(f not in archived for f in original['facts']):raise HTTPException(409,'原解析输入与归档事实不一致')
        replay={'replay_id':str(uuid4()),'resolution_id':resolution_id,'recorded_at':now(),
            'network_calls':0,'replay_kind':'ORIGINAL_IMMUTABLE_INPUT_AND_ASSESSMENT',
            'original_state':original['state'],'original_knowledge_cutoff':original['knowledge_cutoff'],
            'facts':original['facts'],'observations':observations,'freshness':original['freshness'],'gaps':original['gaps'],
            'current_dependency_status':self.get(resolution_id)['dependency_status'],'formal_judgment':'DISABLED'}
        with self.ledger.connection() as db:db.execute('INSERT INTO source_resolution_replays VALUES(?,?)',(replay['replay_id'],encode(replay)))
        return replay

    def compare(self,previous,fact,request):
        reasons=[]
        if fact['instrument'] not in request['instruments'] or not request['start_date']<=fact.get('trade_date',request['end_date'])<=request['end_date']:
            reasons.append('OBJECT_OR_SESSION_OUTSIDE_REQUEST')
        if missing(fact,request):reasons.append('REQUIRED_FIELDS_MISSING')
        if fact.get('errors'):reasons.append('SOURCE_BASIC_CHECK_FAILED')
        fields=[]
        for name in ['open','close','last','high','low','previous_close','volume_shares','amount_yuan']:
            before=previous.get(name) if previous else None;after=fact.get(name)
            outcome='MISSING_PRIMARY' if before is None else 'MISSING_ALTERNATE' if after is None else 'EQUAL' if Decimal(before)==Decimal(after) else 'DIFFERENT'
            fields.append({'field':name,'primary':before,'alternate':after,'comparison':outcome})
            if outcome=='DIFFERENT':reasons.append('CONFLICT_'+name.upper())
        if previous and previous.get('adjustment')!=fact.get('adjustment'):reasons.append('ADJUSTMENT_NOT_COMPARABLE')
        if previous and previous.get('trade_date')!=fact.get('trade_date'):reasons.append('SESSION_NOT_COMPARABLE')
        if previous and fact.get('adjustment')=='FORWARD_CURRENT_VERSION' and previous.get('adjustment_version')!=fact.get('adjustment_version'):
            reasons.append('ADJUSTED_PROVIDER_VERSION_NOT_COMPARABLE')
        return {'instrument':fact['instrument'],'group':fact['group'],'trade_date':fact.get('trade_date'),
            'primary_source':previous.get('source_id') if previous else None,'alternate_source':fact['source_id'],
            'raw_hash':fact['raw_hash'],'decision':'BLOCKED' if reasons else 'ACCEPTED','reasons':reasons,
            'field_checks':fields,'unit':fact.get('volume_unit'),'adjustment':fact.get('adjustment'),
            'primary_unit':previous.get('volume_unit') if previous else None,
            'unit_comparison':'UNKNOWN_PRIMARY_VOLUME_NOT_EXTRAPOLATED' if previous and previous.get('volume_unit')=='UNKNOWN' else 'REGISTERED_NORMALIZED_FIELD_UNITS',
            'upstream_times':{'primary':previous.get('upstream_at') if previous else None,'alternate':fact.get('upstream_at')},
            'basis':'Registered field definitions; source/context/date/required-field checks. No averaging or silent sequence splice.',
            'independence':'NOT_ASSESSED; ticket14 owns independent critical verification'}
