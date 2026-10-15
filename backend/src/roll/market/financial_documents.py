"""Bounded local PDF derivations; archived originals and financial facts stay immutable."""
import asyncio,ctypes,hashlib,json,os
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field,model_validator
from pypdf import PdfReader
from roll.accounts.ledger import encode,now
from roll.agents.codex_process import Job,owner_alive,process_creation

VERSION='2.139.0'
REFERENCE=Path(__file__).with_name('docling-reference.json')


class ParseCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    first_page:int=Field(ge=1)
    last_page:int=Field(ge=1)
    idempotency_key:str=Field(min_length=1,max_length=128)
    basis:str=Field(min_length=1,max_length=2000)
    @model_validator(mode='after')
    def bounded(self):
        if not self.first_page<=self.last_page<self.first_page+8:raise ValueError('DOCLING_PAGE_BUDGET')
        return self


class FinancialDocuments:
    def __init__(self,evidence):
        self.evidence,self.ledger=evidence,evidence.ledger;self.worker=None;self.tasks={};self.cancel_requested=set()
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS financial_document_parses(id TEXT PRIMARY KEY,sha TEXT NOT NULL,key TEXT NOT NULL,command_hash TEXT NOT NULL,value TEXT NOT NULL,UNIQUE(sha,key))')
            for identifier,raw in db.execute('SELECT id,value FROM financial_document_parses').fetchall():
                value=json.loads(raw)
                if value['status']=='RUNNING' and not owner_alive(value):
                    value.update(status='INTERRUPTED',finished_at=now(),errors=['HOST_INTERRUPTED_NO_AUTOMATIC_RETRY'])
                    db.execute('UPDATE financial_document_parses SET value=? WHERE id=?',(encode(value),identifier))

    def source(self,sha):
        with self.ledger.connection() as db:
            facts=[json.loads(row[0]) for row in db.execute('SELECT value FROM financial_income_facts')]
        bindings=[f['fact_id'] for f in facts if (f.get('semantic_document') or {}).get('sha256')==sha]
        if not bindings:raise HTTPException(404,'FINANCIAL_DOCUMENT_NOT_BOUND_TO_SAVED_FACT')
        path=self.evidence.raw(sha)
        if path.stat().st_size>16*1024*1024:raise HTTPException(422,'DOCLING_PDF_BYTE_BUDGET')
        try:count=len(PdfReader(path).pages)
        except Exception:raise HTTPException(422,'FINANCIAL_DOCUMENT_UNREADABLE')
        return path,count,bindings

    def checked(self,value):
        self.evidence.raw(value['source_sha256'])
        for key in ('artifact','attempt_artifact'):
            if value.get(key):self.evidence.raw(value[key]['sha256'])
        return value

    def get(self,identifier):
        with self.ledger.connection() as db:row=db.execute('SELECT value FROM financial_document_parses WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'FINANCIAL_DOCUMENT_PARSE_NOT_FOUND')
        return self.checked(json.loads(row[0]))

    def listing(self,sha):
        _,count,bindings=self.source(sha)
        with self.ledger.connection() as db:rows=db.execute('SELECT value FROM financial_document_parses WHERE sha=? ORDER BY rowid DESC',(sha,)).fetchall()
        return {'source_sha256':sha,'page_count':count,'source_fact_ids':bindings,'parses':[self.checked(json.loads(r[0])) for r in rows],'network_calls':0,'system_usable':False}

    async def cancel(self,identifier):
        if identifier not in self.tasks:raise HTTPException(409,'DOCLING_RUN_NOT_ACTIVE_IN_THIS_HOST')
        self.cancel_requested.add(identifier);self.tasks[identifier].cancel()
        return {'parse_id':identifier,'cancellation_requested':True}

    def runtime(self):
        reference=json.loads(REFERENCE.read_text(encoding='utf-8'))
        executable=os.environ.get('ROLL_DOCLING_PYTHON')
        if not executable or reference.get('status')!='VERIFIED':raise ValueError('DOCLING_ISOLATED_RUNTIME_NOT_VERIFIED')
        required={'docling-slim','docling-ibm-models','rapidocr','torch','onnxruntime'}
        if not required.issubset(reference.get('packages',{})) or len(reference.get('artifacts',[]))<3 or not reference.get('licenses'):raise ValueError('DOCLING_RUNTIME_BINDINGS_INCOMPLETE')
        root=Path(executable).resolve().parent.parent
        for item in reference['artifacts']:
            path=(root/item['path']).resolve()
            if not path.is_relative_to(root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('DOCLING_RUNTIME_FINGERPRINT_MISMATCH')
        return executable,root,reference

    async def process(self,source,output,command):
        executable,root,reference=self.runtime()
        environment={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP'}}
        environment.update(HF_HOME=str(root/'cache/hf'),TORCH_HOME=str(root/'cache/torch'),XDG_CACHE_HOME=str(root/'cache'),DOCLING_ARTIFACTS_PATH=str(root/'models'),OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
        process=await asyncio.create_subprocess_exec(executable,'-I','-B',str(Path(__file__).with_name('docling_pdf_process.py')),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,env=environment,creationflags=0x08000000 if os.name=='nt' else 0)
        job=None
        try:
            job=Job(process.pid)
            limits=ctypes.create_string_buffer(144);ctypes.c_uint32.from_buffer(limits,16).value=0x2000|0x100|0x200|0x10
            ctypes.c_size_t.from_buffer(limits,48).value=(1<<min(2,os.cpu_count() or 1))-1
            ctypes.c_size_t.from_buffer(limits,112).value=2*1024**3;ctypes.c_size_t.from_buffer(limits,120).value=2*1024**3
            if not job.kernel.SetInformationJobObject(job.handle,9,limits,len(limits)):raise ctypes.WinError(ctypes.get_last_error())
            payload={**command.model_dump(),'source':str(source),'output':str(output/'result.json'),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'models':str(root/'models'),'source_page_count':len(PdfReader(source).pages),'reference':reference}
            await asyncio.wait_for(process.communicate(encode(payload).encode()),timeout=120)
            path=output/'result.json'
            if not path.exists() or path.stat().st_size>16*1024*1024:raise ValueError('DOCLING_OUTPUT_MISSING_OR_BYTE_BUDGET')
            return json.loads(path.read_text(encoding='utf-8'))
        finally:
            if job:job.terminate();job.close()
            elif process.returncode is None:process.kill()
            await process.wait()

    async def parse(self,sha,command):
        hashed=hashlib.sha256(encode(command.model_dump()).encode()).hexdigest()
        with self.ledger.connection() as db:prior=db.execute('SELECT command_hash,value FROM financial_document_parses WHERE sha=? AND key=?',(sha,command.idempotency_key)).fetchone()
        if prior:
            if prior[0]!=hashed:raise HTTPException(409,'DOCLING_IDEMPOTENCY_CONFLICT')
            return self.checked(json.loads(prior[1]))
        source,count,bindings=self.source(sha)
        if command.last_page>count:raise HTTPException(422,'DOCLING_PAGE_OUT_OF_RANGE')
        value={'parse_id':str(uuid4()),'source_sha256':sha,'source_fact_ids':bindings,'first_page':command.first_page,'last_page':command.last_page,'basis':command.basis,
            'status':'RUNNING','started_at':now(),'finished_at':None,'artifact':None,'attempt_artifact':None,'errors':[],'review_required':True,'parser_version':VERSION,
            'evidence_kind':'METHOD_CASE' if self.worker else 'REAL_LOCAL_PARSE','network_calls':0,'system_usable':False,'host_owner':{'pid':os.getpid(),'creation_ticks':process_creation(os.getpid())},
            'limits':{'pages':8,'pdf_bytes':16*1024*1024,'seconds':120,'memory_bytes':2*1024**3,'threads':2,'retries':0}}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            concurrent=db.execute('SELECT command_hash,value FROM financial_document_parses WHERE sha=? AND key=?',(sha,command.idempotency_key)).fetchone()
            if concurrent:
                if concurrent[0]!=hashed:raise HTTPException(409,'DOCLING_IDEMPOTENCY_CONFLICT')
                return self.checked(json.loads(concurrent[1]))
            if db.execute("SELECT 1 FROM financial_document_parses WHERE sha=? AND json_extract(value,'$.status')='RUNNING'",(sha,)).fetchone():raise HTTPException(409,'DOCLING_PARSE_ALREADY_RUNNING')
            db.execute('INSERT INTO financial_document_parses VALUES(?,?,?,?,?)',(value['parse_id'],sha,command.idempotency_key,hashed,encode(value)));db.commit()
        output=self.evidence.directory/'document-parses'/value['parse_id']
        try:
            output.mkdir(parents=True)
            self.tasks[value['parse_id']]=asyncio.current_task()
            payload=await (self.worker or self.process)(source,output,command)
            if payload.get('source_sha256')!=sha or payload.get('parser_version')!=VERSION:raise ValueError('DOCLING_OUTPUT_IDENTITY_MISMATCH')
            value['warnings']=payload.get('warnings',[])
            value['attempt_artifact']=self.evidence.archive(encode(payload).encode(),'DOCLING_PARSER_ATTEMPT',source_sha256=sha,evidence_kind=value['evidence_kind'],parser_version=VERSION)
            if payload.get('status') not in ('SUCCESS','PARTIAL_SUCCESS'):raise ValueError('DOCLING_CONVERSION_FAILED')
            document=payload.get('document',{})
            if not document.get('texts') and not document.get('tables'):raise ValueError('DOCLING_EMPTY_DERIVATION')
            for item in document.get('texts',[])+document.get('tables',[]):
                if not item.get('prov'):raise ValueError('DOCLING_PROVENANCE_MISSING')
                if any(not command.first_page<=p.get('page_no',0)<=command.last_page for p in item['prov']):raise ValueError('DOCLING_PAGE_PROVENANCE_OUT_OF_RANGE')
            for table in document.get('tables',[]):
                data=table.get('data',{})
                if not 0<=data.get('num_rows',0)<=500 or not 0<=data.get('num_cols',0)<=40 or len(data.get('table_cells',[]))>10000:raise ValueError('DOCLING_TABLE_SHAPE_BUDGET')
            value['artifact']=value['attempt_artifact']
            represented={p['page_no'] for item in document.get('texts',[])+document.get('tables',[]) for p in item['prov']}
            missing=sorted(set(range(command.first_page,command.last_page+1))-represented)
            warnings=list(payload.get('warnings',[]))
            if missing:warnings.append('PAGES_WITHOUT_TEXT_OR_TABLE:'+','.join(map(str,missing)))
            value.update(status='PARTIAL' if missing or payload['status']=='PARTIAL_SUCCESS' else 'COMPLETE',conversion_status=payload['status'],finished_at=now(),warnings=warnings,confidence=payload.get('confidence'),runtime=payload.get('runtime',{}))
        except (Exception,asyncio.CancelledError) as error:
            value.update(status='CANCELLED' if isinstance(error,asyncio.CancelledError) else 'FAILED',finished_at=now(),errors=[str(error)[:300] if isinstance(error,ValueError) else type(error).__name__])
            if isinstance(error,asyncio.CancelledError) and value['parse_id'] not in self.cancel_requested:
                with self.ledger.connection() as db:db.execute('UPDATE financial_document_parses SET value=? WHERE id=?',(encode(value),value['parse_id']))
                raise
        finally:self.tasks.pop(value['parse_id'],None);self.cancel_requested.discard(value['parse_id'])
        with self.ledger.connection() as db:db.execute('UPDATE financial_document_parses SET value=? WHERE id=?',(encode(value),value['parse_id']))
        return value
