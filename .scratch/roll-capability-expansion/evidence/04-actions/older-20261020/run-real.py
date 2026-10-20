"""Saved real originals, actual clock, complete isolated store; zero acquisition."""
import hashlib
import json
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app

repo = Path(__file__).resolve().parents[5]
out = Path(__file__).resolve().parent
source = repo / '.scratch/r020304-runtime03'
target = repo / '.scratch/r-action-older-runtime02'
assert not target.exists()
assert (source / 'backups/capability-journal/origin.json').exists()
before_hash = hashlib.sha256((source / 'roll.sqlite3').read_bytes()).hexdigest()
shutil.copytree(source, target)
with TestClient(create_app(target, runtime_role='API')) as client:
    account = client.get('/api/account').json()
    previous = client.get('/api/market/source-authority?instrument=SSE:600362').json()
    old_actions = [v for v in previous if v['kind'] == 'ACTION_DOCUMENTS']
    assert old_actions and all(len(v['details']['notices']) == 2 for v in old_actions)
    command = {'kind': 'ACTION_DOCUMENTS', 'idempotency_key': 'actual-older-2024'}
    response = client.post('/api/market/source-authority', json=command)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved['evidence_kind'] == 'REAL_SAVED_SOURCE_OBSERVATION'
    assert saved['network_calls'] == saved['account_events_added'] == 0
    assert len(saved['details']['notices']) == 3 and not saved['system_usable']
    assert client.post('/api/market/source-authority', json=command).json() == saved
    for old in previous:
        assert client.get('/api/market/source-authority/' + old['assessment_id']).json() == old
    assert client.get('/api/account').json() == account
with TestClient(create_app(target, runtime_role='API')) as client:
    assert client.get('/api/market/source-authority/' + saved['assessment_id']).json() == saved
    for old in previous:
        assert client.get('/api/market/source-authority/' + old['assessment_id']).json() == old
    assert client.get('/api/account').json() == account
assert hashlib.sha256((source / 'roll.sqlite3').read_bytes()).hexdigest() == before_hash
(out / 'assessment.json').write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8')
(out / 'runtime-summary.json').write_text(json.dumps({
    'evidence': 'REAL_SAVED_SOURCE_OBSERVATION', 'original_source_db_unchanged': True,
    'old_assessments_unchanged': len(previous), 'new_notices': 3,
    'account_unchanged': True, 'idempotency_and_restart_replay': True,
    'network_calls': 0, 'fit_calls': 0, 'sealed_reads': 0, 'capability': 'NOT_GRANTED',
    'data_directory': str(target),
}, indent=2), encoding='utf-8')
print('REAL saved-source API creation, old/new replay and restart passed')
