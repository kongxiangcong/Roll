"""Immutable engineering audit of registered scope and original lot timelines."""
import hashlib,json
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.research.shadow import fingerprint
from roll.research.statistics import fingerprint as statistics_fingerprint

METHOD=Path(__file__).with_name('reference')/'successor-migration-audit-v1.json'


class MigrationAuditCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


def derive(source,payload,method):
    frozen=payload['frozen'];baseline=frozen['baseline'];rows=payload['rows'];scope=payload['protocol']['design']['g5']['migration_scope'];allowed=set(scope['instruments']);errors=[];lots={};observed=set()
    first=baseline['starting_session'];last=rows[-1][2]['command']['session']
    if len(encode(payload).encode())>method['maximum_input_bytes'] or not 1<=len(rows)<=method['maximum_frames'] or not 1<=last-first<=method['maximum_declared_session_span']:raise HTTPException(422,'MIGRATION_AUDIT_PREFIX_LIMIT_NO_COMPRESSION')
    if set(frozen['rules'])!=allowed:errors.append('REGISTERED_SCOPE_RULES_MISMATCH')
    for position in baseline['positions']:
        migration=frozen['migrations'].get(position['migration_id'])
        valid=bool(migration and all(migration[k]==position[k] for k in ('position_id','instrument','quantity','original_exit_session')) and migration['proposal_id']==frozen['proposal_id'] and migration['policy_fingerprint']==frozen['policy_fingerprint'])
        if not valid:errors.append('BASELINE_MIGRATION_BINDING_MISMATCH:'+position['position_id'])
        identifier='BASELINE:'+position['position_id']
        lots[identifier]={'lot_id':identifier,'baseline':True,'position_id':position['position_id'],'instrument':position['instrument'],'entry_session':first,
            'expected_exit_session':position['original_exit_session'],'initial_quantity':position['quantity'],'migration_id':position['migration_id'],
            'migration_effective_session':migration['effective_session'] if migration else None,'binding_matches_frozen_migration':valid,
            'observations':[],'overdue_observed_sessions':[]}
    fills={}
    for event in source['base']['events']:
        if event['kind']=='BUY_FILL':
            identifier=event['order_id']
            if identifier in fills:errors.append('REUSED_ENTRY_ID:'+identifier)
            fills[identifier]=event
    horizon=frozen['design']['new_lot_horizon_sessions'];sessions=[]
    for _,_,frame in rows:
        command=frame['command'];session=command['session'];sessions.append(session)
        observed.update(row['instrument'] for row in command['bars']+command['signals']);seen=set()
        for position in frame['result']['positions']:
            identifier=position['lot_id'];observed.add(position['instrument'])
            if identifier in seen:errors.append('DUPLICATE_LOT_AT_SESSION:'+identifier+':'+str(session))
            seen.add(identifier)
            if identifier not in lots:
                fill=fills.get(identifier);entry=position['entry_session']
                if position['baseline'] or not fill or fill['session']!=entry or fill['instrument']!=position['instrument']:errors.append('ENTRY_LOT_IDENTITY_NOT_PROVEN:'+identifier)
                lots[identifier]={'lot_id':identifier,'baseline':False,'position_id':identifier,'instrument':position['instrument'],'entry_session':entry,
                    'expected_exit_session':entry+horizon,'initial_quantity':fill['quantity'] if fill else None,'migration_id':None,'migration_effective_session':None,
                    'binding_matches_frozen_migration':None,'observations':[],'overdue_observed_sessions':[]}
            lot=lots[identifier]
            if (position['position_id']!=lot['position_id'] or position['instrument']!=lot['instrument'] or position['entry_session']!=lot['entry_session'] or position['baseline']!=lot['baseline'] or
                position['exit_session']!=lot['expected_exit_session'] or position['original_exit_session']!=lot['expected_exit_session']):errors.append('LOT_IDENTITY_OR_ORIGINAL_HORIZON_CHANGED:'+identifier+':'+str(session))
            if position['quantity']<=0 or (lot['initial_quantity'] is not None and position['quantity']>lot['initial_quantity']) or position['sellable_quantity'] is not None and not 0<=position['sellable_quantity']<=position['quantity']:errors.append('LOT_QUANTITY_SUPPORT_INVALID:'+identifier+':'+str(session))
            if lot['observations'] and position['quantity']>lot['observations'][-1]['quantity']:errors.append('LOT_REMAINING_QUANTITY_INCREASED:'+identifier+':'+str(session))
            if lot['baseline'] and position['migration_id']!=lot['migration_id']:errors.append('LOT_MIGRATION_CHANGED:'+identifier)
            overdue=session>=lot['expected_exit_session']
            if overdue:lot['overdue_observed_sessions'].append(session)
            reasons=[g['reason'] for g in frame['result']['gaps'] if g['session']==session and g.get('instrument')==lot['instrument'] and g.get('original_exit_session')==lot['expected_exit_session']]
            lot['observations'].append({'session':session,'quantity':position['quantity'],'sellable_quantity':position['sellable_quantity'],'exit_session':position['exit_session'],
                'policy_migration_active':lot['migration_effective_session']<=session if lot['baseline'] and lot['migration_effective_session'] is not None else not lot['baseline'],
                'overdue_at_saved_close':overdue,'horizon_blocking_reasons':reasons})
    outside=sorted(observed-allowed)
    if outside:errors.append('INPUT_OUTSIDE_REGISTERED_SCOPE')
    return {'audit_status':'INCONSISTENT_METHOD_BINDINGS' if errors else 'CONSISTENT_METHOD_BINDINGS','binding_errors':errors,
        'registered_scope':scope,'observed_instruments':sorted(observed),'unobserved_registered_instruments':sorted(allowed-observed),'outside_registered_instruments':outside,
        'lots':list(lots.values()),'baseline_migration_applicability':'APPLICABLE' if baseline['positions'] else 'NOT_APPLICABLE_EXPLICIT_EMPTY_BASELINE',
        'missing_declared_sessions':[s for s in range(first+1,last+1) if s not in set(sessions)],'input_prefix_fingerprint':source['input_prefix_fingerprint'],
        'source_input_gaps':source['base']['input_gaps'],'scope_transfer_evidence':'NOT_PROVEN','G5_status':'INCONCLUSIVE','statistical_pass':False,
        'real_input_admitted':False,'risk_matched_qualification':False,'calendar_kind':'DECLARED_METHOD_SESSION_SLOTS_NOT_REAL_TRADING_DATES'}


