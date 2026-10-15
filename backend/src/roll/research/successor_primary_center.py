"""Frozen primary-center identity; never fit or generate a neighbor prediction."""
import hashlib,json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.research.shadow import fingerprint
from roll.research.models import code_fingerprint,features

METHOD=Path(__file__).with_name('reference')/'successor-primary-center-v1.json'
FIELDS=('model_artifact','calibrator_artifact','input_archive','freeze_manifest','calibration_prediction_archive','calibrated_prediction_archive')


class CenterCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


def require(condition,reason):
    if not condition:raise HTTPException(409,'PRIMARY_CENTER_'+reason)


def derive(payload):
    run=payload['model'];objects=payload['objects'];model=objects['model_artifact'];inputs=objects['input_archive'];freeze=objects['freeze_manifest'];cal=objects['calibrator_artifact'];previous=payload['predecessor'];protocol=payload['protocol'];method=payload['method']
    fps=run['artifact_fingerprints']
    require(fps==previous['model_freeze']['artifact_fingerprints']==protocol['model_artifact_fingerprints'],'MODEL_IDENTITY_MISMATCH')
    require(previous['model_freeze_manifest']==run['freeze_manifest'] and previous['model_freeze']==freeze,'FREEZE_IDENTITY_MISMATCH')
    require(freeze['model_run_id']==run['model_run_id']==previous['model_run_id'] and freeze['artifact_fingerprints']==fps,'MODEL_RUN_MISMATCH')
    for field,key in [('model_artifact','model'),('calibrator_artifact','calibrator'),('input_archive','features_and_inputs')]:require(run[field]['sha256']==fps[key],'ARTIFACT_POINTER_MISMATCH')
    require(freeze['before_calibration']==run['calibration_prediction_archive'] and freeze['after_calibration']==run['calibrated_prediction_archive'],'CAL_POINTER_MISMATCH')
    require(model['input_sha256']==run['input_archive']['sha256'] and cal['model_sha256']==run['model_artifact']['sha256'] and cal['prediction_sha256']==run['calibration_prediction_archive']['sha256'],'ARTIFACT_LINK_MISMATCH')
    require(run['code_fingerprint']==fps['code']==model['code_fingerprint']==cal['code_fingerprint']==inputs['code_fingerprint']==code_fingerprint(),'FEATURE_CODE_CHANGED')
    require(model['protocol_fingerprint']==fps['protocol']==inputs['protocol']['protocol_fingerprint'] and model['data_fingerprint']==fps['data'],'INPUT_IDENTITY_MISMATCH')
    require(freeze['feature_definition']==inputs['protocol']['design']['candidates'][0]==protocol['design']['candidates'][0],'FEATURE_DEFINITION_MISMATCH')
    fit=model['fit'];require(fit==run['fit'] and Decimal(str(fit['lambda']))==Decimal(method['centers']['penalty']),'PENALTY_MISMATCH')
    require(fit['objective']=='sum binary negative log likelihood + 0.5 * sum(non-intercept weight^2)' and fit['standardization_partition']=='DEVELOPMENT','PENALTY_CONVENTION_MISMATCH')
    require(model['features']==fit['feature_names']==freeze['feature_definition']['features'],'FEATURE_NAMES_MISMATCH')
    neighbors=protocol['design']['g5']['parameter_neighborhood']
    require(method['centers']['penalty'] in neighbors['penalty'] and method['centers']['lookback_sessions'] in neighbors['lookback_sessions'],'CENTERS_NOT_REGISTERED')
    count=0;partition_counts={}
    for name in method['required_partitions']:
        examples=inputs['examples'][name];require(bool(examples),'EMPTY_FEATURE_PARTITION')
        count+=len(examples);require(count<=method['maximum_examples'],'EXAMPLE_LIMIT')
        for row in examples:
            snapshot=row['feature_snapshot'];dates=snapshot['input_trade_dates']
            require(len(dates)==method['feature_input_closes'] and len(set(dates))==len(dates) and dates==sorted(dates) and dates[-1]==row['observation_date'],'LOOKBACK_DATES_MISMATCH')
            recomputed=features(inputs['parts'][name]['facts'],row['observation_date'],inputs['evidence_kind']=='METHOD_CASE',snapshot['consumer_knowledge_cutoff'])
            require(recomputed==snapshot,'FEATURE_SNAPSHOT_MISMATCH')
        partition_counts[name]=len(examples)
    require(fit['fitted_observation_dates']==[r['observation_date'] for r in inputs['examples']['DEVELOPMENT']],'DEVELOPMENT_FIT_DATES_MISMATCH')
    before=objects['calibration_prediction_archive'];after=objects['calibrated_prediction_archive'];examples=inputs['examples']['CALIBRATION']
    require(len(before)==len(after)==len(examples),'CAL_LENGTH_MISMATCH')
    for a,b,example in zip(before,after,examples):
        require(all(a[k]==b[k]==example[k] for k in ('observation_date','label','execution_input_sha256')) and a['model_artifact_sha256']==b['model_artifact_sha256']==run['model_artifact']['sha256'],'CAL_ROW_IDENTITY_MISMATCH')
        require(a['prediction_phase']=='BEFORE_CALIBRATOR_FIT' and b['prediction_phase']=='AFTER_CALIBRATOR_FIT_IN_SAMPLE','CAL_PHASE_MISMATCH')
    require(run['calibrator_fit_status']==freeze['calibrator_fit_status']==cal['fit_status']=='FITTED_UNVALIDATED','CAL_STATUS_MISMATCH')
    return {'centers':method['centers'],'bound_center_count':2,'binding_status':'EXACT_FROZEN_PRIMARY_IDENTITY',
        'feature_input_closes':method['feature_input_closes'],'feature_return_intervals':method['feature_return_intervals'],'verified_feature_examples':partition_counts,
        'unbound_fitted_neighbor_slots':[{'field':field,'value':v,'status':'NOT_SUPPLIED'} for field in ('penalty','lookback_sessions') for v in neighbors[field] if v!=method['centers'][field]],
        'artifacts':{field:run[field] for field in FIELDS},'model_run_id':run['model_run_id'],'model_artifact_fingerprints':fps,
        'execution_predictions_aligned':False,'neighbor_stress_admitted':False,'remaining_gaps':['NONCENTER_FITTED_ARTIFACTS_NOT_SUPPLIED','FROZEN_MODEL_EXECUTION_PREDICTIONS_NOT_BOUND','SUCCESSOR_REAL_INPUT_CONSUMER_NOT_ADMITTED','INDEPENDENT_VALIDATION_NOT_BOUND'],
        'validation_verdict':payload['completion']['validation_verdict'],'gates':payload['completion']['gates'],
        'engineering_complete':False,'complete_experiment_frozen':False,'evidence_kind':'METHOD_CASE','source_model_evidence_kind':run['evidence_kind'],
        'calibrator_fit_status':'FITTED_UNVALIDATED','capability':'NOT_GRANTED','system_usable':False,'statistical_pass':False,
        'real_forward_started_at':None,'new_fit_calls':0,'new_prediction_calls':0,'sealed_reads':0,'network_calls':0}


