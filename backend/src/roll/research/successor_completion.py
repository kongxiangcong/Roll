"""Versioned inventory of METHOD diagnostic bindings, never a real freeze."""
import copy,hashlib,json
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.research.shadow import fingerprint

METHOD=Path(__file__).with_name('reference')/'successor-completion-check-v1.json'


class CompletionCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    threshold_id:str=Field(min_length=1,max_length=128)
    migration_id:str=Field(min_length=1,max_length=128)
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


def derive(payload):
    review=payload['joint_review'];threshold=payload['threshold'];migration=payload['migration'];protocol=payload['protocol'];method=payload['method']
    components=copy.deepcopy(review['components']);components['threshold']={'bound':True,'manifest':threshold.get('archive'),'status':threshold['status'],'G5_status':threshold.get('G5_status')}
    components['migration']={'bound':True,'manifest':migration['archive'],'audit_status':migration['audit_status']}
    gaps=[name.upper()+'_DIAGNOSTIC_NOT_BOUND' for name in method['required_diagnostics'] if not components.get(name,{}).get('bound')]
    if threshold['status']!='SUCCEEDED':gaps.append('THRESHOLD_RUN_NOT_SUCCEEDED')
    elif [s['entry_threshold'] for s in threshold['scenarios']]!=protocol['design']['g5']['parameter_neighborhood']['probability_threshold'] or not threshold['base_matches_saved_prefix']:gaps.append('THRESHOLD_GRID_OR_BASE_MISMATCH')
    if migration['audit_status']!='CONSISTENT_METHOD_BINDINGS' or migration['binding_errors']:gaps.append('MIGRATION_BINDINGS_INCONSISTENT')
    if any(a['status']=='RUNNING' for a in payload['method_attempt_manifest']['attempts']):gaps.append('FAMILY_METHOD_ATTEMPT_RUNNING')
    if any(a['status']=='RUNNING' for a in payload['research_attempt_manifest']['attempts']):gaps.append('FAMILY_TRAINING_ATTEMPT_RUNNING')
    required=('primary_objective','statistics','stopping','costs','execution','windows','baselines','g5','formal_monitoring','candidates','successor_policy','successor_execution')
    for name in required:
        if not protocol['design'].get(name):gaps.append('REGISTERED_DESIGN_SECTION_MISSING:'+name)
    gates=copy.deepcopy(review['gates'])
    if threshold.get('G5_status')=='FAIL':gates['G5']['status']='FAIL';gates['G5']['reasons'].append('THRESHOLD_CANDIDATE_ABSOLUTE_HARD_FAILURE')
    complete=not gaps
    freeze_reasons=['SUCCESSOR_REAL_INPUT_CONSUMER_NOT_ADMITTED','FITTED_NEIGHBOR_BINDINGS_NOT_SUPPLIED']
    if gaps:freeze_reasons.append('DIAGNOSTIC_BINDINGS_INCOMPLETE')
    neighbors=protocol['design']['g5']['parameter_neighborhood']
    return {'components':components,'bound_diagnostic_count':sum(bool(components.get(name,{}).get('bound')) for name in method['required_diagnostics']),
        'required_diagnostic_count':len(method['required_diagnostics']),'diagnostic_package_complete':complete,
        'diagnostic_binding_status':'CONSISTENT_METHOD_COMPONENT_PACKAGE' if complete else 'PARTIAL_METHOD_COMPONENT_PACKAGE','diagnostic_binding_gaps':gaps,
        'engineering_complete':False,'complete_experiment_frozen':False,'complete_freeze_admission':{'status':'NOT_ADMITTED','reasons':freeze_reasons},
        'unbound_fitted_neighbor_slots':[{'field':field,'value':value,'status':'NOT_SUPPLIED','primary_center_reuse_requires_explicit_frozen_identity_mapping':True} for field in ('penalty','lookback_sessions') for value in neighbors[field]],
        'qualification_gaps':review['qualification_gaps'],'gates':gates,'validation_verdict':'FAIL' if any(g['status']=='FAIL' for g in gates.values()) else 'INCONCLUSIVE',
        'method_attempt_manifest':payload['method_attempt_manifest'],'research_attempt_manifest':payload['research_attempt_manifest'],
        'input_prefix_fingerprint':review['input_prefix_fingerprint'],'shadow_revision':review['shadow_revision'],
        'evidence_kind':'METHOD_CASE','capability':'NOT_GRANTED','system_usable':False,'statistical_pass':False,'confirmation_pass_look':False,
        'real_forward_started_at':None,'new_fit_calls':0,'sealed_reads':0,'network_calls':0,'recomputed_component_engines':False}


