"""Review exact saved successor components without creating a qualification."""
import hashlib,json
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.research.shadow import fingerprint

METHOD=Path(__file__).with_name('reference')/'successor-evidence-review-v1.json'


class EvidenceReviewCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)
    segments_id:str|None=None
    cash_id:str|None=None
    controls_id:str|None=None
    entry_id:str|None=None
    probability_id:str|None=None


def derive(payload):
    source=payload['costs'];records=payload['records'];protocol=payload['protocol'];components={}
    components['costs']={'bound':True,'status':source['G5_status'],'scenario_count':len(source['scenarios']),
        'economics':source['base']['economics'],'hard_failures':source['base']['hard_failures']}
    for name in ('segments','cash','controls','entry','probability'):
        item=records.get(name)
        components[name]={'bound':item is not None,'status':item.get('G3_status',item.get('G4_status',item.get('G5_status','INCONCLUSIVE'))) if item else 'UNBOUND'}
        if item:components[name]['manifest']=item['archive']
    if records.get('segments'):components['segments']['thirds']=records['segments']['segments']
    if records.get('cash'):components['cash'].update(candidate=records['cash']['candidate'],cash=records['cash']['cash'],risk_matched=False)
    if records.get('controls'):components['controls'].update(controls=records['controls']['controls'],timing_contrast=records['controls']['timing_contrast'],risk_matched_qualification=False)
    if records.get('entry'):components['entry'].update(scenario_count=len(records['entry']['scenarios']),scope=records['entry']['scope'])
    if records.get('probability'):components['probability'].update(phases=records['probability']['phases'],cutoff=records['probability']['cutoff'],independent_calibration_validation=False,calendar_join_with_execution=False)
    missing=[name.upper()+'_COMPONENT_NOT_SELECTED' for name,item in records.items() if item is None]
    probability_reasons=sorted({gap for phase in records['probability']['phases'].values() for gap in phase['gaps']}) if records.get('probability') else ['PROBABILITY_BINDING_NOT_SELECTED']
    risk_failures=list(source['base']['hard_failures'])
    for name in ('cash','controls'):
        if records.get(name):risk_failures.extend(records[name]['hard_failures'])
    risk_failures=sorted(set(risk_failures))
    stress_failures=['COST_SCENARIO_HARD_FAILURE'] if source['G5_status']=='FAIL' else []
    for name in ('segments','entry'):
        if records.get(name) and records[name]['G5_status']=='FAIL':stress_failures.append(name.upper()+'_HARD_FAILURE')
    gates={
        'G1':{'status':'INCONCLUSIVE','reasons':['METHOD_INPUTS_NOT_REAL_SOURCE_ADMISSION']},
        'G2':{'status':'INCONCLUSIVE','reasons':['REAL_DEPLOYMENT_ACCEPTANCE_NOT_BOUND']},
        'G3':{'status':'INCONCLUSIVE','reasons':probability_reasons+['INDEPENDENT_PROBABILITY_VALIDATION_NOT_ADMITTED']},
        'G4':{'status':'FAIL' if risk_failures else 'INCONCLUSIVE','reasons':risk_failures+['COMMON_WINDOW_RISK_MATCHED_BENCHMARKS_NOT_ADMITTED']},
        'G5':{'status':'FAIL' if stress_failures else 'INCONCLUSIVE','reasons':stress_failures+missing+['JOINT_COMPARATOR_STRESS_NOT_BOUND','NEIGHBOR_ARTIFACTS_NOT_BOUND','REAL_MIGRATION_SCOPE_AND_INDEPENDENT_SUPPORT_NOT_ADMITTED']},
        'G6':{'status':'INCONCLUSIVE','reasons':['REAL_ONLINE_CONSISTENCY_NOT_RECORDED']},
        'G7':{'status':'INCONCLUSIVE','reasons':['REAL_MATURE_FORWARD_EVIDENCE_MISSING']}}
    return {'components':components,'bound_components':[name for name,value in components.items() if value['bound']],
        'gates':gates,'validation_verdict':'FAIL' if any(g['status']=='FAIL' for g in gates.values()) else 'INCONCLUSIVE',
        'complete_freeze_gaps':['REAL_INPUT_CONSUMER_AND_DEPLOYMENT','PROBABILITY_AND_BENCHMARK_CONSUMER_COMPLETENESS','COMPLETE_G5_PACKAGES'],
        'qualification_gaps':['INDEPENDENT_PROBABILITY_SUPPORT','COMMON_WINDOW_RISK_MATCHED_BENCHMARKS','REAL_G6_G7'],
        'primary_objective':protocol['design']['primary_objective'],'support_requirements':protocol['design']['statistics'],
        'shadow_revision':source['shadow_revision'],'input_prefix_fingerprint':source['input_prefix_fingerprint'],
        'evidence_kind':'METHOD_CASE','complete_experiment_frozen':False,'formal_consumer_admitted':False,
        'statistical_pass':False,'confirmation_pass_look':False,'capability':'NOT_GRANTED','system_usable':False,
        'real_forward_started_at':None,'new_fit_calls':0,'sealed_reads':0,'network_calls':0}


