from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package, prepare
from test_intents import intent_command
from test_capabilities import ready, method_command
from test_reconcile import reconcile, broker_snapshot
from test_account import submit
from datetime import datetime, timedelta
from test_funding import funding


def test_real_old_active_backup_cannot_hide_a_later_committed_revocation(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    file = save_package(tmp_path / 'qualification.json', package)
    directory = tmp_path / 'data'
    with TestClient(create_app(directory, capability_method_file=file)) as client:
        prepare(client, package)
        original = client.get('/api/capabilities/grants').json()[0]
        old = client.post('/api/actions/evaluate', json={}).json()
        backup = client.post('/api/runtime/backups').json()
        bundle = client.get('/api/runtime/backups/' + backup['backup_id'] + '/export').content
        revoked = client.post('/api/capabilities/lifecycle', json={'grant_id': original['grant_id'], 'scope': 'MODEL',
            'state': 'REVOKED', 'reason_code': 'USER_REVOKE', 'reason': '备份之后撤回',
            'expected_version': 0, 'idempotency_key': 'revoke'}).json()
        staged = client.post('/api/runtime/restores', content=bundle, headers={'content-type': 'application/zip'})
        assert staged.status_code == 202, staged.text
    with TestClient(create_app(directory, capability_method_file=file)) as client:
        recovery = client.get('/api/runtime/backups/status').json()['recovery']
        assert recovery['state'] == 'RECOVERY_LOCK'
        status = client.get('/api/capabilities/grants/' + original['grant_id'] + '/status').json()
        assert status['state'] == 'REVOKED', status
        assert client.get('/api/capabilities/grants').json() == [original]
        events = client.get('/api/capabilities/events').json()
        assert next(e for e in events if e['event_id'] == revoked['event_id']) == revoked
        assert client.get('/api/actions/evaluations/' + old['evaluation_id']).json() == old
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert client.post('/api/intents/prepare', json=intent_command(old)).status_code == 409
        assert client.get('/api/account').status_code == 200


def test_recovery_requires_current_source_bound_proof_and_new_broker_reconciliation(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    cutoff = (datetime.fromisoformat(package['required_as_of']) + timedelta(minutes=2)).isoformat()
    package.update(account_version=4, required_as_of=cutoff)
    package['current_data']['as_of'] = cutoff
    package['loss_facts']['as_of'] = cutoff
    package['action_packet'].update(as_of=cutoff)
    for item in package['action_packet']['opportunities']:
        for field in ['quote_at', 'quote_available_at', 'forecast_cutoff']: item[field] = cutoff
    file = save_package(tmp_path / 'qualification.json', package)
    directory = tmp_path / 'data'
    with TestClient(create_app(directory, capability_method_file=file)) as client:
        ready(client)
        backup = client.post('/api/runtime/backups').json()
        bundle = client.get('/api/runtime/backups/' + backup['backup_id'] + '/export').content
        assert client.post('/api/runtime/restores', content=bundle).status_code == 202
    import roll.decisions.capabilities as capabilities
    import roll.accounts.ledger as ledger
    class RecoveryClock(datetime):
        @classmethod
        def now(cls, tz=None): return datetime.fromisoformat(cutoff).astimezone(tz)
    monkeypatch.setattr(ledger, 'datetime', RecoveryClock)
    monkeypatch.setattr(capabilities, 'now', lambda: cutoff)
    with TestClient(create_app(directory, capability_method_file=file)) as client:
        assert client.get('/api/runtime/backups/status').json()['recovery']['state'] == 'RECOVERY_LOCK'
        snapshot = broker_snapshot('100000.10', '0.00', '0.00')
        snapshot['pending_items'] = []
        command = reconcile(2, 'method-current-broker', snapshot)
        command['payload'].update(effective_at=cutoff, source='隔离METHOD当前券商快照；非真实账户')
        submit(client, command, 'reconcile-after-restore')
        submit(client, {'kind': 'ACCOUNT_DECLARATION', 'expected_account_version': 3, 'payload': {
            'effective_at': cutoff, 'source': '隔离METHOD恢复后逐范围核对', 'record_id': 'current-declaration',
            'scope': ['TRADES', 'ORDERS', 'CASH', 'EQUITY'], 'changes': 'NONE', 'basis': '当前快照及未决事项逐项核查'}}, 'current-declaration')
        request = {**method_command(), 'scope': package['scope'], 'expected_account_version': 4,
                   'required_as_of': cutoff, 'idempotency_key': 'proof-under-lock'}
        refused = client.post('/api/capabilities/grants', json=request)
        assert refused.status_code == 409, refused.text
        assert refused.json()['detail']['reasons'] == ['RECOVERY_LOCK']
        proof = client.get('/api/capabilities/proofs').json()[-1]
        assert proof['status'] == 'VERIFIED'
        recovery_response = client.get('/api/capabilities/recovery')
        assert recovery_response.status_code == 200, recovery_response.text
        recovery = recovery_response.json()
        recovery_command = {'proof_id': proof['proof_id'],
            'expected_account_version': 4, 'expected_funding_version': 1,
            'expected_journal_fingerprint': recovery['journal_fingerprint'],
            'basis': '当前source-bound METHOD材料与恢复后券商核对', 'idempotency_key': 'recover'}
        response = client.post('/api/capabilities/recovery', json=recovery_command)
        assert response.status_code == 201, response.text
        verified = response.json()
        assert verified['state'] == 'RECOVERED_VERIFIED' and verified['system_usable'] is False
        assert (directory / 'backups/recovery-lock.json').exists()
        assert __import__('json').loads((directory / 'backups/recovery-lock.json').read_text())['state'] == 'RECOVERY_LOCK'
        assert client.get('/api/capabilities/grants').json() == []
        new = client.post('/api/capabilities/grants', json={**request, 'idempotency_key': 'fresh-after-recovery'})
        assert new.status_code == 201, new.text
        assert new.json()['system_usable'] is False
        assert client.post('/api/formal/evaluate', json={}).status_code == 403
        physical = (directory / 'backups/recovery-lock.json').read_bytes()
        assert client.post('/api/capabilities/recovery', json=recovery_command).json() == verified
        assert client.post('/api/funding/confirm', json=funding(1, single_exposure='10000.00')).status_code == 200
        assert client.get('/api/capabilities/recovery').json()['state'] == 'RECOVERY_LOCK'
        assert client.get('/api/capabilities/grants/' + new.json()['grant_id'] + '/status').json()['allowed_actions'] == []
        assert (directory / 'backups/recovery-lock.json').read_bytes() == physical


def test_imported_active_backup_has_no_proof_of_latest_local_permission_history(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    file = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'source', capability_method_file=file)) as client:
        prepare(client, package)
        backup = client.post('/api/runtime/backups').json()
        bundle = client.get('/api/runtime/backups/' + backup['backup_id'] + '/export').content
    with TestClient(create_app(tmp_path / 'imported', capability_method_file=file)) as client:
        assert client.post('/api/runtime/restores', content=bundle).status_code == 202
    # The target's local empty history predates import; it cannot certify an
    # unrelated restored grant's permission history on the original machine.
    with TestClient(create_app(tmp_path / 'imported', capability_method_file=file)) as client:
        recovery = client.get('/api/capabilities/recovery').json()
        assert recovery['state'] == 'RECOVERY_LOCK'
        assert recovery['permission_history_known'] is False
        assert client.get('/api/actions/current').json()['decisions'] == []
        proof = client.get('/api/capabilities/proofs').json()[0]
        denied = client.post('/api/capabilities/recovery', json={'proof_id': proof['proof_id'],
            'expected_account_version': 2, 'expected_funding_version': 2,
            'expected_journal_fingerprint': recovery['journal_fingerprint'],
            'basis': '旧包不能证明之后没有撤回', 'idempotency_key': 'unknown-recovery'})
        assert denied.status_code == 409
        assert denied.json()['detail'] == 'LATEST_PERMISSION_HISTORY_UNVERIFIED'
        assert client.get('/api/account').status_code == 200


def test_permission_journal_write_failure_refuses_command_and_keeps_observation_only(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    file = save_package(tmp_path / 'qualification.json', package)
    directory = tmp_path / 'data'
    with TestClient(create_app(directory, capability_method_file=file), raise_server_exceptions=False) as client:
        original = prepare(client, package)
        old = client.post('/api/actions/evaluate', json={}).json()
        # Owned native filesystem fault; no collaborator or database mock.
        (directory / 'backups/capability-journal/pending').write_text('not a directory', encoding='utf-8')
        refused = client.post('/api/capabilities/lifecycle', json={'grant_id': original['grant_id'],
            'scope': 'MODEL', 'state': 'REVOKED', 'reason_code': 'USER_REVOKE',
            'reason': '不能持久化权限日志时禁止继续放行', 'expected_version': 0, 'idempotency_key': 'write-failure'})
        assert refused.status_code == 503, refused.text
        assert refused.json()['detail'] == 'CAPABILITY_JOURNAL_WRITE_FAILED'
        assert not any(e.get('reason_code') == 'USER_REVOKE' for e in client.get('/api/capabilities/events').json())
        recovery = client.get('/api/capabilities/recovery').json()
        assert recovery['state'] == 'RECOVERY_LOCK'
        assert recovery['permission_journal_error'] == 'WRITE_FAILED_UNCONFIRMED'
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert client.get('/api/actions/evaluations/' + old['evaluation_id']).json() == old
        assert client.get('/api/account').status_code == 200