class SuccessorCompletionChecks:
    def __init__(self,joint_reviews,thresholds,migrations):
        self.joint_reviews=joint_reviews;self.thresholds=thresholds;self.migrations=migrations;self.ledger=joint_reviews.ledger;self.evidence=joint_reviews.evidence;self.shadow=joint_reviews.shadow;self.reviews=joint_reviews.reviews
        with self.ledger.connection() as db:db.execute('CREATE TABLE IF NOT EXISTS research_successor_completion_checks(id TEXT PRIMARY KEY,joint_review_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(joint_review_id,key))')

    def parents(self,joint_review_id,threshold_id,migration_id):
        joint=self.joint_reviews.get(joint_review_id);root=self.reviews.get(joint['source_review_id']);threshold=self.thresholds.get(threshold_id);migration=self.migrations.get(migration_id)
        if threshold['status']=='RUNNING' or not threshold.get('archive'):raise HTTPException(409,'COMPLETION_CHECK_REQUIRES_TERMINAL_THRESHOLD_RECORD')
        for item in (threshold,migration):
            if any(root[key]!=item[key] for key in ('stress_id','source_manifest','source_input','successor_freeze_id','complete_protocol_fingerprint')):raise HTTPException(409,'COMPLETION_CHECK_SOURCE_PREFIX_MISMATCH')
        protocol=self.reviews.protocols.get(root['successor_freeze_id'])
        return {'joint_review':joint,'source_review':root,'threshold':threshold,'migration':migration,'protocol':protocol}

    def create(self,joint_review_id,command):
        digest=fingerprint(command.model_dump())
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_successor_completion_checks WHERE joint_review_id=? AND key=?',(joint_review_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=digest:raise HTTPException(409,'COMPLETION_CHECK_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(prior[1])['check_id'])
        method_body=METHOD.read_bytes();method=json.loads(method_body);method_archive=self.evidence.archive(method_body,'SUCCESSOR_COMPLETION_CHECK_METHOD')
        parents=self.parents(joint_review_id,command.threshold_id,command.migration_id);protocol_id=parents['protocol']['protocol_id']
        payload={**parents,'method':method,'method_attempt_manifest':self.thresholds.manifest(protocol_id),'research_attempt_manifest':self.thresholds.registry.attempt_manifest(protocol_id)}
        body=encode(payload).encode()
        if len(body)>method['maximum_input_bytes']:raise HTTPException(422,'COMPLETION_CHECK_INPUT_SIZE_LIMIT')
        input_archive=self.evidence.archive(body,'SUCCESSOR_COMPLETION_CHECK_INPUT')
        value={**derive(payload),'check_id':str(uuid4()),'joint_review_id':joint_review_id,'threshold_id':command.threshold_id,'migration_id':command.migration_id,
            'input_archive':input_archive,'method':method_archive,'recorded_at':now(),'basis':command.basis,
            'method_fingerprint':hashlib.sha256(method_body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()}
        value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_COMPLETION_CHECK_MANIFEST')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE');prior=db.execute('SELECT command_hash,value FROM research_successor_completion_checks WHERE joint_review_id=? AND key=?',(joint_review_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=digest:raise HTTPException(409,'COMPLETION_CHECK_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(prior[1])['check_id'])
            db.execute('INSERT INTO research_successor_completion_checks VALUES(?,?,?,?,?)',(value['check_id'],joint_review_id,command.idempotency_key,digest,encode(value)));db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_completion_checks WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_COMPLETION_CHECK_NOT_FOUND')
        value=json.loads(row[0])
        if self.shadow.checked_archive(value['archive'])!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'COMPLETION_CHECK_MANIFEST_MISMATCH')
        saved=self.shadow.checked_archive(value['input_archive']);current=self.parents(value['joint_review_id'],value['threshold_id'],value['migration_id'])
        if any(saved[key]!=item for key,item in current.items()):raise HTTPException(409,'COMPLETION_CHECK_NESTED_SOURCE_MISMATCH')
        self.shadow.checked_archive(value['method']);return value

    def listing(self,joint_review_id):
        with self.ledger.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM research_successor_completion_checks WHERE joint_review_id=? ORDER BY rowid',(joint_review_id,))]
        return [self.get(identifier) for identifier in ids]

    def replay(self,identifier):
        value=self.get(identifier);body=self.evidence.raw(value['method']['sha256']).read_bytes()
        if hashlib.sha256(body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=value['method_fingerprint']:raise HTTPException(409,'COMPLETION_CHECK_METHOD_CHANGED')
        result=derive(self.shadow.checked_archive(value['input_archive']))
        if any(value.get(key)!=item for key,item in result.items()):raise HTTPException(409,'COMPLETION_CHECK_REPLAY_MISMATCH')
        return {'matches_original':True,'recomputed_component_engines':False,'new_fit_calls':0,'sealed_reads':0,'network_calls':0}
