"""Closed METHOD profile upgrade fixture; never starts any provider."""
import json,sqlite3,sys
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
root=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(root/'backend/tests/application'))
from test_market_directory import establish
from test_codex_evidence import request_data
directory=root/'.scratch/csbrowser2'
assert not directory.exists()
with TestClient(create_app(directory)) as client:
    establish(client,['SSE:600519'])
    request_id=request_data(client)
settings={'version':1,'backend':'DEEPSEEK','saved_at':'2026-10-08T00:00:00+00:00'}
run={'run_id':'legacy-deepseek-method','request_id':request_id,'backend':'DEEPSEEK','model':'historical-method',
     'status':'CANCELLED','evidence_kind':'METHOD_CASE_LEGACY_ARCHIVE','started_at':'2026-10-08T00:00:00+00:00',
     'finished_at':'2026-10-08T00:00:01+00:00','backend_settings':settings,'config_fingerprint':'historical-method-fingerprint',
     'question':'依据？','tools':[],'gaps':[]}
with sqlite3.connect(directory/'roll.sqlite3') as db:
    db.execute('INSERT INTO agent_settings VALUES(1,?)',(json.dumps(settings),))
    db.execute('INSERT INTO retrieval_runs VALUES(?,?,?)',(run['run_id'],run['request_id'],json.dumps(run)))
print('Closed METHOD legacy settings/record fixture prepared; no task dispatch.')
