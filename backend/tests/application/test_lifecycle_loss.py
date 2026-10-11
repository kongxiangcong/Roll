from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package, prepare
from test_funding import funding
from roll.decisions.funding import LossFacts, evaluate_loss


def test_trusted_method_loss_event_latches_new_risk_and_funding_expansion_cannot_resume(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    # Two separately declared immutable METHOD inputs: prior qualification was
    # healthy, later action valuation has a literal 6000 cashflow-adjusted loss.
    package['action_packet']['loss_facts'] = {**package['loss_facts'], 'facts_version': 'method-decline',
        'net_assets': '94000.10', 'realized_pnl': '-6000.00'}
    file = save_package(tmp_path / 'qualification.json', package)
    directory = tmp_path / 'data'
    with TestClient(create_app(directory, capability_method_file=file)) as client:
        prepare(client, package)
        grant = client.get('/api/capabilities/grants').json()[0]
        decline = client.post('/api/actions/evaluate', json={}).json()
        assert decline['joint_budget']['loss']['status'] == 'PAUSED'
        assert decline['joint_budget']['loss']['peak_loss'] == '6000.00'
        events = [e for e in client.get('/api/capabilities/events').json() if e.get('reason_code') == 'LOSS_BOUNDARY']
        assert len(events) == 1, events
        assert events[0]['scope'] == 'NEW_RISK' and events[0]['state'] == 'SUSPENDED'
        assert events[0]['evaluation_id'] == decline['evaluation_id']
        before = client.get('/api/capabilities/lifecycle').json()
        assert before['new_risk_allowed'] is False and before['observations_allowed'] is True
        wrong = client.post('/api/capabilities/lifecycle', json={'scope': 'NEW_RISK', 'state': 'ACTIVE',
            'reason_code': 'USER_PAUSE', 'reason': '错误原因不能恢复', 'expected_version': before['version'],
            'resume_event_id': events[0]['event_id'], 'idempotency_key': 'wrong'})
        assert wrong.status_code == 409
        assert client.post('/api/funding/confirm', json=funding(2, single_exposure='40000.00', loss_threshold='10000.00')).status_code == 200
        assert client.get('/api/capabilities/lifecycle').json()['new_risk_allowed'] is False
        latest = client.post('/api/actions/evaluate', json={}).json()
        assert latest['joint_budget']['loss']['triggered'] is True
        assert latest['decisions'] == []
        assert client.get('/api/actions/evaluations/' + decline['evaluation_id']).json() == decline
        assert client.get('/api/capabilities/grants').json() == [grant]
        # Independent literal financial seam: price/net-assets rebound does not
        # erase a peak or latch. This is calculation evidence, not real quotes.
        rebound = LossFacts(**{**package['action_packet']['loss_facts'], 'facts_version': 'method-rebound',
            'net_assets': '100000.10', 'realized_pnl': '0.00'})
        result = evaluate_loss(client.get('/api/funding').json(), rebound, latest['joint_budget']['loss'])
        assert result['loss'] == '0.00' and result['peak_loss'] == '6000.00'
        assert result['status'] == 'PAUSED' and result['triggered'] is True
    with TestClient(create_app(directory, capability_method_file=file)) as client:
        assert client.get('/api/capabilities/lifecycle').json()['new_risk_allowed'] is False
        assert len([e for e in client.get('/api/capabilities/events').json() if e.get('reason_code') == 'LOSS_BOUNDARY']) == 1
