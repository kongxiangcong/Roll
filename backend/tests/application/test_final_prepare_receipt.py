"""Public prepare command receipts stay immutable; current intent facts remain current."""
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package, prepare
from test_action_risk_priority import method_clock, record
from test_account import permission_change, submit
from test_intents import intent_command
from test_fills import fill
from pathlib import Path
import hashlib, json, shutil


def test_prepare_retry_returns_original_after_pending_permission_expiry_and_restart(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    directory = tmp_path / 'data'
    with TestClient(create_app(directory, capability_method_file=file, runtime_role='API')) as client:
        prepare(client, p)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        command = intent_command(evaluation)
        original = client.post('/api/intents/prepare', json=command)
        assert original.status_code == 201, original.text
        receipt = original.json()
        record(tmp_path, 'original-prepare', {'command': command, 'receipt': receipt})
        pending_command = {'state': 'OPERATION_PENDING', 'idempotency_key': command['idempotency_key']}
        pending = client.post('/api/intents/' + receipt['intent_id'] + '/declare', json=pending_command)
        assert pending.status_code == 200, pending.text
        assert client.post('/api/intents/prepare', json=command).json() == receipt
        assert submit(client, permission_change(evaluation['account_version'], 'NOT_OPEN'), 'permission').status_code == 200
        monkeypatch.setattr('roll.decisions.actions.now', lambda: (datetime.fromisoformat(p['expires_at']) + timedelta(minutes=1)).isoformat())
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert client.post('/api/intents/prepare', json=command).json() == receipt
        assert client.post('/api/intents/prepare', json={**command, 'price_yuan': '141'}).status_code == 409
        assert client.post('/api/intents/prepare', json={**command, 'idempotency_key': 'new-key'}).status_code == 409
        current = client.get('/api/intents').json()
        assert len(current['intents']) == 1
        assert current['intents'][0]['status'] == 'OPERATION_PENDING'
        assert current['unreflected_reservation_yuan'] == '30005.00'
        assert client.post('/api/intents/' + receipt['intent_id'] + '/declare', json=pending_command).json() == pending.json()
    with TestClient(create_app(directory, capability_method_file=file, runtime_role='API')) as client:
        assert client.post('/api/intents/prepare', json=command).json() == receipt
        assert client.get('/api/intents').json() == current


def test_prepare_original_survives_partial_fill_and_successor_evaluation(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file, runtime_role='API')) as client:
        prepare(client, p)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        command = intent_command(evaluation)
        receipt = client.post('/api/intents/prepare', json=command).json()
        actual = fill(evaluation['account_version'], 'receipt-partial')
        actual['payload'].update(quantity='100', price='140.00', effective_at=p['required_as_of'], broker_available_after='76000.10')
        draft = client.post('/api/account/drafts', json=actual).json()
        confirmed = client.post('/api/account/confirm', json={'draft_id': draft['draft_id'], 'idempotency_key': 'partial',
            'fill_allocations': [{'intent_id': receipt['intent_id'], 'fill_record_id': 'receipt-partial', 'allocated_quantity': '100', 'association_status': 'USER_CONFIRMED'}]})
        assert confirmed.status_code == 200, confirmed.text
        fresh = client.post('/api/actions/evaluate', json={})
        assert fresh.status_code == 201, fresh.text
        before = client.get('/api/intents').json()
        assert before['intents'][0]['remaining_quantity'] == '100'
        assert before['intents'][0]['synced_quantity'] == '100'
        assert before['intents'][0]['status'] == 'OPERATION_PENDING'
        assert client.post('/api/intents/prepare', json=command).json() == receipt
        assert client.get('/api/intents').json() == before


def test_legacy_mutated_intent_has_no_recoverable_original_prepare_receipt(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    manifest = Path(__file__).parents[3] / '.scratch/roll-p0/evidence/final-review-fix/legacy-profile-manifest.json'
    raw = manifest.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'b42835a26089245b8435c14f827e3bc3afc550b6c8d2401f9636ac561e2e6cca'
    fixture = json.loads(raw)
    source = Path(fixture['target'])
    target = tmp_path / 'data'
    for item in fixture['entries']:
        original = (source / item['path']).read_bytes()
        assert len(original) == item['bytes'] and hashlib.sha256(original).hexdigest() == item['sha256']
        destination = target / item['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / item['path'], destination)
        assert destination.read_bytes() == original and (source / item['path']).read_bytes() == original
    command = fixture['public_original_prepare']['command']
    with TestClient(create_app(target, runtime_role='API')) as client:
        before = client.get('/api/intents').json()
        response = client.post('/api/intents/prepare', json=command)
        assert response.status_code == 409
        assert response.json()['detail'] == 'LEGACY_PREPARE_RECEIPT_UNAVAILABLE'
        different = client.post('/api/intents/prepare', json={**command, 'price_yuan': '141'})
        assert different.status_code == 409
        assert different.json()['detail'] == 'INTENT_IDEMPOTENCY_CONTENT_CONFLICT'
        assert client.get('/api/intents').json() == before
        assert before['intents'][0]['status'] == 'OPERATION_PENDING'
    for item in fixture['entries']:
        assert hashlib.sha256((source / item['path']).read_bytes()).hexdigest() == item['sha256']


def test_prepare_receipt_is_recovered_under_restore_lock_without_new_authorization(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    directory = tmp_path / 'data'
    with TestClient(create_app(directory, capability_method_file=file, runtime_role='API')) as client:
        prepare(client, p)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        command = intent_command(evaluation)
        prepared = client.post('/api/intents/prepare', json=command)
        assert prepared.status_code == 201, prepared.text
        receipt = prepared.json()
        backup = client.post('/api/runtime/backups')
        assert backup.status_code == 201, backup.text
        archive = client.get('/api/runtime/backups/' + backup.json()['backup_id'] + '/export')
        staged = client.post('/api/runtime/restores', content=archive.content, headers={'content-type': 'application/zip'})
        assert staged.status_code == 202, staged.text
    with TestClient(create_app(directory, capability_method_file=file, runtime_role='API')) as client:
        assert client.get('/api/capabilities').json()['runtime_state'] == 'RECOVERY_LOCK'
        before = client.get('/api/intents').json()
        assert client.post('/api/intents/prepare', json=command).json() == receipt
        assert client.post('/api/intents/prepare', json={**command, 'idempotency_key': 'new-key'}).status_code == 409
        assert client.get('/api/intents').json() == before
