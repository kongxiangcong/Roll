"""One invalidation fact per old action; current new causes remain visible."""
import json
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package, prepare
from test_account import submit
from test_funding import funding


def test_old_action_invalidation_is_one_fact_and_new_account_cause_keeps_history(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    file = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file, runtime_role='API')) as client:
        prepare(client, package)
        original = client.post('/api/actions/evaluate', json={}).json()
        assert len(original['decisions']) == 1
        shrunk = client.post('/api/funding/confirm', json=funding(2, total_exposure='10000.00', single_exposure='10000.00', cash_reserve='90000.00'))
        assert shrunk.status_code == 200
        first = client.get('/api/actions/current').json()
        assert first['invalidated'][0]['reasons'] == ['FUNDING_VERSION_CHANGE', 'GRANT_RESTRICTED']
        events = [e for e in client.get('/api/actions/events').json() if e['event_type'] == 'ACTION_INVALIDATED']
        assert len(events) == 1
        second = client.get('/api/actions/current').json()
        assert second['decisions'] == []
        assert second['invalidated'][0]['reasons'] == ['PREVIOUSLY_INVALIDATED_REQUIRES_NEW_ACTION', 'FUNDING_VERSION_CHANGE', 'GRANT_RESTRICTED']
        repeated = [e for e in client.get('/api/actions/events').json() if e['event_type'] == 'ACTION_INVALIDATED']
        (tmp_path / 'repeated-invalidation.json').write_text(json.dumps({'first': events, 'repeated': repeated}, indent=2), encoding='utf-8')
        assert repeated == events
        receipt = submit(client, {'kind': 'ACCOUNT_DECLARATION', 'expected_account_version': 2, 'payload': {
            'effective_at': package['required_as_of'], 'source': 'METHOD confirmed account declaration', 'record_id': 'new-account-cause',
            'scope': ['TRADES', 'ORDERS', 'CASH', 'EQUITY'], 'changes': 'NONE', 'basis': 'isolated current account facts'}}, 'new-account-cause')
        assert receipt.status_code == 200
        latest = client.get('/api/actions/current').json()
        assert latest['decisions'] == []
        assert latest['invalidated'][0]['reasons'] == ['PREVIOUSLY_INVALIDATED_REQUIRES_NEW_ACTION', 'ACCOUNT_VERSION_CHANGE', 'FUNDING_VERSION_CHANGE', 'GRANT_RESTRICTED']
        assert client.get('/api/account').json()['version'] == 3
        assert client.get('/api/account/versions/3').status_code == 200
        assert [e for e in client.get('/api/actions/events').json() if e['event_type'] == 'ACTION_INVALIDATED'] == events
        assert client.get('/api/actions/evaluations/' + original['evaluation_id']).json() == original
        assert client.post('/api/actions/evaluations/' + original['evaluation_id'] + '/replay').json()['matches_original'] is True
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file, runtime_role='API')) as client:
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert [e for e in client.get('/api/actions/events').json() if e['event_type'] == 'ACTION_INVALIDATED'] == events
        assert client.get('/api/actions/audit').json()['invalidated_actions'] == {'status': 'CHECKED', 'value': 1}