class SuccessorMigrationAudits:
    def __init__(self,stresses):
        self.stresses=stresses;self.ledger=stresses.ledger;self.evidence=stresses.evidence;self.shadow=stresses.shadow
        with self.ledger.connection() as db:db.execute('CREATE TABLE IF NOT EXISTS research_successor_migration_audits(id TEXT PRIMARY KEY,stress_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(stress_id,key))')

    def create(self,stress_id,command):
        digest=fingerprint(command.model_dump())
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_successor_migration_audits WHERE stress_id=? AND key=?',(stress_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=digest:raise HTTPException(409,'MIGRATION_AUDIT_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(prior[1])['audit_id'])
        method_body=METHOD.read_bytes();method=json.loads(method_body);method_archive=self.evidence.archive(method_body,'SUCCESSOR_MIGRATION_AUDIT_METHOD')
        source=self.stresses.get(stress_id);payload=self.shadow.checked_archive(source['source'])
        if payload['protocol']['statistical_methods']['code_fingerprint']!=statistics_fingerprint():raise HTTPException(409,'MIGRATION_AUDIT_FROZEN_STATISTICS_CHANGED')
        value={**derive(source,payload,method),'audit_id':str(uuid4()),'stress_id':stress_id,'source_manifest':source['archive'],'source_input':source['source'],
            'method':method_archive,'successor_freeze_id':source['successor_freeze_id'],'complete_protocol_fingerprint':source['complete_protocol_fingerprint'],
            'method_fingerprint':hashlib.sha256(method_body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'statistics_fingerprint':statistics_fingerprint(),
            'basis':command.basis,'recorded_at':now(),'evidence_kind':'METHOD_CASE','system_usable':False,'capability':'NOT_GRANTED','complete_experiment_frozen':False,'new_fit_calls':0,'sealed_reads':0,'network_calls':0}
        value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_MIGRATION_AUDIT_MANIFEST')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE');prior=db.execute('SELECT command_hash,value FROM research_successor_migration_audits WHERE stress_id=? AND key=?',(stress_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=digest:raise HTTPException(409,'MIGRATION_AUDIT_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(prior[1])['audit_id'])
            db.execute('INSERT INTO research_successor_migration_audits VALUES(?,?,?,?,?)',(value['audit_id'],stress_id,command.idempotency_key,digest,encode(value)));db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_migration_audits WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_MIGRATION_AUDIT_NOT_FOUND')
        value=json.loads(row[0])
        if self.shadow.checked_archive(value['archive'])!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'MIGRATION_AUDIT_MANIFEST_MISMATCH')
        source=self.stresses.get(value['stress_id'])
        if source['archive']!=value['source_manifest'] or source['source']!=value['source_input']:raise HTTPException(409,'MIGRATION_AUDIT_SOURCE_MISMATCH')
        self.shadow.checked_archive(value['method']);return value

    def listing(self,stress_id):
        with self.ledger.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM research_successor_migration_audits WHERE stress_id=? ORDER BY rowid',(stress_id,))]
        return [self.get(identifier) for identifier in ids]

    def replay(self,identifier):
        value=self.get(identifier);body=self.evidence.raw(value['method']['sha256']).read_bytes()
        if hashlib.sha256(body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=value['method_fingerprint'] or statistics_fingerprint()!=value['statistics_fingerprint']:raise HTTPException(409,'MIGRATION_AUDIT_METHOD_CHANGED')
        result=derive(self.stresses.get(value['stress_id']),self.shadow.checked_archive(value['source_input']),json.loads(body))
        if any(value.get(key)!=item for key,item in result.items()):raise HTTPException(409,'MIGRATION_AUDIT_REPLAY_MISMATCH')
        return {'matches_original':True,'new_fit_calls':0,'sealed_reads':0,'network_calls':0}
