"""Independent literal public-contract checks, isolated METHOD evidence only."""
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import package, save_package
from test_actions import action_package, prepare
from test_capabilities import ready, method_command
from test_funding import funding


def verify(client, value):
    assert client.get('/api/actions/evaluations/' + value['evaluation_id']).json() == value
    replay = client.post('/api/actions/evaluations/' + value['evaluation_id'] + '/replay')
    assert replay.status_code == 200, replay.text
    assert replay.json()['matches_original'] is True
    assert replay.json()['network_calls'] == 0


def test_profit_five_literal_fields_persist_restart_and_production_restriction(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    directory = tmp_path / 'data'
    with TestClient(create_app(directory, capability_method_file=file, runtime_role='API')) as client:
        grant = prepare(client, p)
        before = client.get('/api/account').json()
        response = client.post('/api/actions/evaluate', json={})
        assert response.status_code == 201, response.text
        value = response.json()
        assert [(d['instrument'], d['action'], d['quantity']) for d in value['decisions']] == [('SSE:600000', 'BUY', '200')]
        decision = value['decisions'][0]
        assert decision['account_status'] == {'purpose': 'NEW_RISK', 'state': 'CONFIRMED_AS_OF', 'fact_scope_state': 'CONFIRMED_AS_OF', 'allowed': True, 'reasons': []}
        assert decision['data_status'] == {'state': 'COMPLETE_CURRENT', 'namespace': 'METHOD_ENGINEERING', 'reasons': []}
        assert decision['model_status'] == 'METHOD_ENGINEERING'
        assert decision['execution_eligibility'] == 'METHOD_ONLY'
        assert decision['capability_status'] == {'state': 'METHOD_GRANTED', 'grant_id': grant['grant_id'], 'allowed_actions': ['BUY'], 'system_usable': False}
        assert decision['grant_id'] == grant['grant_id']
        assert value['system_usable'] is False
        assert value['refusals'][0]['execution_eligibility'] == 'BLOCKED'
        assert client.get('/api/account').json() == before
        verify(client, value)
    with TestClient(create_app(directory, capability_method_file=file, runtime_role='API')) as client:
        verify(client, value)
        assert client.post('/api/actions/evaluate', json={}).json() == value
        assert client.get('/api/actions/current').json()['decisions'] == value['decisions']
    monkeypatch.setenv('ROLL_ENV', 'local')
    with pytest.raises(ValueError):
        create_app(directory, capability_method_file=file, runtime_role='API')
    with TestClient(create_app(directory, runtime_role='API')) as client:
        assert client.get('/api/actions/evaluations/' + value['evaluation_id']).json() == value
        current = client.get('/api/actions/current').json()
        assert current['decisions'] == []
        assert 'GRANT_RESTRICTED' in current['invalidated'][0]['reasons']
        assert client.post('/api/formal/evaluate', json={}).status_code == 403
        denied = client.post('/api/actions/evaluate', json={})
        assert denied.status_code == 201, denied.text
        assert denied.json()['decisions'] == []
        assert denied.json()['system_usable'] is False


@pytest.mark.parametrize('sellable', ['300', '0'])
def test_risk_own_grant_not_global_profit_qualification_and_unsellable_fact(tmp_path, monkeypatch, sellable):
    monkeypatch.setenv('ROLL_ENV', 'test')
    anchor = (datetime.now(timezone(timedelta(hours=8))) - timedelta(days=1)).replace(hour=15, minute=5, second=0, microsecond=0)
    import capability_method_app
    monkeypatch.setattr(capability_method_app, 'ANCHOR', anchor)
    clock = (anchor + timedelta(minutes=1)).isoformat()
    monkeypatch.setattr('roll.decisions.capabilities.now', lambda: clock)
    monkeypatch.setattr('roll.decisions.actions.now', lambda: clock)
    p = package()
    gates = ['DATA', 'RULE_QUANTITY', 'AUTHORIZATION', 'STRESS_EXECUTION', 'ONLINE_CONSISTENCY']
    p.update(candidate_kind='RISK_POLICY', gates={g: 'PASS' for g in gates}, required_gates=gates, allowed_actions=['REDUCE', 'EXIT'])
    p['deployment_fingerprints'] = {'policy': 'e' * 64}
    rule = 'SSE-MAIN-A-2026-07-06'
    profit = action_package()['action_packet']
    p['action_packet'] = {'namespace': 'METHOD_ENGINEERING', 'as_of': p['required_as_of'], 'expires_at': p['expires_at'],
        'complete_protocol_fingerprint': p['complete_protocol_fingerprint'], 'policy': profit['policy'],
        'opportunities': [r for r in profit['opportunities'] if r['instrument'] == 'SSE:600000'],
        'loss_facts': p['loss_facts'], 'risk_inputs': {
            'policy': {'policy_id': 'risk-method', 'policy_fingerprint': 'e' * 64,
                'authorization': {**funding()['authorization'], 'version': 1, 'loss_origin_at': '2026-10-07T02:00:00+00:00'},
                'scope': p['scope'], 'rule_ids': {'SSE:600000': rule}},
            'required_as_of': p['required_as_of'], 'consumer_knowledge_cutoff': clock,
            'quotes': {'SSE:600000': {'last': '100', 'adjustment': 'RAW', 'currency': 'CNY', 'errors': [],
                'upstream_at': p['required_as_of'], 'available_at': p['required_as_of'], 'method_status': 'NORMAL', 'evidence_kind': 'METHOD_CASE'}},
            'identities': {'SSE:600000': {'exchange': 'SSE', 'board': 'MAIN', 'instrument_type': 'STOCK'}},
            'rules': {'SSE:600000': {'implementation_status': 'ADAPTED', 'rule_id': rule, 'normal_price_limit_percent': '10', 'price_tick_yuan': '.01'}},
            'calendars': {'SSE:600000': {'is_trading_day': True}}, 'evidence_kind': 'METHOD_CASE'}}
    file = save_package(tmp_path / 'qualification.json', p)
    directory = tmp_path / 'data'
    positions = [{'instrument': 'SSE:600000', 'quantity': '300', 'sellable_quantity': sellable, 'reference_cost': '100'}]
    with TestClient(create_app(directory, capability_method_file=file, runtime_role='API')) as client:
        ready(client, permission_status='UNKNOWN', positions=positions)
        granted = client.post('/api/capabilities/grants', json={**method_command(), 'allowed_actions': ['REDUCE', 'EXIT'], 'deployment_fingerprints': p['deployment_fingerprints']})
        assert granted.status_code == 201, granted.text
        grant = granted.json()
        assert client.get('/api/capabilities').json()['state'] == 'METHOD_GRANTED'
        before = client.get('/api/account').json()
        response = client.post('/api/actions/evaluate', json={})
        assert response.status_code == 201, response.text
        value = response.json()
        risk = value['holding_risks'][0]
        assert risk['account_status'] == {'purpose': 'REDUCTION', 'state': 'CONFIRMED_AS_OF', 'fact_scope_state': 'CONFIRMED_AS_OF', 'allowed': True, 'reasons': []}
        assert risk['data_status'] == {'state': 'COMPLETE_CURRENT', 'namespace': 'METHOD_ENGINEERING', 'reasons': []}
        assert risk['model_status'] == 'NOT_APPLICABLE'
        assert risk['capability_status'] == {'state': 'METHOD_GRANTED', 'grant_id': grant['grant_id'], 'allowed_actions': ['REDUCE', 'EXIT'], 'system_usable': False}
        refusal = value['refusals'][0]
        assert refusal['model_status'] == 'UNQUALIFIED'
        assert refusal['execution_eligibility'] == 'BLOCKED'
        assert refusal['capability_status'] == {'state': 'UNGRANTED', 'grant_id': None, 'allowed_actions': [], 'system_usable': False}
        if sellable == '300':
            assert [(d['action'], d['quantity'], d['target_quantity']) for d in value['decisions']] == [('REDUCE', '100', '200')]
            decision = value['decisions'][0]
            assert decision['basis_type'] == 'RISK_POLICY' and decision['grant_id'] == grant['grant_id']
            for field in ['account_status', 'data_status', 'model_status', 'execution_eligibility', 'capability_status']:
                assert decision[field] == risk[field]
            assert decision['execution_eligibility'] == 'METHOD_ONLY'
        else:
            assert value['decisions'] == []
            assert risk['execution_eligibility'] == 'BLOCKED'
            assert 'NO_CONFIRMED_SELLABLE_LOT' in risk['reasons']
        assert value['system_usable'] is False
        assert client.get('/api/account').json() == before
        verify(client, value)
    with TestClient(create_app(directory, capability_method_file=file, runtime_role='API')) as client:
        verify(client, value)
        assert client.post('/api/actions/evaluate', json={}).json() == value
