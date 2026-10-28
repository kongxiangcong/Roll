"""Actual child exit before normalization/commit; recovery never consumes another call."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from roll.app import create_app


@pytest.mark.parametrize('fault', ['sse_daily_after_raw', 'sse_daily_before_commit'])
def test_process_interruption_leaves_no_receipt_or_implicit_retry(tmp_path, monkeypatch, fault):
    directory = tmp_path / 'data'
    backend = Path(__file__).resolve().parents[2]
    script = '''
import json,os
from pathlib import Path
import httpx
from roll.app import create_app
from roll.research.prospective import CollectionCommand
from roll.market import sse_daily,post_close_packet,evidence
from roll.market.collection_sources import SourcePolicyCommand
from roll.research import prospective
for module in [sse_daily,post_close_packet,evidence,prospective]:module.now=lambda:'2026-10-14T18:00:00+08:00'
value=json.loads((sse_daily.HISTORY_REFERENCE/'a51334316a941c30047614138f201d3dd3d988a453fa754b8673ae1fd74bb113.raw').read_bytes())
value['result'][0]['TX_DATE']='20261014'
app=create_app(Path(os.environ['ROLL_DATA_DIR']),runtime_role='API',market_transport=httpx.MockTransport(lambda r:httpx.Response(200,json=value)))
plan=app.state.prospective.start(CollectionCommand(instrument='SSE:600362',basis='METHOD actual child source fault'))
policy=app.state.collection_sources.policy(sse_daily.SOURCE)
app.state.collection_sources.change(sse_daily.SOURCE,SourcePolicyCommand(enabled=True,expected_revision=policy['revision'],basis='Explicit child source fault scope'))
app.state.dated_daily.capture_once(plan['plan_id'],'METHOD one-call child')
'''
    env = {k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA'}}
    env.update(ROLL_ENV='test', ROLL_DATA_DIR=str(directory), ROLL_TEST_CRASH_POINT=fault,
               PYTHONPATH=str(backend/'src'), PYTHONDONTWRITEBYTECODE='1')
    run = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', script], env=env,
                         capture_output=True, timeout=40,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (tmp_path/'child-output.log').write_bytes(run.stdout+run.stderr)
    assert run.returncode == 86, run.stderr.decode('utf8', errors='replace')
    monkeypatch.setattr('roll.market.sse_daily.now', lambda:'2026-10-14T18:00:00+08:00')
    with TestClient(create_app(directory, runtime_role='API')) as client:
        plan = client.get('/api/research/collections').json()[0]
        base = '/api/research/collections/' + plan['plan_id']
        result = client.post(base+'/sse-daily/check', json={'basis':'Recovery must not retry the consumed budget'})
        assert result.status_code == 201, result.text
        assert result.json()['state'] == 'INTERRUPTED_NO_RETRY'
        assert client.get(base+'/sse-daily-receipts').json() == []
        with client.app.state.ledger.connection() as db:
            archives = [json.loads(r[0]) for r in db.execute('SELECT value FROM evidence_archives')]
        assert any(a['kind']=='SSE_DATED_DAILY_RAW' for a in archives)
        assert client.get('/api/research/collections/'+plan['plan_id']+'/readiness').json()['real_recorded_sessions'] == 0
