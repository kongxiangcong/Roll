"""Finite Codex tasks. The host owns acquisition, archives and publication."""
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from roll.accounts.ledger import encode, now
from roll.agents.settings import AgentQuestion, check_retry, insert_run, HOST_LIMITS

SDK_VERSION = '0.161.0'
MODEL = 'gpt-6.1-sol'
LIMITS = {**HOST_LIMITS,'runtime_operations':8,'total_calls':22}
TOOLS = ['roll_read_evidence', 'roll_read_source', 'clock__curr_time']
CONFIG = '''approval_policy = "never"
approvals_reviewer = "user"
sandbox_mode = "read-only"
allow_login_shell = false
project_doc_max_bytes = 0
project_doc_fallback_filenames = []
web_search = "disabled"
mcp_servers = {}
[agents]
enabled = false
[skills]
include_instructions = false
[skills.bundled]
enabled = false
[cloud.skills]
enabled = false
[features]
shell_tool = false
shell_snapshot = false
hooks = false
plugins = false
remote_plugin = false
apps = false
tool_suggest = false
skill_mcp_dependency_install = false
multi_agent = false
multi_agent_v2 = false
goals = false
memories = false
view_image = false
image_generation = false
browser_use = false
browser_use_external = false
in_app_browser = false
computer_use = false
code_mode = false
code_mode_only = false
code_mode_host = true
[analytics]
enabled = false
[feedback]
enabled = false
[otel]
exporter = "none"
trace_exporter = "none"
metrics_exporter = "none"
log_user_prompt = false
'''


CodexQuestion=AgentQuestion


