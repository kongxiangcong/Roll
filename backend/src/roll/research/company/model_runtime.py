"""Synchronous bounded model attempt; job scheduling belongs to the shared worker."""
import json
import hashlib
import os
import threading
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from roll.accounts.ledger import encode, now
from .service import fail, record, verified


class AnalysisRuntime:
    worker = None

    def __init__(self, research):
        self.research = research
        self.worker = research.analysis_worker

    def save(self, run):
        value = record({k: v for k, v in run.items() if k != 'content_sha256'})
        with self.research.ledger.connection() as db:
            db.execute('INSERT INTO company_research_analysis_runs VALUES(?,?,?) ON CONFLICT(run_id) DO UPDATE SET value=excluded.value',
                       (run['run_id'], run['company_id'], encode(value)))

    def execute(self, input_id, cancel=None, timeout_seconds=180):
        from roll.agents.codex_process import execute, owner_alive, process_creation
        packet = self.research.analysis_input(input_id)
        with self.research.transaction() as db:
            for row in db.execute('SELECT value FROM company_research_analysis_runs WHERE company_id=?', (packet['company_id'],)):
                prior = verified(json.loads(row[0]))
                if prior['status'] == 'RUNNING' and owner_alive(prior):
                    fail('ANALYSIS_ALREADY_RUNNING', 'A bounded model attempt already owns this company input', 409)
            run = {'run_id': str(uuid4()), 'company_id': packet['company_id'], 'input_id': input_id,
                   'task_kind': 'COMPANY_OPERATING_ANALYSIS', 'backend': 'CODEX', 'model': os.environ.get('ROLL_CODEX_MODEL', 'gpt-6.1-sol'),
                   'status': 'RUNNING', 'started_at': now(), 'archives': [], 'tools': [],
                   'evidence_kind': 'METHOD_CASE' if self.worker else 'REAL_MODEL_ANALYSIS',
                   'formal_authority': False, 'limits': {'timeout_seconds': min(180, max(1, timeout_seconds)), 'runtime_operations': 8, 'tool_calls': 0},
                   'host_owner': {'pid': os.getpid(), 'creation_ticks': process_creation(os.getpid())}}
            root = Path(__file__).parents[2]
            files = ['research/company/analysis.py', 'research/company/candidates.py', 'research/company/model_runtime.py',
                     'agents/company_analysis_runtime.py', 'agents/codex_process.py', 'agents/codex_worker.py']
            run['code_hashes'] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}
            published = db.execute("SELECT value FROM company_research_snapshots WHERE json_extract(value,'$.input_id')=?", (input_id,)).fetchone()
            if published:
                saved = verified(json.loads(published[0]))
                run.update(status='COMPLETE', reused=True, model_executed=False,
                           snapshot_id=saved['snapshot_id'], finished_at=now())
            else:
                run['model_executed'] = False
            self.research.analysis.insert(db, 'analysis_runs', 'run_id', record(run))
        if run.get('reused'):
            return self.research.analysis_run(run['run_id'])
        try:
            configured = os.environ.get('ROLL_CODEX_AUTH_FILE')
            if not configured:
                raise FileNotFoundError()
            auth = json.loads(Path(configured).read_text(encoding='utf-8'))
            if auth.get('auth_mode') != 'chatgpt' or not auth.get('tokens'):
                raise ValueError('CHATGPT_AUTH_REQUIRED')
            run['model_executed'] = True
            execute(self, run, packet, cancel or threading.Event(), auth)
        except (OSError, ValueError, HTTPException) as error:
            code = error.detail.get('code') if isinstance(error, HTTPException) and isinstance(error.detail, dict) else None
            run.update(status='UNAVAILABLE' if isinstance(error, OSError) else 'FAILED',
                       error={'code': code or ('MODEL_UNAVAILABLE' if isinstance(error, OSError) else 'MODEL_OUTPUT_INVALID'),
                              'type': type(error).__name__})
        except Exception as error:
            run.update(status='FAILED', error={'code': 'MODEL_EXECUTION_FAILED', 'type': type(error).__name__})
        finally:
            run['finished_at'] = now()
            self.save(run)
        return self.research.analysis_run(run['run_id'])
