"""DeepSeek tasks: one explicit provider, bounded host tools, local audit only."""
import hashlib
import json
import os
from pathlib import Path
from typing import Callable
import threading
import time
from importlib.metadata import version
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from roll.accounts.ledger import encode, now
from roll.agents.settings import AgentQuestion, check_retry, insert_run, HOST_LIMITS, require_current_backend
from roll.agents.codex_process import owner_alive, process_creation, recover_directory

MODEL='deepseek-flash'
ENDPOINT='https://api.deepseek.com'
TOOLS=['roll_read_evidence','roll_read_source']
LIMITS={**HOST_LIMITS,'total_calls':19,
        'model_calls':5,'max_output_tokens':2048,'model_input_bytes':131072,
        'model_response_bytes':65536,'model_total_response_bytes':262144}


DeepSeekQuestion=AgentQuestion


class DeepSeekEvidence:
    def __init__(self,evidence,endpoint=None,input_observer=None,*,archive_reuse_check:Callable[[set[str]],bool]):
        if endpoint is not None:
            from urllib.parse import urlparse
            parsed=urlparse(endpoint)
            if os.environ.get('ROLL_ENV')!='test' or parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.path:
                raise ValueError('DeepSeek method endpoint requires test-only loopback HTTP')
        self.evidence=evidence
        self.input_observer=input_observer
        self.archive_reuse_check=archive_reuse_check
        self.endpoint=endpoint or ENDPOINT
        self.method=endpoint is not None
        self.active={}
        self.lock=threading.Lock()
        with evidence.ledger.connection() as db:
            for row in db.execute('SELECT value FROM retrieval_runs').fetchall():
                run=json.loads(row[0])
                if run.get('backend')=='DEEPSEEK' and run.get('status')=='INTERRUPTED' and run.get('process',{}).get('task_root'):
                    run['recovery_cleanup']=recover_directory(run)
                    db.execute('UPDATE retrieval_runs SET value=? WHERE id=?',(encode(run),run['run_id']))

    def save(self,run):
        snapshot=run.pop('_snapshot',None)
        with self.evidence.ledger.connection() as db:
            if snapshot:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO market_evidence_snapshots VALUES(?,?,?)',(snapshot['snapshot_id'],run['run_id'],encode(snapshot)))
            db.execute('UPDATE retrieval_runs SET value=? WHERE id=?',(encode(run),run['run_id']))
            db.commit()

    def start(self,request_id,command,selection=None):
        require_current_backend('DEEPSEEK')
        request=self.evidence.get('data_requests',request_id)
        check_retry(self.evidence,request_id,command)
        try:
            timeout=int(os.environ.get('ROLL_DEEPSEEK_TIMEOUT_SECONDS',120))
            if not 1<=timeout<=120:raise ValueError()
        except ValueError:
            raise HTTPException(503,{'code':'INVALID_DEEPSEEK_HOST_LIMIT'})
        limits={**LIMITS,'timeout_seconds':timeout,'http_calls':min(6,request['max_calls'])}
        versions={name:version(name) for name in ['openai-agents','openai','httpx2']}
        code={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
        settings={'endpoint':self.endpoint,'model':MODEL,'protocol':'RESPONSES_STATELESS',
            'allowed_tools':TOOLS,'tracing_disabled':True,'skills':False,'plugins':False,
            'mcp':False,'handoffs':[],'store':None,'auto_previous_response_id':False,
            'retries':0,'host_code_hashes':code,'sdk_runtime_version':versions,'limits':limits}
        settings['research_input_audit_enabled']=self.input_observer is not None
        run={'run_id':str(uuid4()),'request_id':request_id,'backend':'DEEPSEEK','model':MODEL,
            'resolved_model':None,'retry_of':command.retry_of,'question':command.question,
            'status':'RUNNING','started_at':now(),'finished_at':None,'formal_judgment':'DISABLED',
            'config_fingerprint':hashlib.sha256(encode(settings).encode()).hexdigest(),
            'runtime_audit':settings,'sdk_runtime_version':versions,'allowed_tools':TOOLS,
            'limits':limits,'tools':[],'archives':[],'gaps':[],'candidates':[],
            'host_owner':{'pid':os.getpid(),'creation_ticks':process_creation(os.getpid())},
            'evidence_kind':'METHOD_CASE_DEEPSEEK' if self.method else
                'REAL_DEEPSEEK_METHOD_CASE_SOURCE' if self.evidence.transport is not None else 'REAL_DEEPSEEK_TASK'}
        with self.lock:
            if self.active:raise HTTPException(409,{'code':'DEEPSEEK_CONCURRENCY_LIMIT'})
            with self.evidence.ledger.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                insert_run(self.evidence,db,run,selection)
                db.commit()
            cancel=threading.Event()
            self.active[run['run_id']]=cancel
        key=os.environ.get('DEEPSEEK_API_KEY');credential_error=None
        try:
            configured=os.environ.get('ROLL_DEEPSEEK_API_KEY_FILE')
            if not key and configured:
                path=Path(configured)
                if path.stat().st_size>4096:raise ValueError('DEEPSEEK_AUTH_FILE_TOO_LARGE')
                key=path.read_text(encoding='utf-8').strip()
        except Exception:credential_error='DEEPSEEK_AUTH_INVALID'
        threading.Thread(target=self.execute,args=(run,request,cancel,key,credential_error),daemon=True).start()
        return json.loads(encode(run))

    def execute(self,run,request,cancel,key,credential_error):
        try:
            if credential_error:raise ValueError(credential_error)
            if not key:
                run.update(status='UNAVAILABLE',error={'code':'DEEPSEEK_AUTH_NOT_CONFIGURED',
                    'message':'尚未配置 DeepSeek API 凭据。管理员可设置 DEEPSEEK_API_KEY 或明确的 ROLL_DEEPSEEK_API_KEY_FILE；已有网页订阅不证明 API 权限。'})
                return
            if not 1<=len(key)<=4096 or '\n' in key or '\r' in key:
                raise ValueError('DEEPSEEK_AUTH_INVALID')
            # The method server accepts only a synthetic key; real credentials never go to a fixture.
            if self.method and key!='ROLL_METHOD_CASE_ONLY':
                raise ValueError('METHOD_ENDPOINT_REQUIRES_SYNTHETIC_CREDENTIAL')
            from roll.agents.deepseek_process import execute
            execute(self,run,request,cancel,key)
        except Exception as error:
            code=str(error) if isinstance(error,ValueError) else 'DEEPSEEK_HOST_ERROR'
            run.update(status='FAILED',error={'code':code,'type':type(error).__name__})
        finally:
            if cancel.is_set() and run['status'] not in {'CANCELLED','TIMED_OUT'}:
                run['status']='CANCELLED';run.pop('_snapshot',None);run.pop('snapshot_id',None)
            run['finished_at']=now()
            with self.lock:
                self.save(run);self.active.pop(run['run_id'],None)

    def cancel(self,run_id):
        run=self.evidence.get('retrieval_runs',run_id)
        if run['backend']!='DEEPSEEK':raise HTTPException(409,{'code':'NOT_DEEPSEEK_RUN'})
        with self.lock:
            event=self.active.get(run_id)
            if event:event.set()
        return {'run_id':run_id,'cancel_requested':event is not None,'status':run['status']}

    def close(self):
        with self.lock:
            for event in self.active.values():event.set()
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            with self.lock:
                if not self.active:return
            time.sleep(.05)