class CodexEvidence:
    def __init__(self, evidence, worker=None, input_observer=None):
        if worker is not None and os.environ.get('ROLL_ENV') != 'test':
            raise ValueError('External worker injection requires ROLL_ENV=test')
        self.worker = worker
        self.evidence = evidence
        self.input_observer = input_observer
        self.active = {}
        self.lock = threading.Lock()
        from roll.agents.codex_process import recover_directory
        with evidence.ledger.connection() as db:
            for row in db.execute('SELECT value FROM retrieval_runs').fetchall():
                run=json.loads(row[0])
                if run.get('backend')=='CODEX' and run.get('status')=='INTERRUPTED' and run.get('process',{}).get('task_root'):
                    run['recovery_cleanup']=recover_directory(run)
                    db.execute('UPDATE retrieval_runs SET value=? WHERE id=?',(encode(run),run['run_id']))

    def save(self, run):
        snapshot = run.pop('_snapshot', None)
        with self.evidence.ledger.connection() as db:
            if snapshot:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO market_evidence_snapshots VALUES(?,?,?)',
                    (snapshot['snapshot_id'], run['run_id'], encode(snapshot)))
            db.execute('UPDATE retrieval_runs SET value=? WHERE id=?', (encode(run), run['run_id']))
            db.commit()

    def start(self, request_id, command, selection=None):
        request = self.evidence.get('data_requests', request_id)
        check_retry(self.evidence,request_id,command)
        with self.lock:
            if self.active:
                raise HTTPException(409, {'code': 'CODEX_CONCURRENCY_LIMIT'})
            model = os.environ.get('ROLL_CODEX_MODEL', MODEL)
            try:
                timeout = int(os.environ.get('ROLL_CODEX_TIMEOUT_SECONDS', LIMITS['timeout_seconds']))
                if not 1 <= timeout <= LIMITS['timeout_seconds']:
                    raise ValueError()
            except ValueError:
                raise HTTPException(503, {'code': 'INVALID_CODEX_HOST_LIMIT'})
            limits = {**LIMITS, 'timeout_seconds': timeout,
                      'http_calls': min(LIMITS['http_calls'], request['max_calls'])}
            code_hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                for p in Path(__file__).parent.glob('codex_*.py')}
            fingerprint = hashlib.sha256(encode({'config': CONFIG, 'model': model,
                'limits': limits, 'tools': TOOLS, 'sdk': SDK_VERSION,'host_code_hashes':code_hashes}).encode()).hexdigest()
            run = {'run_id': str(uuid4()), 'request_id': request_id, 'backend': 'CODEX',
                'model': model, 'resolved_model': None, 'config_fingerprint': fingerprint,
                'sdk_runtime_version': {'openai-codex': SDK_VERSION, 'openai-codex-cli-bin': SDK_VERSION},
                'allowed_tools': TOOLS, 'allowed_operations': ['V8_PURE_COMPUTATION', 'FUNCTIONS_EXEC', 'FUNCTIONS_WAIT'],
                'host_code_hashes': code_hashes, 'limits': limits, 'status': 'RUNNING',
                'question': command.question, 'retry_of':command.retry_of, 'started_at': now(), 'finished_at': None,
                'tools': [], 'archives': [], 'gaps': [], 'candidates': [],
                'evidence_kind': 'METHOD_CASE_CODEX' if self.worker else
                    'REAL_CODEX_METHOD_CASE_SOURCE' if self.evidence.transport is not None else 'REAL_CODEX_TASK',
                'formal_judgment': 'DISABLED'}
            from roll.agents.codex_process import process_creation,owner_alive
            run['host_owner']={'pid':os.getpid(),'creation_ticks':process_creation(os.getpid())}
            with self.evidence.ledger.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                insert_run(self.evidence,db,run,selection)
                db.commit()
            cancel = threading.Event()
            self.active[run['run_id']] = cancel
        # Capture only the explicit credential's necessary fields in private memory.
        # Neither credentials nor their hashes are part of the public task record.
        credential=None;credential_error=None
        try:
            configured=os.environ.get('ROLL_CODEX_AUTH_FILE')
            if not configured or not Path(configured).is_file():credential_error='CODEX_AUTH_NOT_CONFIGURED'
            else:
                content=json.loads(Path(configured).read_text(encoding='utf-8'))
                if content.get('auth_mode')!='chatgpt' or not content.get('tokens'):credential_error='CHATGPT_AUTH_REQUIRED'
                else:credential={'auth_mode':'chatgpt','tokens':{k:v for k,v in content['tokens'].items()
                    if k in {'access_token','id_token','refresh_token','account_id'}},'last_refresh':content.get('last_refresh')}
        except Exception:credential_error='CODEX_AUTH_INVALID'
        threading.Thread(target=self.execute, args=(run, request, cancel,credential,credential_error), daemon=True).start()
        return json.loads(encode(run))

    def execute(self, run, request, cancel,credential,credential_error):
        try:
            if credential_error:
                run.update(status='UNAVAILABLE',error={'code':credential_error})
                return
            from roll.agents.codex_process import execute
            execute(self, run, request, cancel, credential)
        except Exception as error:
            run.update(status='FAILED', error={'code': 'CODEX_HOST_ERROR', 'type': type(error).__name__})
            if getattr(error, 'filename', None):
                run['error']['file_kind'] = Path(error.filename).name
        finally:
            if cancel.is_set() and run['status'] not in {'CANCELLED','TIMED_OUT'}:
                run['status']='CANCELLED'
                run.pop('_snapshot',None);run.pop('snapshot_id',None)
            run['finished_at'] = now()
            with self.lock:
                self.save(run)
                self.active.pop(run['run_id'], None)

    def cancel(self, run_id):
        run = self.evidence.get('retrieval_runs', run_id)
        if run['backend'] != 'CODEX':
            raise HTTPException(409, {'code': 'NOT_CODEX_RUN'})
        with self.lock:
            event = self.active.get(run_id)
            if event:
                event.set()
        return {'run_id': run_id, 'cancel_requested': event is not None, 'status': run['status']}

    def close(self):
        with self.lock:
            for event in self.active.values():
                event.set()
        deadline = time.monotonic()+15
        while time.monotonic()<deadline:
            with self.lock:
                if not self.active:
                    return
            time.sleep(.05)
