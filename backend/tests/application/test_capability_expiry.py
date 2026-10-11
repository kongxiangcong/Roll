from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package, prepare
from test_intents import intent_command


def test_expiry_is_append_only_and_old_actions_close_without_waiting_for_new_samples(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    clock = [package['required_as_of']]
    monkeypatch.setattr('roll.decisions.capabilities.now', lambda: clock[0])
    monkeypatch.setattr('roll.decisions.actions.now', lambda: clock[0])
    file = save_package(tmp_path / 'qualification.json', package)
    directory = tmp_path / 'data'
    with TestClient(create_app(directory, capability_method_file=file)) as client:
        prepare(client, package)
        grant = client.get('/api/capabilities/grants').json()[0]
        old = client.post('/api/actions/evaluate', json={}).json()
        clock[0] = grant['expires_at']
        status = client.get('/api/capabilities/grants/' + grant['grant_id'] + '/status').json()
        assert status['state'] == 'EXPIRED', status
        assert status['allowed_actions'] == []
        expiry = [e for e in client.get('/api/capabilities/events').json() if e.get('reason_code') == 'EXPIRY']
        assert len(expiry) == 1 and expiry[0]['effective_at'] == grant['expires_at']
        assert expiry[0]['recorded_at'] == clock[0]
        assert client.post('/api/intents/prepare', json=intent_command(old)).status_code == 409
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert client.get('/api/actions/evaluations/' + old['evaluation_id']).json() == old
        assert client.get('/api/capabilities/grants').json() == [grant]
    with TestClient(create_app(directory, capability_method_file=file)) as client:
        assert client.get('/api/capabilities/grants/' + grant['grant_id'] + '/status').json()['state'] == 'EXPIRED'
        assert len([e for e in client.get('/api/capabilities/events').json() if e.get('reason_code') == 'EXPIRY']) == 1
