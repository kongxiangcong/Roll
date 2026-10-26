"""Immutable v2 protocol bindings and prefix diagnostics; no qualification writer."""
import copy
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.research.shadow import fingerprint
from roll.research.successor_shadow import source_fingerprint,usable,simulate
from roll.research.statistics import method_manifest,continuous_summary,fingerprint as statistics_fingerprint


class ProtocolFreezeCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    protocol_id:str
    expected_protocol_fingerprint:str
    expected_successor_fingerprint:str
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


class DiagnosticCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_complete_protocol_fingerprint:str
    expected_revision:int=Field(ge=0,le=1000)
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


def code():
    return fingerprint({'protocol':hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        'successor_engine':source_fingerprint(),'statistics':statistics_fingerprint()})


def diagnostic(protocol,frozen,frames):
    baseline=frozen['baseline'];curve=[{'session':baseline['starting_session'],
        'nav_yuan':baseline['cash_yuan'] if not baseline['positions'] else None}]
    for frame in frames:
        bars={b['instrument']:b for b in frame['command']['bars']};state=frame['result']
        known=all(usable(bars.get(p['instrument'])) for p in state['positions'])
        nav=Decimal(state['cash_yuan'])+sum((Decimal(bars[p['instrument']]['close_yuan'])*p['quantity'] for p in state['positions']),Decimal(0)) if known else None
        curve.append({'session':frame['command']['session'],'nav_yuan':str(nav) if nav is not None else None})
    economics=continuous_summary(curve)
    hard=[]
    if economics['maximum_drawdown'] is not None and Decimal(str(economics['maximum_drawdown']))>Decimal(protocol['design']['primary_objective']['risk_constraints']['maximum_drawdown']):
        hard.append('MAXIMUM_DRAWDOWN_EXCEEDED')
    reasons={
        'G1':['METHOD_SNAPSHOTS_NOT_REAL_SOURCE_ADMISSION'],
        'G2':['REAL_DEPLOYMENT_ACCEPTANCE_NOT_BOUND'],
        'G3':['INDEPENDENT_MATURE_FORECAST_LABEL_PACKAGE_NOT_BOUND'],
        'G4':hard or ['COMMON_WINDOW_RISK_MATCHED_BENCHMARK_PACKAGE_NOT_BOUND'],
        'G5':['SUCCESSOR_STRESS_AND_NEIGHBOR_PACKAGES_NOT_BOUND'],
        'G6':['REAL_ONLINE_CONSISTENCY_NOT_RECORDED'],
        'G7':['REAL_MATURE_FORWARD_EVIDENCE_MISSING']}
    gates={key:{'status':'FAIL' if key=='G4' and hard else 'INCONCLUSIVE','reasons':value} for key,value in reasons.items()}
    return {'gates':gates,'validation_verdict':'FAIL' if hard else 'INCONCLUSIVE',
        'method_checks':{'replay_matches':True,'statistical_arithmetic_passed':protocol['statistical_methods']['algorithm_checks_passed']},
        'economics':economics,'curve':curve,'calendar_kind':'DECLARED_METHOD_SESSION_SLOTS_NOT_REAL_TRADING_DATE_COVERAGE',
        'probability_support':{'status':'UNBOUND_MATURE_LABELS','mature_real_count':0},
        'statistical_pass':False,'assumptions_verified':False,'confirmation_pass_look':False,'sealed_read':False}


