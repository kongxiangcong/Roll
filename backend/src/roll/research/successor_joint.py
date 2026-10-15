"""Archive paired scenario stress contracts beside one saved METHOD successor."""
import asyncio,hashlib,json,os,sys
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.research.shadow import fingerprint

METHOD=Path(__file__).with_name('reference')/'successor-joint-stress-v1.json'


class JointStressCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    idempotency_key:str=Field(min_length=1,max_length=128)
    controls_id:str=Field(min_length=1,max_length=128)
    entry_id:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


def code():
    return hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')+Path(__file__).with_name('successor_joint_process.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()


class SuccessorJointStresses:
    def __init__(self,stresses,controls,entries):
        self.controls=controls;self.entries=entries
        self.stresses=stresses;self.ledger=stresses.ledger;self.evidence=stresses.evidence;self.shadow=stresses.shadow
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_successor_joint_stresses(id TEXT PRIMARY KEY,stress_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(stress_id,key))')

    async def run(self,payload,output):
        with (output/'stderr.log').open('wb') as errors:
            process=await asyncio.create_subprocess_exec(sys.executable,'-I','-B',str(Path(__file__).with_name('successor_joint_process.py')),
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=errors,creationflags=0x08000000 if os.name=='nt' else 0)
            try:await asyncio.wait_for(process.communicate(json.dumps({**payload,'output_file':str(output/'result.json')}).encode()),timeout=payload['method']['worker_seconds'])
            except (asyncio.TimeoutError,asyncio.CancelledError):
                if process.returncode is None:process.kill()
                await process.wait();raise HTTPException(409,'SUCCESSOR_JOINT_STRESS_INTERRUPTED')
        file=output/'result.json'
        if process.returncode!=0 or not file.exists() or file.stat().st_size>payload['method']['maximum_output_bytes']:raise HTTPException(409,'SUCCESSOR_JOINT_STRESS_WORKER_FAILED '+output.name)
        return json.loads(file.read_text(encoding='utf-8'))

    async def create(self,stress_id,command):
        digest=fingerprint(command.model_dump())
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_successor_joint_stresses WHERE stress_id=? AND key=?',(stress_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=digest:raise HTTPException(409,'SUCCESSOR_JOINT_STRESS_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(prior[1])['joint_id'])
        method_body=METHOD.read_bytes();method=json.loads(method_body)
        method_archive=self.evidence.archive(method_body,'SUCCESSOR_JOINT_STRESS_METHOD')
        source=self.stresses.get(stress_id);original=self.shadow.checked_archive(source['source'])
        controls=self.controls.get(command.controls_id);entries=self.entries.get(command.entry_id)
        for item in (controls,entries):
            if any(item[key]!=source[key] for key in ('stress_id','successor_freeze_id','complete_protocol_fingerprint')) or item['source_manifest']!=source['archive'] or item['source_input']!=source['source']:
                raise HTTPException(409,'JOINT_STRESS_COMPONENT_PREFIX_MISMATCH')
        payload={'source':source,'controls':controls,'entries':entries,'control_input':self.shadow.checked_archive(controls['input_archive']),'method':method}
        body=encode(payload).encode()
        if len(body)>method['maximum_input_bytes']:raise HTTPException(422,'SUCCESSOR_JOINT_STRESS_INPUT_SIZE_LIMIT')
        input_archive=self.evidence.archive(body,'SUCCESSOR_JOINT_STRESS_INPUT')
        identifier=str(uuid4());output=self.evidence.directory/'successor-joint-stresses'/identifier;output.mkdir(parents=True)
        result=await self.run(payload,output)
        value={**result,'joint_id':identifier,'stress_id':stress_id,'source_manifest':source['archive'],'source_input':source['source'],
            'controls_id':controls['comparison_id'],'entry_id':entries['diagnostic_id'],'controls_manifest':controls['archive'],'entry_manifest':entries['archive'],'input_archive':input_archive,'method':method_archive,'method_fingerprint':code(),
            'complete_protocol_fingerprint':source['complete_protocol_fingerprint'],
            'successor_freeze_id':source['successor_freeze_id'],'recorded_at':now(),'basis':command.basis,
            'evidence_kind':'METHOD_CASE','system_usable':False,'capability':'NOT_GRANTED','complete_experiment_frozen':False}
        value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_JOINT_STRESS_MANIFEST')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT command_hash,value FROM research_successor_joint_stresses WHERE stress_id=? AND key=?',(stress_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=digest:raise HTTPException(409,'SUCCESSOR_JOINT_STRESS_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(prior[1])['joint_id'])
            db.execute('INSERT INTO research_successor_joint_stresses VALUES(?,?,?,?,?)',(identifier,stress_id,command.idempotency_key,digest,encode(value)));db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_joint_stresses WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_JOINT_STRESS_NOT_FOUND')
        value=json.loads(row[0])
        if self.shadow.checked_archive(value['archive'])!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'SUCCESSOR_JOINT_STRESS_MANIFEST_MISMATCH')
        source=self.stresses.get(value['stress_id'])
        if source['archive']!=value['source_manifest'] or source['source']!=value['source_input']:raise HTTPException(409,'SUCCESSOR_JOINT_STRESS_SOURCE_MISMATCH')
        if self.controls.get(value['controls_id'])['archive']!=value['controls_manifest'] or self.entries.get(value['entry_id'])['archive']!=value['entry_manifest']:raise HTTPException(409,'JOINT_STRESS_COMPONENT_MANIFEST_MISMATCH')
        for key in ('input_archive','method'):self.shadow.checked_archive(value[key])
        return value

    def listing(self,stress_id):
        with self.ledger.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM research_successor_joint_stresses WHERE stress_id=? ORDER BY rowid',(stress_id,))]
        return [self.get(identifier) for identifier in ids]

    async def replay(self,identifier):
        value=self.get(identifier)
        if value['method_fingerprint']!=code():raise HTTPException(409,'SUCCESSOR_JOINT_STRESS_REPLAY_CODE_CHANGED')
        payload=self.shadow.checked_archive(value['input_archive'])
        output=self.evidence.directory/'successor-joint-stresses'/('replay-'+str(uuid4()));output.mkdir(parents=True)
        result=await self.run(payload,output)
        if any(value.get(key)!=item for key,item in result.items()):raise HTTPException(409,'SUCCESSOR_JOINT_STRESS_REPLAY_MISMATCH')
        return {'matches_original':True,'network_calls':0,'new_fit_calls':0,'sealed_reads':0}
