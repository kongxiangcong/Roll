"""Versioned joint-evidence review; original review objects remain unchanged."""
import copy,hashlib,json
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.research.shadow import fingerprint

METHOD=Path(__file__).with_name('reference')/'successor-joint-review-v1.json'


class JointReviewCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    joint_id:str=Field(min_length=1,max_length=128)
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


def derive(payload):
    original=payload['review'];joint=payload['joint']
    fields=('components','bound_components','gates','complete_freeze_gaps','qualification_gaps','primary_objective','support_requirements','shadow_revision','input_prefix_fingerprint')
    value={key:copy.deepcopy(original[key]) for key in fields}
    value['components']['joint']={'bound':True,'manifest':joint['archive'],'scenario_count':len(joint['scenarios']),'status':joint['G5_status'],'risk_matched_qualification':False}
    value['bound_components'].append('joint');gates=value['gates']
    gates['G5']['reasons']=[reason for reason in gates['G5']['reasons'] if reason!='JOINT_COMPARATOR_STRESS_NOT_BOUND']
    gates['G5']['reasons'].append('JOINT_DESCRIPTIVE_SCENARIOS_BOUND_RISK_MATCHING_AND_INDEPENDENT_INTERVALS_NOT_ADMITTED')
    if joint['G5_status']=='FAIL':
        gates['G5']['status']='FAIL';gates['G5']['reasons'].append('JOINT_CANDIDATE_HARD_FAILURE')
    base=next(s for s in joint['scenarios'] if s['scenario_id']=='ENTRY:NEXT_OPEN:1')
    if base['candidate']['hard_failures']:
        gates['G4']['status']='FAIL';gates['G4']['reasons']=sorted(set(gates['G4']['reasons']+base['candidate']['hard_failures']))
    return {**value,'validation_verdict':'FAIL' if any(g['status']=='FAIL' for g in gates.values()) else 'INCONCLUSIVE',
        'evidence_kind':'METHOD_CASE','complete_experiment_frozen':False,'formal_consumer_admitted':False,'statistical_pass':False,
        'confirmation_pass_look':False,'capability':'NOT_GRANTED','system_usable':False,'real_forward_started_at':None,
        'original_review_unchanged':True,'recomputed_component_engines':False,'new_fit_calls':0,'sealed_reads':0,'network_calls':0}


class SuccessorJointReviews:
    def __init__(self,reviews,joints):
        self.reviews=reviews;self.joints=joints;self.ledger=reviews.ledger;self.evidence=reviews.evidence;self.shadow=reviews.shadow
        with self.ledger.connection() as db:db.execute('CREATE TABLE IF NOT EXISTS research_successor_joint_reviews(id TEXT PRIMARY KEY,source_review_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(source_review_id,key))')

    def payload(self,review_id,joint_id):
        review=self.reviews.get(review_id);joint=self.joints.get(joint_id)
        if any(review[key]!=joint[key] for key in ('stress_id','source_manifest','source_input','successor_freeze_id','complete_protocol_fingerprint','input_prefix_fingerprint')):raise HTTPException(409,'JOINT_REVIEW_SOURCE_PREFIX_MISMATCH')
        return {'review':review,'joint':joint}

    def create(self,review_id,command):
        digest=fingerprint(command.model_dump())
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_successor_joint_reviews WHERE source_review_id=? AND key=?',(review_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=digest:raise HTTPException(409,'JOINT_REVIEW_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(prior[1])['joint_review_id'])
        method_body=METHOD.read_bytes();method=json.loads(method_body);method_archive=self.evidence.archive(method_body,'SUCCESSOR_JOINT_REVIEW_METHOD')
        payload=self.payload(review_id,command.joint_id);body=encode(payload).encode()
        if len(body)>method['maximum_input_bytes']:raise HTTPException(422,'JOINT_REVIEW_INPUT_SIZE_LIMIT')
        archived=self.evidence.archive(body,'SUCCESSOR_JOINT_REVIEW_INPUT')
        value={**derive(payload),'joint_review_id':str(uuid4()),'source_review_id':review_id,'joint_id':command.joint_id,
            'original_review_manifest':payload['review']['archive'],'joint_manifest':payload['joint']['archive'],
            'input_archive':archived,'method':method_archive,'basis':command.basis,'recorded_at':now(),
            'method_fingerprint':hashlib.sha256(method_body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()}
        value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_JOINT_REVIEW_MANIFEST')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT command_hash,value FROM research_successor_joint_reviews WHERE source_review_id=? AND key=?',(review_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=digest:raise HTTPException(409,'JOINT_REVIEW_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(prior[1])['joint_review_id'])
            db.execute('INSERT INTO research_successor_joint_reviews VALUES(?,?,?,?,?)',(value['joint_review_id'],review_id,command.idempotency_key,digest,encode(value)));db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_joint_reviews WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_JOINT_REVIEW_NOT_FOUND')
        value=json.loads(row[0])
        if self.shadow.checked_archive(value['archive'])!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'JOINT_REVIEW_MANIFEST_MISMATCH')
        payload=self.payload(value['source_review_id'],value['joint_id'])
        if payload!=self.shadow.checked_archive(value['input_archive']):raise HTTPException(409,'JOINT_REVIEW_NESTED_SOURCE_MISMATCH')
        if payload['review']['archive']!=value['original_review_manifest'] or payload['joint']['archive']!=value['joint_manifest']:raise HTTPException(409,'JOINT_REVIEW_PARENT_MANIFEST_MISMATCH')
        self.shadow.checked_archive(value['method']);return value

    def listing(self,review_id):
        with self.ledger.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM research_successor_joint_reviews WHERE source_review_id=? ORDER BY rowid',(review_id,))]
        return [self.get(identifier) for identifier in ids]

    def replay(self,identifier):
        value=self.get(identifier);method_body=self.evidence.raw(value['method']['sha256']).read_bytes()
        if hashlib.sha256(method_body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=value['method_fingerprint']:raise HTTPException(409,'JOINT_REVIEW_METHOD_CHANGED')
        result=derive(self.shadow.checked_archive(value['input_archive']))
        if any(value.get(key)!=item for key,item in result.items()):raise HTTPException(409,'JOINT_REVIEW_REPLAY_MISMATCH')
        return {'matches_original':True,'original_review_unchanged':True,'recomputed_component_engines':False,'new_fit_calls':0,'sealed_reads':0,'network_calls':0}
