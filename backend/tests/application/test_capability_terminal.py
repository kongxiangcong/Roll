from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package, prepare


def test_global_resume_cannot_override_terminal_grant(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    file = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, package)
        original = client.get('/api/capabilities/grants').json()[0]
        revoked = client.post('/api/capabilities/lifecycle', json={'grant_id': original['grant_id'],
            'scope': 'MODEL', 'state': 'REVOKED', 'reason_code': 'USER_REVOKE', 'reason': '撤回单项',
            'expected_version': 0, 'idempotency_key': 'revoke'})
        assert revoked.status_code == 200, revoked.text
        pause = client.post('/api/capabilities/lifecycle', json={'scope': 'MODEL', 'state': 'SUSPENDED',
            'reason_code': 'USER_PAUSE', 'reason': '全局暂停', 'expected_version': 1, 'idempotency_key': 'pause'})
        assert pause.status_code == 200, pause.text
        resume = client.post('/api/capabilities/lifecycle', json={'scope': 'MODEL', 'state': 'ACTIVE',
            'reason_code': 'USER_PAUSE', 'reason': '只恢复全局暂停', 'resume_event_id': pause.json()['event_id'],
            'expected_version': 2, 'idempotency_key': 'resume'})
        assert resume.status_code == 200, resume.text
        assert client.get('/api/capabilities/lifecycle').json()['model_judgments_allowed'] is True
        status = client.get('/api/capabilities/grants/' + original['grant_id'] + '/status').json()
        assert status['state'] == 'REVOKED', status
        assert status['allowed_actions'] == []
        assert client.post('/api/actions/evaluate', json={}).json()['decisions'] == []
        assert client.get('/api/capabilities/grants').json() == [original]
