"""Archive model-bound CAL execution contracts beside one saved center."""
import asyncio,hashlib,json,os,sys
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.research.shadow import fingerprint

METHOD=Path(__file__).with_name('reference')/'successor-model-replay-v1.json'


class ModelReplayCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


def code():
    return hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')+Path(__file__).with_name('successor_model_replay_process.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()


class SuccessorModelReplays:
    def __init__(self,centers):
        self.centers=centers;self.ledger=centers.ledger;self.evidence=centers.evidence;self.shadow=centers.shadow;self.protocols=centers.checks.reviews.protocols
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_successor_model_replays(id TEXT PRIMARY KEY,binding_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(binding_id,key))')

    async def run(self,payload,output):
        with (output/'stderr.log').open('wb') as errors:
            process=await asyncio.create_subprocess_exec(sys.executable,'-I','-B',str(Path(__file__).with_name('successor_model_replay_process.py')),
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=errors,creationflags=0x08000000 if os.name=='nt' else 0)
            try:await asyncio.wait_for(process.communicate(json.dumps({**payload,'output_file':str(output/'result.json')}).encode()),timeout=payload['method']['worker_seconds'])
            except (asyncio.TimeoutError,asyncio.CancelledError):
                if process.returncode is None:process.kill()
                await process.wait();raise HTTPException(409,'SUCCESSOR_MODEL_REPLAY_INTERRUPTED')
        file=output/'result.json'
        if process.returncode!=0 or not file.exists() or file.stat().st_size>payload['method']['maximum_output_bytes']:raise HTTPException(409,'SUCCESSOR_MODEL_REPLAY_WORKER_FAILED '+output.name)
        return json.loads(file.read_text(encoding='utf-8'))

    async def create(self,binding_id,command):
        digest=fingerprint(command.model_dump())
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_successor_model_replays WHERE binding_id=? AND key=?',(binding_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=digest:raise HTTPException(409,'SUCCESSOR_MODEL_REPLAY_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(prior[1])['replay_id'])
        method_body=METHOD.read_bytes();method=json.loads(method_body)
        method_archive=self.evidence.archive(method_body,'SUCCESSOR_MODEL_REPLAY_METHOD')
        source=self.centers.get(binding_id);original=self.shadow.checked_archive(source['input_archive']);previous=original['predecessor']
        protocol=original['protocol'];frozen=self.protocols.successor.get(protocol['successor_freeze_id'])
        if frozen['baseline']['positions']:raise HTTPException(409,'MODEL_REPLAY_REQUIRES_EMPTY_INITIAL_POSITIONS_NO_ASSUMED_LIQUIDATION')
        if original['model']['evidence_kind']!='METHOD_CASE':raise HTTPException(409,'MODEL_REPLAY_ONLY_BOUND_METHOD_INPUT')
        state=self.shadow.current(previous['freeze_id'])
        if not state.get('input_archive'):raise HTTPException(409,'MODEL_REPLAY_SAVED_FULL_CALENDAR_REQUIRED')
        calendar_archive=state['input_archive'];calendar=self.shadow.checked_archive(calendar_archive)
        payload={'source':source,'frozen':frozen,'predecessor':previous,'model_input':original['objects']['input_archive'],
            'predictions':original['objects']['calibrated_prediction_archive'],'prediction_archive':source['artifacts']['calibrated_prediction_archive'],
            'model_input_archive':source['artifacts']['input_archive'],'calendar_archive':calendar_archive,'calendar':calendar,'method':method,'statistics_code':protocol['statistical_methods']['code_fingerprint']}
        body=encode(payload).encode()
        if len(body)>method['maximum_input_bytes']:raise HTTPException(422,'SUCCESSOR_MODEL_REPLAY_INPUT_SIZE_LIMIT')
        input_archive=self.evidence.archive(body,'SUCCESSOR_MODEL_REPLAY_INPUT')
        identifier=str(uuid4());output=self.evidence.directory/'successor-model-replays'/identifier;output.mkdir(parents=True)
        result=await self.run(payload,output)
        value={**result,'replay_id':identifier,'binding_id':binding_id,'source_manifest':source['archive'],'source_input':source['input_archive'],
            'input_archive':input_archive,'method':method_archive,'method_fingerprint':code(),
            'calendar_archive':calendar_archive,'prediction_archive':payload['prediction_archive'],'recorded_at':now(),'basis':command.basis,
            'evidence_kind':'METHOD_CASE','system_usable':False,'capability':'NOT_GRANTED','complete_experiment_frozen':False}
        value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_MODEL_REPLAY_MANIFEST')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT command_hash,value FROM research_successor_model_replays WHERE binding_id=? AND key=?',(binding_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=digest:raise HTTPException(409,'SUCCESSOR_MODEL_REPLAY_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(prior[1])['replay_id'])
            db.execute('INSERT INTO research_successor_model_replays VALUES(?,?,?,?,?)',(identifier,binding_id,command.idempotency_key,digest,encode(value)));db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_model_replays WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_MODEL_REPLAY_NOT_FOUND')
        value=json.loads(row[0])
        if self.shadow.checked_archive(value['archive'])!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'SUCCESSOR_MODEL_REPLAY_MANIFEST_MISMATCH')
        source=self.centers.get(value['binding_id'])
        if source['archive']!=value['source_manifest'] or source['input_archive']!=value['source_input']:raise HTTPException(409,'SUCCESSOR_MODEL_REPLAY_SOURCE_MISMATCH')
        payload=self.shadow.checked_archive(value['input_archive'])
        if self.shadow.checked_archive(value['calendar_archive'])!=payload['calendar']:raise HTTPException(409,'MODEL_REPLAY_CALENDAR_MISMATCH')
        frozen=self.protocols.successor.get(payload['frozen']['successor_freeze_id'])
        if frozen!=payload['frozen'] or source!=payload['source']:raise HTTPException(409,'MODEL_REPLAY_NESTED_SOURCE_MISMATCH')
        self.shadow.checked_archive(value['method'])
        return value

    def listing(self,binding_id):
        with self.ledger.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM research_successor_model_replays WHERE binding_id=? ORDER BY rowid',(binding_id,))]
        return [self.get(identifier) for identifier in ids]

    async def replay(self,identifier):
        value=self.get(identifier)
        if value['method_fingerprint']!=code():raise HTTPException(409,'SUCCESSOR_MODEL_REPLAY_REPLAY_CODE_CHANGED')
        payload=self.shadow.checked_archive(value['input_archive'])
        output=self.evidence.directory/'successor-model-replays'/('replay-'+str(uuid4()));output.mkdir(parents=True)
        result=await self.run(payload,output)
        if any(value.get(key)!=item for key,item in result.items()):raise HTTPException(409,'SUCCESSOR_MODEL_REPLAY_REPLAY_MISMATCH')
        return {'matches_original':True,'network_calls':0,'new_fit_calls':0,'sealed_reads':0}
