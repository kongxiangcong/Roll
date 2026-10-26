"""Chronological views of an immutable METHOD trajectory, never capital resets."""
from decimal import Decimal
import hashlib,json
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.research.shadow import fingerprint
from roll.research.statistics import continuous_summary,fingerprint as statistics_fingerprint

METHOD=Path(__file__).with_name('reference')/'successor-time-segments-v1.json'


class SegmentCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


def derive(source,payload,method):
    baseline=payload['frozen']['baseline'];rows=payload['rows'];start=baseline['starting_session'];last=rows[-1][2]['command']['session']
    if not 1<=last-start<=method['maximum_declared_session_span']:raise HTTPException(422,'SUCCESSOR_SEGMENT_DECLARED_SPAN_LIMIT_NO_COMPRESSION')
    points={p['session']:p for p in source['base']['curve']}
    states={frame['command']['session']:frame['result'] for _,_,frame in rows}
    states[start]={'cash_yuan':baseline['cash_yuan'],'positions':baseline['positions'],'reserved_cash_yuan':'0.00'}
    slots=list(range(start+1,last+1));segments=[];bound=Decimal(source['risk_constraints']['maximum_drawdown'])
    for i in range(3):
        selected=slots[len(slots)*i//3:len(slots)*(i+1)//3]
        first=selected[0] if selected else None;end=selected[-1] if selected else None;before=first-1 if first is not None else None
        carry=states.get(before);curve=[points.get(session,{'session':session,'nav_yuan':None}) for session in ([before]+selected if selected else [])]
        economics=continuous_summary(curve);peak=Decimal(0);drawdown=Decimal(0)
        for point in curve:
            if point['nav_yuan'] is None:continue
            value=Decimal(point['nav_yuan']);peak=max(peak,value)
            if peak>0:drawdown=max(drawdown,1-value/peak)
        failures=['MAXIMUM_DRAWDOWN_EXCEEDED'] if drawdown>bound else []
        events=[e for e in source['base']['events'] if e['session'] in selected]
        segments.append({'third':i+1,'first_session':first,'last_session':end,'declared_sessions':selected,
            'carry_in':{'session':before,'boundary_state_known':carry is not None,'cash_yuan':carry['cash_yuan'] if carry else None,
                'positions':carry['positions'] if carry else None,'reserved_cash_yuan':carry.get('reserved_cash_yuan') if carry else None},
            'curve':curve,'economics':economics,'observed_drawdown_lower_bound':str(drawdown),'hard_failures':failures,
            'events':events,'fees_yuan':str(sum((Decimal(e['fees_yuan']) for e in events if 'fees_yuan' in e),Decimal(0))),
            'unknown_nav_sessions':[p['session'] for p in curve if p['nav_yuan'] is None],
            'input_gaps':[g for g in source['base']['input_gaps'] if g['session'] in selected],
            'missing_declared_sessions':[session for session in selected if session not in points],
            'status':'FAIL' if failures else 'INCONCLUSIVE','capital_reset':False,'statistical_pass':False})
    return {'segments':segments,'G5_status':'FAIL' if source['G5_status']=='FAIL' or any(s['hard_failures'] for s in segments) else 'INCONCLUSIVE',
        'source_prefix_hard_failure':source['G5_status']=='FAIL','calendar_kind':'DECLARED_METHOD_SESSION_SLOTS_NOT_REAL_TRADING_DATE_COVERAGE',
        'not_concatenated_performance':True,'capital_reset':False,'assumptions_verified':False,'statistical_pass':False,
        'remaining_components':['REAL_INPUT','COMMON_RISK_BASELINES','DELAYS','NEIGHBOR_ARTIFACTS','MIGRATION','INDEPENDENT_SEGMENT_SUPPORT']}


class SuccessorTimeSegments:
    def __init__(self,stresses):
        self.stresses=stresses;self.ledger=stresses.ledger;self.evidence=stresses.evidence;self.shadow=stresses.shadow
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_successor_time_segments(id TEXT PRIMARY KEY,stress_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(stress_id,key))')

    def create(self,stress_id,command):
        digest=fingerprint(command.model_dump())
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_successor_time_segments WHERE stress_id=? AND key=?',(stress_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=digest:raise HTTPException(409,'SUCCESSOR_SEGMENT_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(prior[1])['segmentation_id'])
        method_body=METHOD.read_bytes();method=json.loads(method_body)
        method_archive=self.evidence.archive(method_body,'SUCCESSOR_TIME_SEGMENTS_METHOD')
        source=self.stresses.get(stress_id);payload=self.shadow.checked_archive(source['source'])
        if payload['protocol']['statistical_methods']['code_fingerprint']!=statistics_fingerprint():raise HTTPException(409,'SUCCESSOR_SEGMENT_FROZEN_STATISTICS_CHANGED')
        value={**derive(source,payload,method),'segmentation_id':str(uuid4()),'stress_id':stress_id,'successor_freeze_id':source['successor_freeze_id'],
            'source_manifest':source['archive'],'source_input':source['source'],'method':method_archive,
            'method_fingerprint':hashlib.sha256(method_body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
            'statistics_fingerprint':statistics_fingerprint(),'complete_protocol_fingerprint':source['complete_protocol_fingerprint'],
            'recorded_at':now(),'basis':command.basis,'evidence_kind':'METHOD_CASE','system_usable':False,'capability':'NOT_GRANTED',
            'complete_experiment_frozen':False,'new_fit_calls':0,'sealed_reads':0,'network_calls':0}
        value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_TIME_SEGMENTS_MANIFEST')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT command_hash,value FROM research_successor_time_segments WHERE stress_id=? AND key=?',(stress_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=digest:raise HTTPException(409,'SUCCESSOR_SEGMENT_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(prior[1])['segmentation_id'])
            db.execute('INSERT INTO research_successor_time_segments VALUES(?,?,?,?,?)',(value['segmentation_id'],stress_id,command.idempotency_key,digest,encode(value)));db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_time_segments WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_TIME_SEGMENTS_NOT_FOUND')
        value=json.loads(row[0])
        if self.shadow.checked_archive(value['archive'])!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'SUCCESSOR_TIME_SEGMENTS_MANIFEST_MISMATCH')
        source=self.stresses.get(value['stress_id'])
        if source['archive']!=value['source_manifest'] or source['source']!=value['source_input']:raise HTTPException(409,'SUCCESSOR_TIME_SEGMENTS_SOURCE_MISMATCH')
        self.shadow.checked_archive(value['method']);return value

    def listing(self,stress_id):
        with self.ledger.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM research_successor_time_segments WHERE stress_id=? ORDER BY rowid',(stress_id,))]
        return [self.get(identifier) for identifier in ids]

    def replay(self,identifier):
        value=self.get(identifier);method=self.shadow.checked_archive(value['method'])
        # The exact original method bytes, including whitespace, are fingerprinted.
        actual=hashlib.sha256(self.evidence.raw(value['method']['sha256']).read_bytes()+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if actual!=value['method_fingerprint'] or statistics_fingerprint()!=value['statistics_fingerprint']:raise HTTPException(409,'SUCCESSOR_TIME_SEGMENTS_METHOD_CHANGED')
        result=derive(self.stresses.get(value['stress_id']),self.shadow.checked_archive(value['source_input']),method)
        if any(value.get(key)!=item for key,item in result.items()):raise HTTPException(409,'SUCCESSOR_TIME_SEGMENTS_REPLAY_MISMATCH')
        return {'matches_original':True,'new_fit_calls':0,'sealed_reads':0,'network_calls':0}
