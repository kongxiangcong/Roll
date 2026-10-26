"""Audited METHOD threshold runs beside, never inside, training partitions."""
import asyncio,hashlib,json,os,sys
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field
from roll.accounts.ledger import encode,now
from roll.agents.codex_process import owner_alive
from roll.research.shadow import fingerprint

METHOD=Path(__file__).with_name('reference')/'successor-threshold-stress-v1.json'
START='SUCCESSOR_METHOD_THRESHOLD_STARTED';FINISH='SUCCESSOR_METHOD_THRESHOLD_FINISHED';INTERRUPT='SUCCESSOR_METHOD_THRESHOLD_INTERRUPTED'


class ThresholdCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)


def code():
    return hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')+Path(__file__).with_name('successor_threshold_process.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()


class SuccessorThresholdStresses:
    def __init__(self,stresses):
        self.stresses=stresses;self.protocols=stresses.protocols;self.registry=self.protocols.registry;self.ledger=stresses.ledger;self.evidence=stresses.evidence;self.shadow=stresses.shadow
        with self.ledger.connection() as db:db.execute('CREATE TABLE IF NOT EXISTS research_successor_threshold_runs(id TEXT PRIMARY KEY,stress_id TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(stress_id,key))')
        with self.ledger.connection() as db:runs=[json.loads(r[0]) for r in db.execute("SELECT value FROM research_successor_threshold_runs WHERE json_extract(value,'$.status')='RUNNING'")]
        for run in runs:
            if not owner_alive(run):self.finish(run['diagnostic_id'],'ABORTED','Original METHOD host no longer verifiable; no numerical result admitted',recovering=True)

    def manifest(self,protocol_id,db=None):
        if db is None:
            with self.ledger.connection() as connection:return self.manifest(protocol_id,connection)
        records={r['protocol_id']:r for row in db.execute('SELECT value FROM research_protocols') if (r:=json.loads(row[0]))}
        if protocol_id not in records:raise HTTPException(404,'METHOD_ATTEMPT_PROTOCOL_NOT_FOUND')
        family=self.registry.family(protocol_id,db);lineage=[];current=records[protocol_id]
        while True:
            lineage.append(current['protocol_id'])
            if not current['predecessor_id']:break
            current=records[current['predecessor_id']]
        starts={};completed={}
        for row in db.execute('SELECT value FROM research_events ORDER BY ordinal'):
            event=json.loads(row[0])
            if event['protocol_id'] not in family:continue
            if event['action']==START:starts[event['method_attempt_id']]=event
            elif event['action'] in (FINISH,INTERRUPT):completed[event['method_attempt_id']]=event
        attempts=[{**start,'status':completed[key]['status'] if key in completed else 'RUNNING','completion':completed.get(key)} for key,start in starts.items()]
        return {'lineage':list(reversed(lineage)),'family_protocol_ids':family,'attempts':attempts,'attempt_ids':list(starts),
            'data_scope':'METHOD_DECLARED_SLOTS','partition':None,'training_attempt_manifest_separate':True,'fit_budget_increased':False}

    async def run(self,payload,output):
        with (output/'stderr.log').open('wb') as errors:
            process=await asyncio.create_subprocess_exec(sys.executable,'-I','-B',str(Path(__file__).with_name('successor_threshold_process.py')),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=errors,creationflags=0x08000000 if os.name=='nt' else 0)
            try:await asyncio.wait_for(process.communicate(json.dumps({**payload,'output_file':str(output/'result.json')}).encode()),timeout=payload['method']['worker_seconds'])
            except (asyncio.TimeoutError,asyncio.CancelledError):
                if process.returncode is None:process.kill()
                await process.wait();raise
        path=output/'result.json'
        if process.returncode!=0 or not path.exists() or path.stat().st_size>payload['method']['maximum_output_bytes']:raise HTTPException(409,'THRESHOLD_WORKER_FAILED '+output.name)
        return json.loads(path.read_text(encoding='utf-8'))

    def finish(self,identifier,status,reason,result=None,*,recovering=False):
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT value FROM research_successor_threshold_runs WHERE id=?',(identifier,)).fetchone();value=json.loads(row[0])
            if value['status']!='RUNNING':
                if recovering:return value
                raise HTTPException(409,'THRESHOLD_RUN_ALREADY_TERMINAL')
            cases={c['entry_threshold']:c for c in result['scenarios']} if result else {}
            terminal='INTERRUPTED' if status=='ABORTED' else status
            for attempt in value['method_attempts']:
                attempt.update(status=terminal,finished_at=now(),reason=reason)
                self.registry.event(value['protocol_id'],INTERRUPT if status=='ABORTED' else FINISH,db=db,method_attempt_id=attempt['method_attempt_id'],diagnostic_id=identifier,status=terminal,reason=reason,
                    result_fingerprint=fingerprint(cases[attempt['entry_threshold']]) if attempt['entry_threshold'] in cases else None)
            value.update(status=status,finished_at=now(),reason=reason,method_attempt_manifest=self.manifest(value['protocol_id'],db))
            if result:value.update(result)
            else:
                for key in ('scenarios','G5_status','base_matches_saved_prefix'):value.pop(key,None)
            value['archive']=self.evidence.archive(encode(value).encode(),'SUCCESSOR_THRESHOLD_TERMINAL_RUN',db=db)
            db.execute('UPDATE research_successor_threshold_runs SET value=? WHERE id=?',(encode(value),identifier));db.commit()
        return value

    async def create(self,stress_id,command):
        digest=fingerprint(command.model_dump())
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM research_successor_threshold_runs WHERE stress_id=? AND key=?',(stress_id,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=digest:raise HTTPException(409,'THRESHOLD_IDEMPOTENCY_CONFLICT')
            saved=json.loads(prior[1])
            if saved['status']!='SUCCEEDED':raise HTTPException(409,{'code':'THRESHOLD_ATTEMPT_PRESERVED_NO_DUPLICATE','diagnostic_id':saved['diagnostic_id'],'status':saved['status']})
            return self.get(saved['diagnostic_id'])
        method_body=METHOD.read_bytes();method=json.loads(method_body);method_archive=self.evidence.archive(method_body,'SUCCESSOR_THRESHOLD_METHOD')
        source=self.stresses.get(stress_id);original=self.shadow.checked_archive(source['source']);protocol=original['protocol'];payload={'source':source,'input':original,'method':method};body=encode(payload).encode()
        if len(body)>method['maximum_input_bytes']:raise HTTPException(422,'THRESHOLD_INPUT_SIZE_LIMIT')
        input_archive=self.evidence.archive(body,'SUCCESSOR_THRESHOLD_INPUT');identifier=str(uuid4());recorded=now()
        attempts=[{'method_attempt_id':str(uuid4()),'diagnostic_id':identifier,'category':'THRESHOLD','entry_threshold':rate,'status':'RUNNING','partition':None,
            'data_scope':'METHOD_DECLARED_SLOTS','started_at':recorded,'host_owner':self.registry.owner,'source_prefix_fingerprint':source['input_prefix_fingerprint'],
            'method_sha256':method_archive['sha256'],'rate_fingerprint':fingerprint([rate,source['input_prefix_fingerprint'],method_archive['sha256']])} for rate in method['grid']]
        value={'diagnostic_id':identifier,'stress_id':stress_id,'protocol_id':protocol['protocol_id'],'status':'RUNNING','host_owner':self.registry.owner,'recorded_at':recorded,
            'method_attempts':attempts,'research_attempt_manifest':self.registry.attempt_manifest(protocol['protocol_id']),
            'source_manifest':source['archive'],'source_input':source['source'],'input_archive':input_archive,'method':method_archive,'method_fingerprint':code(),
            'successor_freeze_id':source['successor_freeze_id'],'complete_protocol_fingerprint':source['complete_protocol_fingerprint'],'basis':command.basis,
            'evidence_kind':'METHOD_CASE','capability':'NOT_GRANTED','system_usable':False,'complete_experiment_frozen':False,'new_fit_calls':0,'sealed_reads':0,'network_calls':0}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT id FROM research_successor_threshold_runs WHERE stress_id=? AND key=?',(stress_id,command.idempotency_key)).fetchone():raise HTTPException(409,'THRESHOLD_CONCURRENT_REQUEST_PRESERVED')
            db.execute('INSERT INTO research_successor_threshold_runs VALUES(?,?,?,?,?)',(identifier,stress_id,command.idempotency_key,digest,encode(value)))
            for attempt in attempts:self.registry.event(protocol['protocol_id'],START,db=db,**attempt)
            db.commit()
        try:
            output=self.evidence.directory/'successor-threshold-stress'/identifier;output.mkdir(parents=True)
            result=await self.run(payload,output)
            return self.finish(identifier,'SUCCEEDED','All three fixed METHOD rates saved; no winner or qualification',result)
        except asyncio.CancelledError:
            self.finish(identifier,'ABORTED','Host cancelled bounded METHOD grid; per-rate outcome not admitted');raise
        except Exception as error:
            self.finish(identifier,'FAILED','Bounded METHOD grid failed; per-rate outcome not admitted: '+type(error).__name__)
            raise HTTPException(409,{'code':'THRESHOLD_RUN_FAILED','diagnostic_id':identifier}) from error

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM research_successor_threshold_runs WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'SUCCESSOR_THRESHOLD_RUN_NOT_FOUND')
        value=json.loads(row[0])
        if value.get('archive') and self.shadow.checked_archive(value['archive'])!={k:v for k,v in value.items() if k!='archive'}:raise HTTPException(409,'THRESHOLD_MANIFEST_MISMATCH')
        source=self.stresses.get(value['stress_id'])
        if source['archive']!=value['source_manifest'] or source['source']!=value['source_input']:raise HTTPException(409,'THRESHOLD_SOURCE_MISMATCH')
        for key in ('input_archive','method'):self.shadow.checked_archive(value[key])
        return value

    def listing(self,stress_id):
        with self.ledger.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM research_successor_threshold_runs WHERE stress_id=? ORDER BY rowid',(stress_id,))]
        return [self.get(identifier) for identifier in ids]

    async def replay(self,identifier):
        value=self.get(identifier)
        if value['status']!='SUCCEEDED' or value['method_fingerprint']!=code():raise HTTPException(409,'THRESHOLD_REPLAY_NOT_ADMITTED_OR_CODE_CHANGED')
        payload=self.shadow.checked_archive(value['input_archive']);output=self.evidence.directory/'successor-threshold-stress'/('replay-'+str(uuid4()));output.mkdir(parents=True)
        result=await self.run(payload,output)
        if any(value.get(key)!=item for key,item in result.items()):raise HTTPException(409,'THRESHOLD_REPLAY_MISMATCH')
        return {'matches_original':True,'new_method_attempts':0,'new_fit_calls':0,'sealed_reads':0,'network_calls':0}