class SuccessorPrimaryCenters:
    def __init__(self,checks):
        self.checks=checks;self.shadow=checks.shadow;self.ledger=checks.ledger;self.evidence=checks.evidence
        with self.ledger.connection() as db:db.execute('CREATE TABLE IF NOT EXISTS research_successor_primary_centers(id TEXT PRIMARY KEY,check_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(check_id,key))')

    def parents(self,check_id):
        completion=self.checks.get(check_id);saved=self.shadow.checked_archive(completion['input_archive']);protocol=saved['protocol']
        previous=self.shadow.get(protocol['predecessor_freeze_id']);run=self.shadow.models.get(previous['model_run_id'])
        require(previous['complete_protocol_fingerprint']==protocol['predecessor_complete_protocol_fingerprint'],'PREDECESSOR_MISMATCH')
        return {'completion':completion,'protocol':protocol,'predecessor':previous,'model':run,'objects':{field:self.shadow.checked_archive(run[field]) for field in FIELDS}}

    def create(self,check_id,command):
        digest=fingerprint(command.model_dump())
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_successor_primary_centers WHERE check_id=? AND key=?',(check_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=digest:raise HTTPException(409,'PRIMARY_CENTER_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(prior[1])['binding_id'])
        body=METHOD.read_bytes();method=json.loads(body);payload={**self.parents(check_id),'method':method}
        encoded=encode(payload).encode()
        if len(encoded)>method['maximum_input_bytes']:raise HTTPException(422,'PRIMARY_CENTER_INPUT_SIZE_LIMIT')
        result=derive(payload)
        value={**result,'binding_id':str(uuid4()),'check_id':check_id,'recorded_at':now(),'basis':command.basis,
            'method':self.evidence.archive(body,'SUCCESSOR_PRIMARY_CENTER_METHOD'),'input_archive':self.evidence.archive(encoded,'SUCCESSOR_PRIMARY_CENTER_INPUT'),
            'method_fingerprint':hashlib.sha256(body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()}
        value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_PRIMARY_CENTER_MANIFEST')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE');prior=db.execute('SELECT command_hash,value FROM research_successor_primary_centers WHERE check_id=? AND key=?',(check_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=digest:raise HTTPException(409,'PRIMARY_CENTER_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(prior[1])['binding_id'])
            db.execute('INSERT INTO research_successor_primary_centers VALUES(?,?,?,?,?)',(value['binding_id'],check_id,command.idempotency_key,digest,encode(value)));db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_primary_centers WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_PRIMARY_CENTER_NOT_FOUND')
        value=json.loads(row[0]);require(self.shadow.checked_archive(value['archive'])=={k:v for k,v in value.items() if k!='archive'},'MANIFEST_MISMATCH')
        saved=self.shadow.checked_archive(value['input_archive']);require(all(saved[k]==v for k,v in self.parents(value['check_id']).items()),'NESTED_SOURCE_MISMATCH')
        self.shadow.checked_archive(value['method']);return value

    def listing(self,check_id):
        self.checks.get(check_id)
        with self.ledger.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM research_successor_primary_centers WHERE check_id=? ORDER BY rowid',(check_id,))]
        return [self.get(i) for i in ids]

    def replay(self,identifier):
        value=self.get(identifier);body=self.evidence.raw(value['method']['sha256']).read_bytes()
        require(hashlib.sha256(body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==value['method_fingerprint'],'METHOD_CHANGED')
        result=derive(self.shadow.checked_archive(value['input_archive']));require(all(value[k]==v for k,v in result.items()),'REPLAY_MISMATCH')
        return {'matches_original':True,'new_fit_calls':0,'new_prediction_calls':0,'sealed_reads':0,'network_calls':0}
