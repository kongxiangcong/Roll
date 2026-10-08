"""One saved selection; each evidence task freezes its own effective configuration."""
import json
import hashlib
from pathlib import Path
import unicodedata
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from roll.accounts.ledger import encode, now

HOST_LIMITS={'timeout_seconds':120,'tool_calls':8,'http_calls':6,'response_bytes':65536,
             'total_bytes':262144,'concurrency':1,'subtasks':0,'recursive_depth':0,'retries':0}


class BackendSelection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_version:int=Field(ge=0)
    backend:Literal['CODEX','DEEPSEEK']


class AgentQuestion(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question:str=Field(min_length=1,max_length=2000)
    retry_of:str|None=None


def check_retry(evidence,request_id,command):
    if not command.retry_of:return
    prior=evidence.get('retrieval_runs',command.retry_of)
    normalize=lambda value:' '.join(unicodedata.normalize('NFC',value).split())
    if (prior.get('backend') not in {'CODEX','DEEPSEEK'} or prior['request_id']!=request_id
            or prior['status']=='RUNNING' or normalize(prior.get('question',''))!=normalize(command.question)):
        raise HTTPException(409,{'code':'INVALID_AGENT_RETRY','message':'重试须保持原事实请求与问题；更改问题请发起新任务。'})


def insert_run(evidence,db,run,selection):
    """Called inside the same transaction that obtains the shared execution slot."""
    from roll.agents.codex_process import owner_alive
    current=json.loads(db.execute('SELECT value FROM agent_settings ORDER BY version DESC LIMIT 1').fetchone()[0])
    if selection is not None and current['version']!=selection['version']:
        raise HTTPException(409,{'code':'BACKEND_SETTINGS_VERSION_CONFLICT','current':current})
    run['backend_settings']=selection or current
    run['selection_kind']='SAVED_BACKEND' if selection else 'EXPLICIT_BACKEND'
    paths=[Path(__file__).with_name('codex_process.py'),*Path(__file__).parent.parent.joinpath('market').glob('*.py')]
    run['source_dependency_fingerprint']=hashlib.sha256(encode({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}).encode()).hexdigest()
    for row in db.execute('SELECT value FROM retrieval_runs'):
        prior=json.loads(row[0])
        if prior.get('backend') in {'CODEX','DEEPSEEK'} and prior['status']=='RUNNING' and owner_alive(prior):
            raise HTTPException(409,{'code':'AGENT_CONCURRENCY_LIMIT','running_backend':prior['backend'],'max_concurrency':1})
    db.execute('INSERT INTO retrieval_runs VALUES(?,?,?)',(run['run_id'],run['request_id'],encode(run)))


class AgentSettings:
    def __init__(self,ledger):
        self.ledger=ledger
        with ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS agent_settings(version INTEGER PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO agent_settings VALUES(0,?)',(encode({'version':0,'backend':'CODEX','saved_at':None}),))

    def get(self,db=None):
        if db is None:
            with self.ledger.connection() as db:return self.get(db)
        return json.loads(db.execute('SELECT value FROM agent_settings ORDER BY version DESC LIMIT 1').fetchone()[0])

    def select(self,command):
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            current=self.get(db)
            if current['version']!=command.expected_version:
                raise HTTPException(409,{'code':'BACKEND_SETTINGS_VERSION_CONFLICT','current':current})
            if current['backend']==command.backend:return current
            value={'version':current['version']+1,'backend':command.backend,'saved_at':now()}
            db.execute('INSERT INTO agent_settings VALUES(?,?)',(value['version'],encode(value)))
            db.commit()
            return value

    def history(self):
        with self.ledger.connection() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT value FROM agent_settings ORDER BY version DESC')]
