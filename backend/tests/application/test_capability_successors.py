from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import prepare
from test_capability_monitoring import monitored_package


def test_revoked_record_stays_closed_when_current_checks_admit_an_explicit_successor(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = monitored_package()
    file = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, package)
        original = client.get('/api/capabilities/grants').json()[0]
        revoked = client.post('/api/capabilities/lifecycle', json={'grant_id': original['grant_id'], 'scope': 'MODEL', 'state': 'REVOKED',
            'reason_code': 'USER_REVOKE', 'reason': '撤回原记录', 'expected_version': 0, 'idempotency_key': 'revoke'})
        assert revoked.status_code == 200
        proposal = client.get('/api/capabilities/proposal', params={'material_id': package['material_id'], 'review_run_id': package['review_run_id']}).json()
        response = client.post('/api/capabilities/grants', json={**proposal, 'predecessor_grant_id': original['grant_id'],
            'idempotency_key': 'successor', 'basis': 'METHOD当前完整检查后登记后继；不是复活原记录'})
        assert response.status_code == 201, response.text
        successor = response.json()
        assert successor['predecessor_grant_id'] == original['grant_id']
        assert successor['grant_id'] != original['grant_id'] and successor['system_usable'] is False
        assert client.get('/api/capabilities/grants/' + original['grant_id'] + '/status').json()['state'] == 'REVOKED'
        assert client.get('/api/capabilities/grants/' + successor['grant_id'] + '/status').json()['state'] == 'METHOD_GRANTED'
        assert client.get('/api/capabilities/grants').json() == [original, successor]
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        assert len(evaluation['decisions']) == 1
        assert evaluation['decisions'][0]['grant_id'] == successor['grant_id']
