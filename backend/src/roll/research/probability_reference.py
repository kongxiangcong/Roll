"""Read archived CAL vectors without fitting, forecasting or consuming SEALED."""
import asyncio
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.research.shadow import fingerprint

METHOD=Path(__file__).with_name('reference')/'probability-reference-v1.json'


class ProbabilityCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_complete_protocol_fingerprint:str
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


class ProbabilityReferences:
    def __init__(self,shadow):
        self.shadow,self.models,self.ledger,self.evidence=shadow,shadow.models,shadow.ledger,shadow.evidence
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_probability_references(id TEXT PRIMARY KEY,freeze_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(freeze_id,key))')

    def source(self,frozen):
        run=self.models.get(frozen['model_run_id'])
        if run.get('artifact_fingerprints')!=frozen['model_freeze']['artifact_fingerprints']:raise HTTPException(409,'PROBABILITY_MODEL_BINDING_MISMATCH')
        manifest=self.shadow.checked_archive(frozen['model_freeze_manifest'])
        if manifest!=frozen['model_freeze'] or run['freeze_manifest']['sha256']!=frozen['model_freeze_manifest']['sha256']:
            raise HTTPException(409,'PROBABILITY_MODEL_MANIFEST_BINDING_MISMATCH')
        expected={'model_artifact':manifest['artifact_fingerprints']['model'],
            'calibrator_artifact':manifest['artifact_fingerprints']['calibrator'],
            'input_archive':manifest['artifact_fingerprints']['features_and_inputs'],
            'calibration_prediction_archive':manifest['before_calibration']['sha256'],
            'calibrated_prediction_archive':manifest['after_calibration']['sha256']}
        if any(run[key]['sha256']!=sha for key,sha in expected.items()):raise HTTPException(409,'PROBABILITY_ARCHIVE_POINTER_BINDING_MISMATCH')
        inputs=self.shadow.checked_archive(run['input_archive'])
        if set(inputs.get('parts',{}))-{'DEVELOPMENT','CALIBRATION'}:raise HTTPException(403,'REFERENCE_ONLY_SAVED_DEVELOPMENT_CALIBRATION_INPUTS')
        part=inputs['parts']['CALIBRATION'];window=part['metadata'];cutoff=part['consumer_knowledge_cutoff']
        if (inputs['protocol']['design']['event']!=frozen['design']['event'] or frozen['design']['horizon_sessions']!=20 or
                inputs['protocol']['scope']['instruments']!=frozen['scope']['instruments'] or
                any(window[key]!=manifest['windows']['CALIBRATION'][key] or window[key]!=frozen['design']['windows']['CALIBRATION'][key] for key in ('first_date','last_date'))):
            raise HTTPException(409,'PROBABILITY_CALIBRATION_SCOPE_BINDING_MISMATCH')
        examples=inputs['examples']['CALIBRATION'];scope=frozen['scope']['instruments']
        if len(examples)>10000:raise HTTPException(422,'PROBABILITY_REFERENCE_EXAMPLE_LIMIT')
        examples_by_event={}
        for example in examples:
            examples_by_event.setdefault((example['observation_date'],example['execution_input_sha256']),[]).append(example)
        if len(scope)!=1:raise HTTPException(409,'SAVED_MODEL_VECTOR_INSTRUMENT_ALIGNMENT_NOT_PROVEN')
        state=self.shadow.current(frozen['freeze_id'])
        if not state.get('input_archive'):raise HTTPException(409,'SAVED_CALENDAR_INPUT_NOT_AVAILABLE')
        original=self.shadow.checked_archive(state['input_archive'])
        sessions=[d for d in original['inputs']['sessions'] if window['first_date']<=d<=window['last_date']]
        if sessions!=sorted(set(sessions)):raise HTTPException(409,'REFERENCE_CALENDAR_ORDER_OR_DUPLICATE')
        base=self.shadow.checked_archive(run['model_artifact'])['base_rate'];phases={}
        for name,archive,old in [('BEFORE_CALIBRATION',run['calibration_prediction_archive'],run['reliability']['before_calibration']),
                ('AFTER_CALIBRATION',run['calibrated_prediction_archive'],run['reliability']['after_calibration'])]:
            predictions=self.shadow.checked_archive(archive);rows=[]
            if len(predictions)>10000:raise HTTPException(422,'PROBABILITY_REFERENCE_EVENT_LIMIT')
            for prediction in predictions:
                day=prediction['observation_date']
                matching=examples_by_event.get((day,prediction['execution_input_sha256']),[])
                example=matching[0] if len(matching)==1 else None
                mature=bool(example and example['label']==prediction['label'] and example.get('maturity_date') and
                    example['maturity_date']<=window['last_date'] and example.get('label_available_at') and
                    datetime.fromisoformat(example['label_available_at'])<=datetime.fromisoformat(cutoff) and day in sessions)
                rows.append({'canonical_key':fingerprint([scope[0],day,frozen['design']['event'],20]),'instrument':scope[0],
                    'observation_date':day,'event':frozen['design']['event'],'horizon_sessions':20,'probability':prediction['probability'],
                    'baseline_probability':base,'label':prediction['label'],'mature':mature,
                    'maturity_date':example.get('maturity_date') if example else None,'label_available_at':example.get('label_available_at') if example else None,
                    'source_prediction_sha256':archive['sha256'],'exclusion_reason':None if mature else 'ARCHIVED_LABEL_ALIGNMENT_OR_MATURITY_UNPROVEN'})
            phases[name]={'rows':rows,'saved_metrics':old,'source_archive':archive}
        return {'phases':phases,'sessions':sessions,'cutoff':cutoff,'window':window,'model_run_id':run['model_run_id'],
            'source_evidence_kind':run['evidence_kind'],'model_input_archive':run['input_archive'],'original_artifact_fingerprints':run['artifact_fingerprints'],
            'source_scope':'SAVED_CALIBRATION_FIT_IN_SAMPLE; NOT_INDEPENDENT_VALIDATION','historical_pit_proven':False}

    async def create(self,freeze_id,command):
        content=hashlib.sha256(encode(command.model_dump()).encode()).hexdigest()
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_probability_references WHERE freeze_id=? AND key=?',(freeze_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=content:raise HTTPException(409,'PROBABILITY_REFERENCE_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(prior[1])['reference_id'])
        frozen=self.shadow.get(freeze_id)
        if command.expected_complete_protocol_fingerprint!=frozen['complete_protocol_fingerprint']:raise HTTPException(409,'PROBABILITY_REFERENCE_FREEZE_CHANGED')
        # Fixed numerical conventions are archived before reading vectors or
        # calling the independent library. No post-result tolerance adjustment.
        method_body=METHOD.read_bytes();method=json.loads(method_body)
        method_archive=self.evidence.archive(method_body,'PROBABILITY_REFERENCE_METHOD')
        source=self.source(frozen)
        source_archive=self.evidence.archive(encode(source).encode(),'PROBABILITY_REFERENCE_SOURCE')
        executable=os.environ.get('ROLL_SKLEARN_PYTHON')
        if not executable:raise HTTPException(409,'SKLEARN_ISOLATED_PYTHON_NOT_CONFIGURED')
        identifier=str(uuid4());output=self.evidence.directory/'probability-reference'/identifier;output.mkdir(parents=True)
        payload={'phases':source['phases'],'method':method,'output_file':str(output/'result.json')}
        with (output/'stderr.log').open('wb') as errors:
            process=await asyncio.create_subprocess_exec(executable,'-I','-B',str(Path(__file__).with_name('probability_process.py')),
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=errors,
                env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'},creationflags=0x08000000 if os.name=='nt' else 0)
            try:await asyncio.wait_for(process.communicate(json.dumps(payload).encode()),timeout=20)
            except (asyncio.TimeoutError,asyncio.CancelledError):
                if process.returncode is None:process.kill()
                await process.wait();raise HTTPException(409,'PROBABILITY_REFERENCE_INTERRUPTED')
        result_file=output/'result.json'
        if process.returncode!=0 or not result_file.exists() or result_file.stat().st_size>8*1024*1024:raise HTTPException(409,'PROBABILITY_REFERENCE_WORKER_FAILED '+identifier)
        result=json.loads(result_file.read_text(encoding='utf-8'))
        value={**result,'reference_id':identifier,'freeze_id':freeze_id,'complete_protocol_fingerprint':frozen['complete_protocol_fingerprint'],
            'recorded_at':now(),'basis':command.basis,'source':source_archive,'method':method_archive,
            'source_scope':source['source_scope'],'source_evidence_kind':source['source_evidence_kind'],'cutoff':source['cutoff'],
            'model_run_id':source['model_run_id'],'original_artifact_fingerprints':source['original_artifact_fingerprints'],
            'method_fingerprint':hashlib.sha256(method_body+Path(__file__).read_bytes().replace(b'\r\n',b'\n')+Path(__file__).with_name('probability_process.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
            'system_usable':False,'capability':'NOT_GRANTED','statistical_assumptions_verified':False}
        value['archive']=self.evidence.archive(encode(value).encode(),'PROBABILITY_REFERENCE_MANIFEST')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT command_hash,value FROM research_probability_references WHERE freeze_id=? AND key=?',(freeze_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=content:raise HTTPException(409,'PROBABILITY_REFERENCE_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(prior[1])['reference_id'])
            db.execute('INSERT INTO research_probability_references VALUES(?,?,?,?,?)',(identifier,freeze_id,command.idempotency_key,content,encode(value)));db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_probability_references WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'PROBABILITY_REFERENCE_NOT_FOUND')
        value=json.loads(row[0]);original=self.shadow.checked_archive(value['archive'])
        if original!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'PROBABILITY_REFERENCE_MANIFEST_MISMATCH')
        self.evidence.raw(value['source']['sha256']);self.evidence.raw(value['method']['sha256'])
        return value

    def listing(self,freeze_id):
        with self.ledger.connection() as db:identifiers=[r[0] for r in db.execute('SELECT id FROM research_probability_references WHERE freeze_id=? ORDER BY rowid',(freeze_id,))]
        return [self.get(identifier) for identifier in identifiers]