class SuccessorEvidenceReviews:
    def __init__(self,stresses,segments,cash,controls,entry,probability):
        self.stresses=stresses;self.protocols=stresses.protocols;self.ledger=stresses.ledger;self.evidence=stresses.evidence;self.shadow=stresses.shadow
        self.services={'segments':segments,'cash':cash,'controls':controls,'entry':entry,'probability':probability}
        with self.ledger.connection() as db:db.execute('CREATE TABLE IF NOT EXISTS research_successor_evidence_reviews(id TEXT PRIMARY KEY,stress_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(stress_id,key))')

    def payload(self,stress_id,selected):
        source=self.stresses.get(stress_id);protocol=self.protocols.get(source['successor_freeze_id']);records={}
        for name,service in self.services.items():
            identifier=selected.get(name+'_id');item=service.get(identifier) if identifier else None
            if item and name!='probability' and (item['stress_id']!=stress_id or item['source_manifest']!=source['archive'] or item['source_input']!=source['source']):raise HTTPException(409,'EVIDENCE_REVIEW_COMPONENT_PREFIX_MISMATCH '+name)
            if item and (item['successor_freeze_id']!=source['successor_freeze_id'] or item['complete_protocol_fingerprint']!=source['complete_protocol_fingerprint']):raise HTTPException(409,'EVIDENCE_REVIEW_COMPONENT_PROTOCOL_MISMATCH '+name)
            records[name]=item
        return {'costs':source,'protocol':protocol,'records':records}

    def create(self,stress_id,command):
        digest=fingerprint(command.model_dump())
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_successor_evidence_reviews WHERE stress_id=? AND key=?',(stress_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=digest:raise HTTPException(409,'EVIDENCE_REVIEW_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(prior[1])['review_id'])
        method_body=METHOD.read_bytes();method=json.loads(method_body);method_archive=self.evidence.archive(method_body,'SUCCESSOR_EVIDENCE_REVIEW_METHOD')
        selected=command.model_dump(exclude={'idempotency_key','basis'});payload=self.payload(stress_id,selected);body=encode(payload).encode()
        if len(body)>method['maximum_input_bytes']:raise HTTPException(422,'EVIDENCE_REVIEW_INPUT_SIZE_LIMIT')
        archived=self.evidence.archive(body,'SUCCESSOR_EVIDENCE_REVIEW_INPUT');source=payload['costs']
        value={**derive(payload),'review_id':str(uuid4()),'stress_id':stress_id,'selected':selected,'input_archive':archived,'method':method_archive,
            'method_fingerprint':hashlib.sha256(method_body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
            'source_manifest':source['archive'],'source_input':source['source'],'successor_freeze_id':source['successor_freeze_id'],
            'complete_protocol_fingerprint':source['complete_protocol_fingerprint'],'basis':command.basis,'recorded_at':now()}
        value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_EVIDENCE_REVIEW_MANIFEST')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT command_hash,value FROM research_successor_evidence_reviews WHERE stress_id=? AND key=?',(stress_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=digest:raise HTTPException(409,'EVIDENCE_REVIEW_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(prior[1])['review_id'])
            db.execute('INSERT INTO research_successor_evidence_reviews VALUES(?,?,?,?,?)',(value['review_id'],stress_id,command.idempotency_key,digest,encode(value)));db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_evidence_reviews WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_EVIDENCE_REVIEW_NOT_FOUND')
        value=json.loads(row[0]);manifest=self.shadow.checked_archive(value['archive'])
        if manifest!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'EVIDENCE_REVIEW_MANIFEST_MISMATCH')
        payload=self.payload(value['stress_id'],value['selected'])
        if payload!=self.shadow.checked_archive(value['input_archive']):raise HTTPException(409,'EVIDENCE_REVIEW_NESTED_SOURCE_MISMATCH')
        self.shadow.checked_archive(value['method']);return value

    def listing(self,stress_id):
        with self.ledger.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM research_successor_evidence_reviews WHERE stress_id=? ORDER BY rowid',(stress_id,))]
        return [self.get(identifier) for identifier in ids]

    def replay(self,identifier):
        value=self.get(identifier);method_body=self.evidence.raw(value['method']['sha256']).read_bytes()
        if hashlib.sha256(method_body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=value['method_fingerprint']:raise HTTPException(409,'EVIDENCE_REVIEW_METHOD_CHANGED')
        result=derive(self.shadow.checked_archive(value['input_archive']))
        if any(value.get(key)!=item for key,item in result.items()):raise HTTPException(409,'EVIDENCE_REVIEW_REPLAY_MISMATCH')
        return {'matches_original':True,'recomputed_component_engines':False,'new_fit_calls':0,'sealed_reads':0,'network_calls':0}
