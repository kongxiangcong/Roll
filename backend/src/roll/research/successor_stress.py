"""Immutable cost sensitivity around saved METHOD prefixes, never a G5 grant."""
import asyncio,hashlib,json,os,sys
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from roll.accounts.ledger import encode,now
from roll.research.shadow import fingerprint

METHOD=Path(__file__).with_name('reference')/'successor-cost-stress-v1.json'


class SuccessorStresses:
    def __init__(self,protocols):
        self.protocols=protocols;self.ledger=protocols.ledger;self.evidence=protocols.evidence;self.shadow=protocols.shadow
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_successor_cost_stresses(id TEXT PRIMARY KEY,freeze_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(freeze_id,key))')

    async def run(self,payload,output):
        with (output/'stderr.log').open('wb') as errors:
            process=await asyncio.create_subprocess_exec(sys.executable,'-I','-B',str(Path(__file__).with_name('successor_stress_process.py')),
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=errors,creationflags=0x08000000 if os.name=='nt' else 0)
            try:await asyncio.wait_for(process.communicate(json.dumps({**payload,'output_file':str(output/'result.json')}).encode()),timeout=payload['method']['worker_seconds'])
            except (asyncio.TimeoutError,asyncio.CancelledError):
                if process.returncode is None:process.kill()
                await process.wait();raise HTTPException(409,'SUCCESSOR_STRESS_INTERRUPTED')
        file=output/'result.json'
        if process.returncode!=0 or not file.exists() or file.stat().st_size>payload['method']['maximum_output_bytes']:raise HTTPException(409,'SUCCESSOR_STRESS_WORKER_FAILED '+output.name)
        return json.loads(file.read_text(encoding='utf-8'))

    async def create(self,freeze_id,command):
        digest=fingerprint(command.model_dump())
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_successor_cost_stresses WHERE freeze_id=? AND key=?',(freeze_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=digest:raise HTTPException(409,'SUCCESSOR_STRESS_IDEMPOTENCY_CONFLICT')
            return self.get(json.loads(prior[1])['stress_id'])
        method_body=METHOD.read_bytes();method=json.loads(method_body)
        method_archive=self.evidence.archive(method_body,'SUCCESSOR_COST_STRESS_METHOD',evidence_kind='METHOD_CASE')
        if not 1<=command.expected_revision<=method['maximum_frames']:raise HTTPException(422,'SUCCESSOR_COST_STRESS_PREFIX_LIMIT')
        protocol=self.protocols.get(freeze_id)
        if protocol['complete_protocol_fingerprint']!=command.expected_complete_protocol_fingerprint:raise HTTPException(409,'SUCCESSOR_STRESS_PROTOCOL_MISMATCH')
        frozen=self.protocols.successor.get(freeze_id)
        with self.ledger.connection() as db:
            rows=[(number,digest,json.loads(raw)) for number,digest,raw in db.execute('SELECT revision,command_hash,value FROM research_successor_frames WHERE freeze_id=? AND revision<=? ORDER BY revision',(freeze_id,command.expected_revision))]
        if len(rows)!=command.expected_revision:raise HTTPException(409,'SUCCESSOR_STRESS_PREFIX_UNAVAILABLE')
        if any(row[2].get('command',{}).get('evidence_kind')!='METHOD_CASE' for row in rows):raise HTTPException(409,'SUCCESSOR_STRESS_ONLY_METHOD_PREFIX')
        previous=self.shadow.get(protocol['predecessor_freeze_id'])
        payload={'frozen':frozen,'protocol':protocol,'rows':rows,'method':method,'inherited_shadow_code':previous['fingerprints']['shadow_code']}
        body=encode(payload).encode()
        if len(body)>method['maximum_input_bytes']:raise HTTPException(422,'SUCCESSOR_STRESS_INPUT_SIZE_LIMIT')
        source=self.evidence.archive(body,'SUCCESSOR_COST_STRESS_INPUT',evidence_kind='METHOD_CASE')
        identifier=str(uuid4());output=self.evidence.directory/'successor-cost-stress'/identifier;output.mkdir(parents=True)
        result=await self.run(payload,output)
        code_hash=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')+Path(__file__).with_name('successor_stress_process.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        value={**result,'stress_id':identifier,'successor_freeze_id':freeze_id,'shadow_revision':command.expected_revision,
            'complete_protocol_fingerprint':protocol['complete_protocol_fingerprint'],'successor_fingerprint':frozen['successor_fingerprint'],
            'method_fingerprint':code_hash,'method':method_archive,'source':source,'recorded_at':now(),'basis':command.basis,
            'evidence_kind':'METHOD_CASE','system_usable':False,'capability':'NOT_GRANTED','complete_experiment_frozen':False,
            'confirmation_pass_look':False,'attempt_manifest':self.protocols.registry.attempt_manifest(protocol['protocol_id'])}
        value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_COST_STRESS_MANIFEST',evidence_kind='METHOD_CASE')
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT command_hash,value FROM research_successor_cost_stresses WHERE freeze_id=? AND key=?',(freeze_id,command.idempotency_key)).fetchone()
            if prior:
                if prior[0]!=digest:raise HTTPException(409,'SUCCESSOR_STRESS_IDEMPOTENCY_CONFLICT')
                return self.get(json.loads(prior[1])['stress_id'])
            db.execute('INSERT INTO research_successor_cost_stresses VALUES(?,?,?,?,?)',(identifier,freeze_id,command.idempotency_key,digest,encode(value)));db.commit()
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_cost_stresses WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_COST_STRESS_NOT_FOUND')
        value=json.loads(row[0])
        if self.shadow.checked_archive(value['archive'])!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'SUCCESSOR_COST_STRESS_MANIFEST_MISMATCH')
        for key in ('source','method'):self.shadow.checked_archive(value[key])
        return value

    def listing(self,freeze_id):
        with self.ledger.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM research_successor_cost_stresses WHERE freeze_id=? ORDER BY rowid',(freeze_id,))]
        return [self.get(identifier) for identifier in ids]

    async def replay(self,identifier):
        value=self.get(identifier);payload=self.shadow.checked_archive(value['source'])
        code_hash=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')+Path(__file__).with_name('successor_stress_process.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if value['method_fingerprint']!=code_hash:raise HTTPException(409,'SUCCESSOR_STRESS_REPLAY_CODE_CHANGED')
        output=self.evidence.directory/'successor-cost-stress'/('replay-'+str(uuid4()));output.mkdir(parents=True)
        result=await self.run(payload,output)
        if any(value.get(key)!=item for key,item in result.items()):raise HTTPException(409,'SUCCESSOR_STRESS_REPLAY_MISMATCH')
        return {'stress_id':identifier,'matches_original':True,'network_calls':0,'system_usable':False,'capability':'NOT_GRANTED'}
