from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_capability_monitoring import monitored_package
from test_actions import prepare
from test_intents import intent_command


def test_data_drift_resume_requires_a_later_bound_healthy_check_and_new_action(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = monitored_package(20, outside=4)
    clock = [datetime.fromisoformat(package['required_as_of'])]
    later = clock[0] + timedelta(seconds=2)
    # Immutable METHOD observations of the second in-scope stock become known
    # later. This tests the consumer's cause binding, not actual future evidence.
    package['monitoring_basis']['observations'] += [{'observation_date': day, 'known_at': later.isoformat(),
        'instrument': 'SSE:600001', 'features': {'x': 50}, 'source_binding': 'literal-later-' + day}
        for day in package['monitoring_basis']['eligible_sessions']]
    monkeypatch.setattr('roll.decisions.monitoring.now', lambda: clock[0].isoformat())
    monkeypatch.setattr('roll.decisions.capabilities.now', lambda: clock[0].isoformat())
    file = save_package(tmp_path / 'qualification.json', package)
    client = TestClient(create_app(tmp_path / 'data', capability_method_file=file))
    try:
        grant = prepare(client, package)
        old = client.post('/api/actions/evaluate', json={}).json()
        first = client.post('/api/capabilities/monitoring/check', json={'grant_id': grant['grant_id'], 'basis': 'initial literal drift'}).json()
        assert first['status'] == 'RESTRICTED'
        resume = {'grant_id': grant['grant_id'], 'scope': 'MODEL', 'state': 'ACTIVE', 'reason_code': 'DATA_DRIFT',
            'resume_event_id': first['restriction_event_id'], 'recovery_check_id': first['check_id'],
            'reason': '同冻结source后续输入恢复支持，不改历史结论', 'expected_version': 1, 'idempotency_key': 'unhealthy'}
        rejected = client.post('/api/capabilities/lifecycle', json=resume)
        assert rejected.status_code == 409, rejected.text
        clock[0] = later
        healthy = client.post('/api/capabilities/monitoring/check', json={'grant_id': grant['grant_id'], 'basis': 'later literal frozen support'}).json()
        assert healthy['status'] == 'CHECKED', healthy
        assert client.get('/api/capabilities/grants/' + grant['grant_id'] + '/status').json()['allowed_actions'] == []
        restored = client.post('/api/capabilities/lifecycle', json={**resume, 'recovery_check_id': healthy['check_id'], 'idempotency_key': 'healthy'})
        assert restored.status_code == 200, restored.text
        assert restored.json()['recovery_check_id'] == healthy['check_id']
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert client.post('/api/intents/prepare', json=intent_command(old)).status_code == 409
        fresh = client.post('/api/actions/evaluate', json={}).json()
        assert len(fresh['decisions']) == 1 and fresh['evaluation_id'] != old['evaluation_id']
        assert client.get('/api/actions/evaluations/' + old['evaluation_id']).json() == old
        assert client.get('/api/capabilities/monitoring/' + first['check_id']).json() == first
        assert client.get('/api/capabilities/grants').json() == [grant]
    finally:
        client.close()