class SuccessorProtocols:
    def __init__(self,successor,validation):
        self.successor=successor;self.validation=validation
        self.shadow=successor.successors.shadow;self.registry=self.shadow.registry
        self.ledger=self.registry.ledger;self.evidence=self.registry.evidence
        with self.ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS research_successor_complete_protocols(
                    freeze_id TEXT PRIMARY KEY,key TEXT,command_hash TEXT,value TEXT);
                CREATE TABLE IF NOT EXISTS research_successor_protocol_validations(
                    id TEXT PRIMARY KEY,freeze_id TEXT,key TEXT,command_hash TEXT,value TEXT,UNIQUE(freeze_id,key));
                CREATE UNIQUE INDEX IF NOT EXISTS successor_complete_protocol_owner
                    ON research_successor_complete_protocols(json_extract(value,'$.protocol_id'));
            ''')

    def for_parent(self,predecessor_freeze_id):
        self.shadow.get(predecessor_freeze_id)
        with self.ledger.connection() as db:
            rows=db.execute("SELECT id FROM research_successor_freezes WHERE json_extract(value,'$.predecessor_freeze_id')=? ORDER BY rowid",(predecessor_freeze_id,)).fetchall()
        return [self.successor.get(r[0]) for r in rows]

    def freeze(self,freeze_id,command):
        frozen=self.successor.get(freeze_id)
        previous=self.shadow.get(frozen['predecessor_freeze_id'])
        child=self.registry.get(command.protocol_id);parent=self.registry.get(previous['protocol_id'])
        if frozen['successor_fingerprint']!=command.expected_successor_fingerprint or child['protocol_fingerprint']!=command.expected_protocol_fingerprint:
            raise HTTPException(409,'SUCCESSOR_PROTOCOL_FINGERPRINT_MISMATCH')
        if child['predecessor_id']!=parent['protocol_id'] or child['dataset_id']!=parent['dataset_id']:
            raise HTTPException(409,'SAME_FAMILY_SUCCESSOR_PROTOCOL_REQUIRED')
        content=fingerprint(command.model_dump(exclude={'idempotency_key'}))
        with self.ledger.connection() as db:
            prior=db.execute('SELECT key,command_hash,value FROM research_successor_complete_protocols WHERE freeze_id=?',(freeze_id,)).fetchone()
        if prior:
            if prior[0]!=command.idempotency_key or prior[1]!=content:raise HTTPException(409,'SUCCESSOR_COMPLETE_PROTOCOL_IMMUTABLE')
            return self.get(freeze_id)
        design=copy.deepcopy(previous['design'])
        required=['primary_objective','statistics','stopping','costs','execution','windows','baselines','g5','formal_monitoring','candidates']
        missing=['MISSING_'+name.upper() for name in required if not design.get(name)]
        if Decimal(frozen['baseline']['cash_yuan'])==0 and not frozen['baseline']['positions']:
            missing.append('EMPTY_ZERO_VALUE_BASELINE')
        missing+=['CHILD_DESIGN_MISMATCH_'+name.upper() for name in required if child.get('design',{}).get(name)!=design.get(name)]
        attempts=self.registry.attempt_manifest(child['protocol_id'])
        if any(a['status']=='RUNNING' for a in attempts['attempts']):missing.append('FAMILY_ATTEMPT_STILL_RUNNING')
        if missing:raise HTTPException(409,{'gaps':missing})
        methods=method_manifest(design)
        design['successor_policy']=frozen['policy'];design['successor_execution']=frozen['design']
        value={'complete_protocol_id':str(uuid4()),'successor_freeze_id':freeze_id,'protocol_id':child['protocol_id'],
            'protocol_fingerprint':child['protocol_fingerprint'],'predecessor_freeze_id':previous['freeze_id'],
            'predecessor_complete_protocol_fingerprint':previous['complete_protocol_fingerprint'],
            'successor_fingerprint':frozen['successor_fingerprint'],'model_artifact_fingerprints':frozen['model_artifact_fingerprints'],
            'model_evidence_kind':previous['evidence_kind'],'evidence_kind':'METHOD_CASE','namespace':'SUCCESSOR_METHOD_PROTOCOL',
            'design':design,'baseline':frozen['baseline'],'rules':frozen['rules'],'statistical_methods':methods,
            'validation_resource_plan':{'maximum_method_frames':1000,'uses_existing_pinned_shadow_replay':True},
            'attempt_manifest':attempts,'prior_validation_records':self.validation.list(previous['freeze_id']),
            'protocol_parameters_frozen':True,'complete_experiment_frozen':False,
            'complete_freeze_gaps':['SUCCESSOR_REAL_INPUT_CONSUMER_UNIMPLEMENTED',
                'MATURE_PROBABILITY_AND_COMMON_BENCHMARK_BINDINGS_UNIMPLEMENTED','SUCCESSOR_G5_BINDINGS_UNIMPLEMENTED'],
            'formal_consumer_admitted':False,'system_usable':False,'capability':'NOT_GRANTED',
            'validation_verdict':'INCONCLUSIVE','real_forward_started_at':None,'calibrator_fit_status':previous['calibrator_fit_status'],
            'registered_at':now(),'basis':command.basis,'code_fingerprint':code()}
        value['complete_protocol_fingerprint']=fingerprint(value)
        value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_COMPLETE_METHOD_PROTOCOL',evidence_kind='METHOD_CASE')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM research_successor_frames WHERE freeze_id=?',(freeze_id,)).fetchone():
                raise HTTPException(409,'SUCCESSOR_PROTOCOL_MUST_PRECEDE_SHADOW_FRAMES')
            if db.execute('SELECT 1 FROM research_successor_complete_protocols WHERE freeze_id=?',(freeze_id,)).fetchone():
                raise HTTPException(409,'SUCCESSOR_COMPLETE_PROTOCOL_CONCURRENT_CHANGE')
            if db.execute("SELECT 1 FROM research_successor_complete_protocols WHERE json_extract(value,'$.protocol_id')=?",(child['protocol_id'],)).fetchone():
                raise HTTPException(409,'SUCCESSOR_REGISTERED_PROTOCOL_ALREADY_BOUND')
            family=self.registry.attempt_manifest(child['protocol_id'])
            if family!=attempts:raise HTTPException(409,'SUCCESSOR_FAMILY_CHANGED_DURING_FREEZE')
            db.execute('INSERT INTO research_successor_complete_protocols VALUES(?,?,?,?)',(freeze_id,command.idempotency_key,content,encode(value)))
            self.registry.event(child['protocol_id'],'SUCCESSOR_METHOD_PROTOCOL_PARAMETERS_FROZEN',db=db,successor_freeze_id=freeze_id,complete_protocol_fingerprint=value['complete_protocol_fingerprint'],complete_experiment_frozen=False,confirmatory_pass_look=False)
            db.commit()
        return value

    def get(self,freeze_id):
        frozen=self.successor.get(freeze_id)
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_complete_protocols WHERE freeze_id=?',(freeze_id,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_COMPLETE_PROTOCOL_NOT_FOUND')
        value=json.loads(row[0])
        if self.shadow.checked_archive(value['archive'])!={k:v for k,v in value.items() if k!='archive'}:
            raise HTTPException(409,'SUCCESSOR_PROTOCOL_ARCHIVE_MISMATCH')
        if value['code_fingerprint']!=code() or frozen['successor_fingerprint']!=value['successor_fingerprint']:
            raise HTTPException(409,'SUCCESSOR_PROTOCOL_CODE_OR_BINDING_CHANGED')
        if self.registry.get(value['protocol_id'])['protocol_fingerprint']!=value['protocol_fingerprint']:
            raise HTTPException(409,'SUCCESSOR_REGISTERED_PROTOCOL_CHANGED')
        return value

    def prefix(self,freeze_id,revision):
        frozen=self.successor.get(freeze_id)
        # Bind verification to this immutable prefix, including SQL retrieval.
        # Later history must neither consume this budget nor affect its replay.
        frames=[]
        with self.ledger.connection() as db:
            rows=db.execute('SELECT revision,command_hash,value FROM research_successor_frames WHERE freeze_id=? AND revision<=? ORDER BY revision',(freeze_id,revision))
            for number,command_hash,raw in rows:
                value=json.loads(raw)
                try:
                    if (number!=len(frames)+1 or value['command']['expected_revision']!=len(frames) or
                            fingerprint(value['command'])!=value['input_fingerprint'] or command_hash!=value['input_fingerprint']):
                        raise ValueError('input')
                    result=simulate(frozen,[f['command'] for f in frames]+[value['command']])
                    if result!=value['result'] or fingerprint(result)!=value['result_fingerprint']:
                        raise ValueError('result')
                except (KeyError,TypeError,ValueError):
                    raise HTTPException(409,'SUCCESSOR_VALIDATION_PREFIX_BINDING_MISMATCH')
                frames.append(value)
        if revision>len(frames):raise HTTPException(409,'SUCCESSOR_VALIDATION_REVISION_NOT_AVAILABLE')
        return frozen,frames

    def create(self,freeze_id,command):
        protocol=self.get(freeze_id)
        if command.expected_complete_protocol_fingerprint!=protocol['complete_protocol_fingerprint']:
            raise HTTPException(409,'SUCCESSOR_VALIDATION_PROTOCOL_MISMATCH')
        content=fingerprint(command.model_dump(exclude={'idempotency_key'}))
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_successor_protocol_validations WHERE freeze_id=? AND key=?',(freeze_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=content:raise HTTPException(409,'SUCCESSOR_VALIDATION_IDEMPOTENCY_CONFLICT')
            return self.checked(json.loads(prior[1]))
        frozen,frames=self.prefix(freeze_id,command.expected_revision)
        result=diagnostic(protocol,frozen,frames)
        value={'validation_id':str(uuid4()),'successor_freeze_id':freeze_id,'complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],
            'shadow_revision':command.expected_revision,'input_fingerprint':fingerprint(frames),'registered_at':now(),'basis':command.basis,
            'attempt_manifest':self.registry.attempt_manifest(protocol['protocol_id']),
            'evidence_kind':'METHOD_CASE','system_usable':False,'capability':'NOT_GRANTED',**result}
        value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_METHOD_VALIDATION',evidence_kind='METHOD_CASE')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT command_hash,value FROM research_successor_protocol_validations WHERE freeze_id=? AND key=?',(freeze_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=content:raise HTTPException(409,'SUCCESSOR_VALIDATION_IDEMPOTENCY_CONFLICT')
                return self.checked(json.loads(prior[1]))
            db.execute('INSERT INTO research_successor_protocol_validations VALUES(?,?,?,?,?)',(value['validation_id'],freeze_id,command.idempotency_key,content,encode(value)))
            self.registry.event(protocol['protocol_id'],'SUCCESSOR_METHOD_VALIDATION_RECORDED',db=db,validation_id=value['validation_id'],validation_verdict=value['validation_verdict'],confirmatory_pass_look=False,sealed_read=False)
            db.commit()
        return value

    def checked(self,value):
        protocol=self.get(value['successor_freeze_id'])
        if self.shadow.checked_archive(value['archive'])!={k:v for k,v in value.items() if k!='archive'} or value['complete_protocol_fingerprint']!=protocol['complete_protocol_fingerprint']:
            raise HTTPException(409,'SUCCESSOR_VALIDATION_ARCHIVE_MISMATCH')
        return value

    def list(self,freeze_id):
        self.get(freeze_id)
        with self.ledger.connection() as db:rows=db.execute('SELECT value FROM research_successor_protocol_validations WHERE freeze_id=? ORDER BY rowid',(freeze_id,)).fetchall()
        return [self.checked(json.loads(r[0])) for r in rows]

    def replay(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_protocol_validations WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_VALIDATION_NOT_FOUND')
        value=self.checked(json.loads(row[0]));protocol=self.get(value['successor_freeze_id'])
        frozen,frames=self.prefix(value['successor_freeze_id'],value['shadow_revision'])
        computed=diagnostic(protocol,frozen,frames)
        matches=fingerprint(frames)==value['input_fingerprint'] and all(value.get(k)==v for k,v in computed.items())
        if not matches:raise HTTPException(409,'SUCCESSOR_VALIDATION_REPLAY_MISMATCH')
        return {'validation_id':identifier,'matches_original':True,'shadow_revision':value['shadow_revision'],'network_calls':0,'system_usable':False,'capability':'NOT_GRANTED'}
