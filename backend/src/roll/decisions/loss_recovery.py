"""Explicit LOSS acknowledgement with fresh boundary and successor qualification."""
import hashlib,json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now,timestamp
from roll.accounts.reconcile import use_check,UseCheck
from roll.decisions.funding import LossFacts,evaluate_loss
from roll.decisions.capabilities import GrantCommand,moment
from roll.decisions.actions import EvaluationCommand
from roll.market.rules import SHANGHAI

RULE=Path(__file__).with_name('reference')/'loss-recovery-v1.json'


def digest(value):return hashlib.sha256(encode(value).encode()).hexdigest()


class RecoveryCheckCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    pause_event_id:str=Field(min_length=1,max_length=128)
    successor_grant_id:str=Field(min_length=1,max_length=128)
    expected_account_version:int=Field(ge=0)
    expected_funding_version:int=Field(ge=1)
    expected_lifecycle_version:int=Field(ge=0)
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


class RecoveryActivateCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    acknowledge_preserved_peak:Literal[True]
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


class LossRecoveries:
    def __init__(self,funding,capabilities,actions):
        self.funding=funding;self.capabilities=capabilities;self.actions=actions;self.ledger=funding.ledger;self.evidence=actions.evidence;self.shadow=actions.shadow
        with self.ledger.connection() as db:db.executescript('''
            CREATE TABLE IF NOT EXISTS loss_recovery_checks(id TEXT PRIMARY KEY,key TEXT UNIQUE,hash TEXT NOT NULL,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS loss_recovery_receipts(id TEXT PRIMARY KEY,check_id TEXT UNIQUE NOT NULL,key TEXT UNIQUE NOT NULL,hash TEXT NOT NULL,value TEXT NOT NULL);
        ''')

    def effective(self,authorization,db):
        row=db.execute('SELECT value FROM loss_recovery_receipts WHERE json_extract(value,\'$.funding_version\')=? ORDER BY rowid DESC LIMIT 1',(authorization['version'],)).fetchone()
        if not row:return authorization
        receipt=self.checked(json.loads(row[0]),db)
        if receipt['evidence_kind']=='METHOD_ENGINEERING' and self.capabilities.method_package is None:return authorization
        if receipt['funding_identity']!=digest(authorization):raise HTTPException(409,'LOSS_RECOVERY_FUNDING_IDENTITY_MISMATCH')
        return {**authorization,'loss_recovery':{'recovery_id':receipt['recovery_id'],'funding_version':receipt['funding_version'],
            'acknowledged_peak_loss':receipt['preserved_peak_loss'],'pause_event_id':receipt['pause_event_id'],
            'loss_scope':receipt['loss_scope'],'activated_at':receipt['recorded_at']}}

    def checked(self,value,db=None):
        if self.shadow.checked_archive(value['archive'])!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'LOSS_RECOVERY_ARCHIVE_MISMATCH')
        self.shadow.checked_archive(value['rule'])
        if 'recovery_id' in value:
            if db is None:
                with self.ledger.connection() as connection:return self.checked(value,connection)
            row=db.execute('SELECT value FROM loss_recovery_checks WHERE id=?',(value['check_id'],)).fetchone()
            if not row:raise HTTPException(409,'LOSS_RECOVERY_ORIGINAL_CHECK_MISSING')
            check=self.checked(json.loads(row[0]),db);snapshot=check['snapshot']
            bindings=(check['status']=='READY' and check['rule']==value['rule'] and check['command']['pause_event_id']==value['pause_event_id']
                and check['command']['successor_grant_id']==value['successor_grant_id'] and snapshot['loss_scope']==value['loss_scope']
                and snapshot['current_loss']['peak_loss']==value['preserved_peak_loss']
                and all(snapshot[k]==value[k] for k in ('funding_identity','funding_version','account_version','evidence_kind')))
            if not bindings:raise HTTPException(409,'LOSS_RECOVERY_PARENT_BINDING_MISMATCH')
        return value

    def inspect(self,command,captured,db):
        caps=self.capabilities;funding=self.funding.current(db=db);account=self.ledger.account(db=db);control=caps.lifecycle(db);gaps=[]
        if account['version']!=command.expected_account_version or captured['account']!=account:gaps.append('ACCOUNT_VERSION_CHANGED')
        key=encode([funding.get('scope_kind'),funding.get('scope_id'),funding.get('loss_origin_at')])
        live=db.execute('SELECT value FROM action_loss_state WHERE scope=?',(key,)).fetchone()
        if (json.loads(live[0]) if live else None)!=captured['previous_loss']:gaps.append('CURRENT_LOSS_STATE_CHANGED')
        if self.actions.data_state(db,account)!=captured['data_state']:gaps.append('CURRENT_DATA_STATE_CHANGED')
        pending_ids=[r[0] for r in db.execute("SELECT d.id FROM account_drafts d WHERE status IN ('READY','QUARANTINED') AND NOT EXISTS(SELECT 1 FROM account_receipts r WHERE json_extract(r.receipt,'$.draft_id')=d.id)")]
        use=use_check(account,[self.ledger.get_draft(i,db) for i in pending_ids],UseCheck(purpose='NEW_RISK',required_as_of=captured['required_as_of']),timestamp,self.ledger.events(db=db))
        if use!=captured['new_risk_check'] or not use['allowed']:gaps.append('CURRENT_ACCOUNT_USE_CHANGED')
        if funding['version']!=command.expected_funding_version or captured['funding']!=funding:gaps.append('FUNDING_VERSION_CHANGED')
        if control['version']!=command.expected_lifecycle_version:gaps.append('LIFECYCLE_VERSION_CHANGED')
        row=db.execute('SELECT value FROM capability_events WHERE id=?',(command.pause_event_id,)).fetchone();pause=json.loads(row[0]) if row else None
        active=control['scopes']['NEW_RISK']
        if not pause or pause.get('reason_code')!='LOSS_BOUNDARY' or pause.get('scope')!='NEW_RISK' or pause.get('state')!='SUSPENDED' or pause.get('grant_id') is not None:gaps.append('GLOBAL_LOSS_PAUSE_REQUIRED')
        if active.get('event_id')!=command.pause_event_id or active['state']!='SUSPENDED' or active['reason_code']!='LOSS_BOUNDARY':gaps.append('LOSS_PAUSE_NO_LONGER_CURRENT')
        if any(control['scopes'][s]['state']!='ACTIVE' for s in ('MODEL','ALL_MONITOR')):gaps.append('OTHER_SCOPE_RESTRICTION_REMAINS')
        if funding['state']!='CONFIRMED' or not funding.get('enabled') or funding.get('pause_latched'):gaps.append('FUNDING_NOT_EXPLICITLY_ENABLED')
        if pause and moment(funding.get('confirmed_at'))<=moment(pause['recorded_at']):gaps.append('BOUNDARY_NOT_RECONFIRMED_AFTER_LOSS')
        loss_evaluation=db.execute('SELECT value FROM action_evaluations WHERE id=?',(pause.get('evaluation_id'),)).fetchone() if pause else None
        if not loss_evaluation:gaps.append('ORIGINAL_LOSS_EVALUATION_REQUIRED')
        elif funding['version']<=json.loads(loss_evaluation[0])['funding_version']:gaps.append('NEW_FUNDING_VERSION_REQUIRED')
        previous=captured['previous_loss'];scope={k:funding.get(k) for k in ('scope_kind','scope_id','baseline_account_version')};scope['origin_at']=funding.get('loss_origin_at')
        if not previous or not previous.get('triggered') or any(previous.get(k)!=v for k,v in scope.items()):gaps.append('TRIGGERED_LOSS_STATE_SCOPE_REQUIRED')
        if pause and pause.get('loss_scope')!=scope:gaps.append('PAUSE_LOSS_SCOPE_MISMATCH')
        current_loss=None
        try:
            if not use['allowed']:raise ValueError('CURRENT_ACCOUNT_NOT_USABLE')
            if captured['method_capture']:
                if not captured['packet'] or captured['packet_expired']:raise ValueError('CURRENT_METHOD_PACKET_NOT_USABLE')
                facts=captured['packet']['loss_facts'];valuation=None
            else:
                valuation=caps.valuations.get(replay=True)
                if valuation['input_authority']!='CONFIRMED_ACCOUNT_AND_ARCHIVED_SOURCE' or valuation['account_version']!=account['version']:raise ValueError('CURRENT_VALUATION_NOT_AUTHORITATIVE')
                facts=valuation['facts']
                if moment(facts['as_of'])<moment(captured['required_as_of']) or moment(facts['as_of']).astimezone(SHANGHAI).date()!=moment(now()).astimezone(SHANGHAI).date():raise ValueError('CURRENT_VALUATION_STALE')
            current_loss=evaluate_loss(funding,LossFacts(**facts),previous)
            if current_loss['status']=='RESTRICTED' or current_loss['peak_loss'] is None:raise ValueError('CURRENT_LOSS_FACTS_INCOMPLETE')
            if Decimal(funding['loss_threshold'])<=Decimal(current_loss['peak_loss']):gaps.append('RECONFIRMED_THRESHOLD_MUST_EXCEED_PRESERVED_PEAK')
        except (ValueError,KeyError,TypeError,HTTPException):gaps.append('CURRENT_LOSS_FACTS_NOT_USABLE')
        row=db.execute('SELECT value FROM capability_grants WHERE id=?',(command.successor_grant_id,)).fetchone();grant=json.loads(row[0]) if row else None;kind=None
        if not grant:gaps.append('SUCCESSOR_GRANT_MISSING')
        else:
            reasons,_,kind=caps._admit(GrantCommand(**grant['command']),db,grant.get('proof_id'))
            gaps.extend('SUCCESSOR:'+r for r in reasons)
            status=caps.current(db,grant['grant_id'])
            if status['state'] not in {'GRANTED','METHOD_GRANTED'} or status['reasons']:gaps.append('SUCCESSOR_NOT_CURRENTLY_QUALIFIED')
            if not set(grant['allowed_actions'])&{'BUY','ADD'}:gaps.append('SUCCESSOR_NEW_RISK_SCOPE_REQUIRED')
            if grant['funding_version']!=funding['version'] or grant['account_version']!=account['version']:gaps.append('SUCCESSOR_CURRENT_ACCOUNT_FUNDING_BINDING_REQUIRED')
            if not grant.get('predecessor_grant_id'):gaps.append('EXPLICIT_SUCCESSOR_REQUIRED')
            else:
                parent=caps.current(db,grant['predecessor_grant_id'])
                if parent['state'] not in {'REVOKED','EXPIRED'}:gaps.append('OLD_GRANT_MUST_STAY_TERMINAL')
                if pause:
                    raw=db.execute('SELECT value FROM action_evaluations WHERE id=?',(pause.get('evaluation_id'),)).fetchone()
                    evaluation=json.loads(raw[0]) if raw else None
                    inputs=self.shadow.checked_archive(evaluation['input_archive']) if evaluation else {}
                    affected=[s['grant']['grant_id'] for s in inputs.get('capabilities',{}).get('grant_statuses',[]) if not s['reasons'] and set(s['allowed_actions'])&{'BUY','ADD'}]
                    if grant['predecessor_grant_id'] not in affected:gaps.append('SUCCESSOR_NOT_LINKED_TO_LOSS_AFFECTED_GRANT')
            if pause and (moment(grant['recorded_at'])<=moment(pause['recorded_at']) or moment(grant['recorded_at'])<moment(funding['confirmed_at'])):gaps.append('SUCCESSOR_MUST_FOLLOW_LOSS_AND_BOUNDARY_CONFIRMATION')
        recovery=caps.recovery() if caps.recovery else {'state':'NORMAL'}
        if recovery['state']=='RECOVERY_LOCK':gaps.append('RECOVERY_LOCK')
        return {'gaps':sorted(set(gaps)),'account_version':account['version'],'funding_version':funding['version'],'funding_identity':digest(funding),
            'lifecycle_version':control['version'],'pause':pause,'successor':grant,'previous_loss':previous,'current_loss':current_loss,
            'loss_scope':scope,'evidence_kind':kind or 'UNQUALIFIED','data_identity':digest(captured['data_state']),
            'packet_identity':digest(captured['packet']),'recovery_state':recovery['state']}

    def create_check(self,command):
        hashed=digest(command.model_dump())
        with self.ledger.connection() as db:prior=db.execute('SELECT hash,value FROM loss_recovery_checks WHERE key=?',(command.idempotency_key,)).fetchone()
        if prior:
            if prior[0]!=hashed:raise HTTPException(409,'LOSS_RECOVERY_IDEMPOTENCY_CONFLICT')
            return self.checked(json.loads(prior[1]))
        captured=self.actions.capture(EvaluationCommand())
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT hash,value FROM loss_recovery_checks WHERE key=?',(command.idempotency_key,)).fetchone()
            if prior:
                if prior[0]!=hashed:raise HTTPException(409,'LOSS_RECOVERY_IDEMPOTENCY_CONFLICT')
                return self.checked(json.loads(prior[1]))
            snapshot=self.inspect(command,captured,db);rule=self.evidence.archive(RULE.read_bytes(),'LOSS_RECOVERY_RULE',db=db)
            value={'check_id':str(uuid4()),'status':'READY' if not snapshot['gaps'] else 'RESTRICTED','gaps':snapshot['gaps'],
                'command':command.model_dump(),'snapshot':snapshot,'rule':rule,'recorded_at':now(),'actual_funds_recovered':False}
            value['archive']=self.evidence.archive(encode(value).encode(),'LOSS_RECOVERY_CHECK',db=db)
            db.execute('INSERT INTO loss_recovery_checks VALUES(?,?,?,?)',(value['check_id'],command.idempotency_key,hashed,encode(value)));db.commit()
        return value

    def get_check(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM loss_recovery_checks WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'LOSS_RECOVERY_CHECK_NOT_FOUND')
        return self.checked(json.loads(row[0]))

    def activate(self,identifier,command):
        hashed=digest({'check_id':identifier,**command.model_dump()});self.capabilities.refresh_journal()
        with self.ledger.connection() as db:prior=db.execute('SELECT hash,value FROM loss_recovery_receipts WHERE key=?',(command.idempotency_key,)).fetchone()
        if prior:
            if prior[0]!=hashed:raise HTTPException(409,'LOSS_RECOVERY_IDEMPOTENCY_CONFLICT')
            return self.checked(json.loads(prior[1]))
        checked=self.get_check(identifier);captured=self.actions.capture(EvaluationCommand());caps=self.capabilities
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE');prior=db.execute('SELECT hash,value FROM loss_recovery_receipts WHERE key=?',(command.idempotency_key,)).fetchone()
            if prior:
                if prior[0]!=hashed:raise HTTPException(409,'LOSS_RECOVERY_IDEMPOTENCY_CONFLICT')
                return self.checked(json.loads(prior[1]))
            snapshot=self.inspect(RecoveryCheckCommand(**checked['command']),captured,db)
            if checked['status']!='READY' or snapshot['gaps'] or snapshot!=checked['snapshot']:raise HTTPException(409,{'code':'LOSS_RECOVERY_CURRENT_CONDITIONS_CHANGED','gaps':snapshot['gaps']})
            if db.execute('SELECT 1 FROM loss_recovery_receipts WHERE check_id=?',(identifier,)).fetchone():raise HTTPException(409,'LOSS_RECOVERY_CHECK_ALREADY_USED')
            if self.shadow.checked_archive(checked['rule'])!=json.loads(RULE.read_bytes()):raise HTTPException(409,'LOSS_RECOVERY_RULE_CHANGED')
            receipt={'recovery_id':str(uuid4()),'check_id':identifier,'pause_event_id':checked['command']['pause_event_id'],
                'successor_grant_id':checked['command']['successor_grant_id'],'funding_version':snapshot['funding_version'],'funding_identity':snapshot['funding_identity'],
                'account_version':snapshot['account_version'],'loss_scope':snapshot['loss_scope'],'preserved_peak_loss':snapshot['current_loss']['peak_loss'],
                'evidence_kind':snapshot['evidence_kind'],'recorded_at':now(),'basis':command.basis,'rule':checked['rule'],
                'actual_funds_recovered':snapshot['evidence_kind']=='REAL_ACQUISITION','previous_pause_preserved':True,'old_grant_revived':False}
            receipt['archive']=self.evidence.archive(encode(receipt).encode(),'LOSS_RECOVERY_RECEIPT',db=db)
            event={'event_id':str(uuid4()),'event_type':'CAPABILITY_SCOPE_CHANGED','scope':'NEW_RISK','grant_id':None,'state':'ACTIVE',
                'version':snapshot['lifecycle_version']+1,'reason_code':'LOSS_BOUNDARY','reason':command.basis,'resume_event_id':receipt['pause_event_id'],
                'recovery_check_id':identifier,'loss_recovery_id':receipt['recovery_id'],'effective_at':receipt['recorded_at'],'recorded_at':receipt['recorded_at']}
            db.execute('INSERT INTO loss_recovery_receipts VALUES(?,?,?,?,?)',(receipt['recovery_id'],identifier,command.idempotency_key,hashed,encode(receipt)))
            db.execute('INSERT INTO capability_events VALUES(?,?)',(event['event_id'],encode(event)));caps.journal.stage(event)
            if hasattr(caps,'notifications'):caps.notifications.lifecycle_changed(db,event)
            self.ledger.crash_point('loss_recovery_before_commit');db.commit()
            self.ledger.crash_point('loss_recovery_after_commit')
        caps.journal.reconcile_committed();return receipt

    def receipts(self):
        with self.ledger.connection() as db:rows=db.execute('SELECT value FROM loss_recovery_receipts ORDER BY rowid').fetchall()
        return [self.checked(json.loads(r[0])) for r in rows]
