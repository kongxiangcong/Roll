"""Actual HTTP/process commit boundaries; METHOD authority cannot be deployed."""
import json
import io
import subprocess
import tarfile
from pathlib import Path
from datetime import datetime

import httpx
import pytest
from test_intent_process import IntentServer
from test_actions import prepare
from test_account_process import Server


@pytest.mark.parametrize('fault,committed', [
    ('capability_lifecycle_before_commit', False),
    ('capability_lifecycle_after_commit', True),
])
def test_permission_journal_never_calls_an_uncommitted_revoke_a_fact(tmp_path, fault, committed):
    directory = tmp_path / 'data'
    server = IntentServer(directory)
    try:
        package = json.loads((tmp_path / 'qualification.json').read_text(encoding='utf-8'))['package']
        import capability_method_app
        capability_method_app.ANCHOR = datetime.fromisoformat(package['required_as_of'])
        original = prepare(server.client, package)
        evaluation = server.client.post('/api/actions/evaluate', json={}).json()
    finally:
        server.stop()
    command = {'grant_id': original['grant_id'], 'scope': 'MODEL', 'state': 'REVOKED',
        'reason_code': 'USER_REVOKE', 'reason': '隔离METHOD提交故障验收',
        'expected_version': 0, 'idempotency_key': 'fault-revoke'}
    failing = IntentServer(directory, fault)
    try:
        with pytest.raises(httpx.TransportError):
            failing.client.post('/api/capabilities/lifecycle', json=command)
        assert failing.process.wait(timeout=10) == 86
    finally:
        failing.stop()
    restarted = IntentServer(directory)
    try:
        client = restarted.client
        facts = [e for e in client.get('/api/capabilities/events').json()
                 if e.get('reason_code') == 'USER_REVOKE']
        assert len(facts) == int(committed)
        control = client.get('/api/capabilities/lifecycle').json()
        assert control['version'] == int(committed)
        status = client.get('/api/capabilities/grants/' + original['grant_id'] + '/status').json()
        if committed:
            assert status['state'] == 'REVOKED'
            assert facts[0]['reason'] == command['reason']
        else:
            lock = client.get('/api/runtime/backups/status').json()['recovery']
            assert lock['state'] == 'RECOVERY_LOCK'
            assert lock['possibly_missing_revocations'] == 'UNVERIFIED'
            assert len(lock['pending_permission_events']) == 1
            assert lock['missing_committed_event_ids'] == []
            assert status['state'] == 'RESTRICTED'
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert client.get('/api/actions/evaluations/' + evaluation['evaluation_id']).json() == evaluation
        assert client.get('/api/capabilities/grants').json() == [original]
        assert client.get('/api/account').status_code == 200
    finally:
        restarted.stop()


def test_actual_pre27_code_rollback_still_reads_physical_recovery_lock(tmp_path):
    directory = tmp_path / 'data'
    server = IntentServer(directory)
    try:
        package = json.loads((tmp_path / 'qualification.json').read_text(encoding='utf-8'))['package']
        import capability_method_app
        capability_method_app.ANCHOR = datetime.fromisoformat(package['required_as_of'])
        original = prepare(server.client, package)
        account = server.client.get('/api/account').json()
        backup = server.client.post('/api/runtime/backups').json()
        bundle = server.client.get('/api/runtime/backups/' + backup['backup_id'] + '/export').content
        revoked = server.client.post('/api/capabilities/lifecycle', json={'grant_id': original['grant_id'],
            'scope': 'MODEL', 'state': 'REVOKED', 'reason_code': 'USER_REVOKE', 'reason': 'rollback METHOD撤回',
            'expected_version': 0, 'idempotency_key': 'rollback-revoke'})
        assert revoked.status_code == 200
        assert server.client.post('/api/runtime/restores', content=bundle).status_code == 202
    finally:
        server.stop()
    restored = IntentServer(directory)
    try:
        assert restored.client.get('/api/runtime/backups/status').json()['recovery']['state'] == 'RECOVERY_LOCK'
        assert restored.client.get('/api/capabilities/grants/' + original['grant_id'] + '/status').json()['state'] == 'REVOKED'
    finally:
        restored.stop()
    repo = Path(__file__).resolve().parents[3]
    old = tmp_path / 'pre27-source'
    raw = subprocess.run(['git', 'archive', '--format=tar', '0d331791e2ab09d4bb226d3e00f438a6d8995530',
        'backend/src/roll', 'backend/uv.lock'], cwd=repo, capture_output=True, check=True).stdout
    old.mkdir()
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive.getmembers():
            assert (old / member.name).resolve().is_relative_to(old.resolve())
        archive.extractall(old, filter='data')
    rollback = Server(directory, source_directory=old / 'backend/src')
    try:
        lock = rollback.client.get('/api/runtime/backups/status').json()['recovery']
        assert lock['state'] == 'RECOVERY_LOCK'
        denied = rollback.client.post('/api/formal/evaluate', json={})
        assert denied.status_code == 403 and denied.json()['detail']['code'] == 'RECOVERY_LOCK'
        assert rollback.client.get('/api/account').json() == account
        assert rollback.client.get('/api/capabilities/grants').json() == [original]
    finally:
        rollback.stop()
