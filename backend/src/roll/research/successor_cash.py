"""Zero-exposure control on one immutable empty-position METHOD baseline."""
from decimal import Decimal
import hashlib,json
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.research.shadow import fingerprint
from roll.research.statistics import continuous_summary,fingerprint as statistics_fingerprint

METHOD=Path(__file__).with_name('reference')/'successor-cash-control-v1.json'


class CashControlCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


def derive(source,payload,method):
    baseline=payload['frozen']['baseline'];start=baseline['starting_session'];last=payload['rows'][-1][2]['command']['session']
    if baseline['positions']:raise HTTPException(409,'CASH_CONTROL_REQUIRES_EXPLICIT_EMPTY_INITIAL_POSITIONS_NO_ASSUMED_LIQUIDATION')
    if not 1<=last-start<=method['maximum_declared_session_span']:raise HTTPException(422,'CASH_CONTROL_DECLARED_SPAN_LIMIT_NO_COMPRESSION')
    slots=list(range(start,last+1));points={p['session']:p for p in source['base']['curve']}
    candidate=[points.get(session,{'session':session,'nav_yuan':None}) for session in slots]
    cash=[{'session':session,'nav_yuan':baseline['cash_yuan']} for session in slots]
    candidate_summary=continuous_summary(candidate);cash_summary=continuous_summary(cash)
    exposures=[]
    for _,_,frame in payload['rows']:
        nav=points[frame['command']['session']]['nav_yuan']
        if nav is not None and Decimal(nav)>0:exposures.append((Decimal(nav)-Decimal(frame['result']['cash_yuan']))/Decimal(nav))
    failures=list(source['base']['hard_failures'])
    maximum=Decimal(source['risk_constraints']['maximum_simulated_gross_exposure'])
    if exposures and max(exposures)>maximum+Decimal('1e-12'):failures.append('MAXIMUM_EXPOSURE_EXCEEDED')
    return {'declared_sessions':slots,'candidate':{'curve':candidate,'economics':candidate_summary,
            'missing_declared_sessions':[session for session in slots if session not in points],
            'unknown_nav_sessions':[p['session'] for p in candidate if p['nav_yuan'] is None],
            'input_gaps':source['base']['input_gaps'],'maximum_observed_gross_exposure_fraction':str(max(exposures)) if exposures else None},
        'cash':{'curve':cash,'economics':cash_summary,'gross_exposure_fraction':'0','interest_yuan':'0','fees_yuan':'0','trades':[]},
        'interval_return_difference':candidate_summary['net_return']-cash_summary['net_return'] if candidate_summary['net_return'] is not None else None,
        'risk_matched':False,'risk_difference':'CASH has zero exposure; invested candidate risk differs; no risk-matched qualification',
        'hard_failures':failures,'G4_status':'FAIL' if failures else 'INCONCLUSIVE',
        'remaining_components':['REGISTERED_START_HOLD','REGISTERED_MA5_MA20','REAL_INPUTS','INDEPENDENT_DEPENDENT_SUPPORT'],
        'calendar_kind':'DECLARED_METHOD_SESSION_SLOTS_NOT_REAL_TRADING_DATE_COVERAGE','statistical_pass':False,'assumptions_verified':False}


class SuccessorCashControls:
    def __init__(self,stresses):
        self.stresses=stresses;self.ledger=stresses.ledger;self.evidence=stresses.evidence;self.shadow=stresses.shadow
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_successor_cash_controls(id TEXT PRIMARY KEY,stress_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(stress_id,key))')

    def create(self,stress_id,command):
        digest=fingerprint(command.model_dump())
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_successor_cash_controls WHERE stress_id=? AND key=?',(stress_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=digest:raise HTTPException(409,'SUCCESSOR_CASH_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(prior[1])['control_id'])
        method_body=METHOD.read_bytes();method=json.loads(method_body)
        method_archive=self.evidence.archive(method_body,'SUCCESSOR_CASH_CONTROL_METHOD')
        source=self.stresses.get(stress_id);payload=self.shadow.checked_archive(source['source'])
        if payload['protocol']['statistical_methods']['code_fingerprint']!=statistics_fingerprint():raise HTTPException(409,'CASH_CONTROL_FROZEN_STATISTICS_CHANGED')
        value={**derive(source,payload,method),'control_id':str(uuid4()),'stress_id':stress_id,'source_manifest':source['archive'],
            'source_input':source['source'],'method':method_archive,'successor_freeze_id':source['successor_freeze_id'],
            'complete_protocol_fingerprint':source['complete_protocol_fingerprint'],'method_fingerprint':hashlib.sha256(method_body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
            'statistics_fingerprint':statistics_fingerprint(),'basis':command.basis,'recorded_at':now(),'evidence_kind':'METHOD_CASE',
            'system_usable':False,'capability':'NOT_GRANTED','complete_experiment_frozen':False,'new_fit_calls':0,'sealed_reads':0,'network_calls':0}
        value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_CASH_CONTROL_MANIFEST')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT command_hash,value FROM research_successor_cash_controls WHERE stress_id=? AND key=?',(stress_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=digest:raise HTTPException(409,'SUCCESSOR_CASH_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(prior[1])['control_id'])
            db.execute('INSERT INTO research_successor_cash_controls VALUES(?,?,?,?,?)',(value['control_id'],stress_id,command.idempotency_key,digest,encode(value)));db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_cash_controls WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_CASH_CONTROL_NOT_FOUND')
        value=json.loads(row[0])
        if self.shadow.checked_archive(value['archive'])!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'CASH_CONTROL_MANIFEST_MISMATCH')
        source=self.stresses.get(value['stress_id'])
        if source['archive']!=value['source_manifest'] or source['source']!=value['source_input']:raise HTTPException(409,'CASH_CONTROL_SOURCE_MISMATCH')
        self.shadow.checked_archive(value['method']);return value

    def listing(self,stress_id):
        with self.ledger.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM research_successor_cash_controls WHERE stress_id=? ORDER BY rowid',(stress_id,))]
        return [self.get(identifier) for identifier in ids]

    def replay(self,identifier):
        value=self.get(identifier);method_body=self.evidence.raw(value['method']['sha256']).read_bytes()
        if hashlib.sha256(method_body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=value['method_fingerprint'] or statistics_fingerprint()!=value['statistics_fingerprint']:
            raise HTTPException(409,'CASH_CONTROL_REPLAY_METHOD_CHANGED')
        result=derive(self.stresses.get(value['stress_id']),self.shadow.checked_archive(value['source_input']),json.loads(method_body))
        if any(value.get(key)!=item for key,item in result.items()):raise HTTPException(409,'CASH_CONTROL_REPLAY_MISMATCH')
        return {'matches_original':True,'new_fit_calls':0,'sealed_reads':0,'network_calls':0}
