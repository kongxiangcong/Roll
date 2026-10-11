"""Literal public risk-first contract; isolated METHOD archives and real SQLite."""
from datetime import datetime, timedelta, timezone
import json
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from action_order_method import paired_package, grant_command
from test_capabilities import ready


def setup(client, value):
    ready(client, positions=[{'instrument': 'SSE:600000', 'quantity': '300', 'sellable_quantity': '300', 'reference_cost': '100'}])
    for instrument in value['scope']['instruments']:
        listing = client.get('/api/market/list').json()
        if instrument not in {r['instrument'] for r in listing['members']}:
            response = client.post('/api/market/watch', json={'instrument': instrument, 'operation': 'ADD', 'expected_list_version': listing['version']})
            assert response.status_code == 200, response.text


def method_clock(monkeypatch):
    import capability_method_app
    anchor = (datetime.now(timezone(timedelta(hours=8))) - timedelta(days=1)).replace(hour=15, minute=5, second=0, microsecond=0)
    monkeypatch.setattr(capability_method_app, 'ANCHOR', anchor)
    clock = (anchor + timedelta(minutes=1)).isoformat()
    monkeypatch.setenv('ROLL_ENV', 'test')
    monkeypatch.setattr('roll.decisions.capabilities.now', lambda: clock)
    monkeypatch.setattr('roll.decisions.actions.now', lambda: clock)


def record(path, name, value):
    (path / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def test_two_host_candidates_register_distinct_public_grants_and_proofs(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    value = paired_package()
    file = save_package(tmp_path / 'qualification.json', value)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file, runtime_role='API')) as client:
        setup(client, value)
        profit = client.post('/api/capabilities/grants', json=grant_command(value, 'profit'))
        record(tmp_path, 'profit-grant', profit.json())
        assert profit.status_code == 201, profit.text
        risk = client.post('/api/capabilities/grants', json=grant_command(value['risk_qualification'], 'risk'))
        record(tmp_path, 'risk-grant', risk.json())
        assert risk.status_code == 201, risk.text
        assert profit.json()['candidate_kind'] == 'PROFIT_MODEL'
        assert risk.json()['candidate_kind'] == 'RISK_POLICY'
        assert profit.json()['grant_id'] != risk.json()['grant_id']
        assert profit.json()['proof_id'] != risk.json()['proof_id']
        for grant in [profit.json(), risk.json()]:
            status = client.get('/api/capabilities/grants/' + grant['grant_id'] + '/status').json()
            assert status['state'] == 'METHOD_GRANTED', status
            assert status['grant']['system_usable'] is False
            assert client.get('/api/capabilities/proofs/' + grant['proof_id'] + '/check').status_code == 200


def test_independent_risk_precedes_buy_and_one_new_entry_limit(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    value = paired_package()
    file = save_package(tmp_path / 'qualification.json', value)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file, runtime_role='API')) as client:
        setup(client, value)
        grants = []
        for package, key in [(value, 'profit'), (value['risk_qualification'], 'risk')]:
            response = client.post('/api/capabilities/grants', json=grant_command(package, key))
            assert response.status_code == 201, response.text
            grants.append(response.json())
        response = client.post('/api/actions/evaluate', json={})
        record(tmp_path, 'risk-and-buy', response.json())
        assert response.status_code == 201, response.text
        result = response.json()
        assert [(r['instrument'], r['action'], r['quantity'], r['target_quantity']) for r in result['decisions']] == [
            ('SSE:600000', 'REDUCE', '100', '200'), ('SSE:600001', 'BUY', '200', '200')]
        risk, buy = result['decisions']
        assert risk['grant_id'] == grants[1]['grant_id']
        assert buy['grant_id'] == grants[0]['grant_id']
        assert risk['model_status'] == 'NOT_APPLICABLE'
        assert buy['model_status'] == 'METHOD_ENGINEERING'
        assert all(row['execution_eligibility'] == 'METHOD_ONLY' and row['capability_status']['state'] == 'METHOD_GRANTED' for row in result['decisions'])
        assert result['system_usable'] is False
        assert result['joint_budget']['existing_exposure_yuan'] == '30000.00'
        assert result['joint_budget']['reserved_yuan'] == '10005.00'
        refused = next(row for row in result['refusals'] if row['instrument'] == 'SSE:600002')
        assert refused['reasons'] == ['ONE_NEW_ENTRY_LIMIT']
        assert client.get('/api/actions/current').json()['decisions'] == result['decisions']
        assert client.post('/api/actions/evaluations/' + result['evaluation_id'] + '/replay').json()['matches_original'] is True
        account = client.get('/api/account').json()
        assert account['positions'][0]['quantity'] == '300'


@pytest.mark.parametrize('profit_input', ['missing_policy', 'unsupported_policy', 'ungranted_invalid_probability'])
def test_unavailable_profit_input_does_not_hide_independent_risk(tmp_path, monkeypatch, profit_input):
    method_clock(monkeypatch)
    value = paired_package()
    packet = value['action_packet']
    if profit_input == 'missing_policy':
        packet.pop('policy')
    elif profit_input == 'unsupported_policy':
        packet['policy'] = {'version': 'UNSUPPORTED'}
    else:
        for opportunity in packet['opportunities']:
            opportunity['probability'] = 'NOT_A_QUALIFIED_MODEL_INPUT'
    file = save_package(tmp_path / 'qualification.json', value)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file, runtime_role='API'), raise_server_exceptions=False) as client:
        setup(client, value)
        if profit_input != 'ungranted_invalid_probability':
            profit = client.post('/api/capabilities/grants', json=grant_command(value, 'profit'))
            assert profit.status_code == 201, profit.text
        granted = client.post('/api/capabilities/grants', json=grant_command(value['risk_qualification'], 'risk'))
        assert granted.status_code == 201, granted.text
        response = client.post('/api/actions/evaluate', json={})
        record(tmp_path, 'risk-with-unavailable-profit', {'status': response.status_code, 'body': response.text})
        assert response.status_code == 201, response.text
        result = response.json()
        assert [(r['instrument'], r['action'], r['quantity'], r['target_quantity']) for r in result['decisions']] == [('SSE:600000', 'REDUCE', '100', '200')]
        assert result['decisions'][0]['grant_id'] == granted.json()['grant_id']
        assert result['decisions'][0]['model_status'] == 'NOT_APPLICABLE'
        assert result['decisions'][0]['capability_status']['state'] == 'METHOD_GRANTED'
        assert result['decisions'][0]['execution_eligibility'] == 'METHOD_ONLY'
        if profit_input != 'ungranted_invalid_probability':
            assert 'FROZEN_POLICY_NOT_SUPPORTED' in result['limitations']
        else:
            assert all(row['model_status'] == 'UNQUALIFIED' and row['capability_status']['state'] == 'UNGRANTED' and row['execution_eligibility'] == 'BLOCKED' for row in result['refusals'])
            assert all('PROFIT_CAPABILITY_NOT_CURRENT_IN_SCOPE' in row['reasons'] for row in result['refusals'])
        assert client.post('/api/actions/evaluations/' + result['evaluation_id'] + '/replay').json()['matches_original'] is True


@pytest.mark.parametrize('shared_field', ['account_version', 'current_data', 'loss_facts'])
def test_paired_host_rejects_conflicting_shared_fact_binding(tmp_path, monkeypatch, shared_field):
    method_clock(monkeypatch)
    value = paired_package()
    value['risk_qualification'][shared_field] = {'conflicting': 'METHOD fixture'}
    file = save_package(tmp_path / 'qualification.json', value)
    with pytest.raises(ValueError, match='CAPABILITY_METHOD_RISK_BINDING_INVALID'):
        create_app(tmp_path / 'data', capability_method_file=file, runtime_role='API')


def test_child_failed_gate_cannot_borrow_profit_qualification(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    value = paired_package()
    value['risk_qualification']['gates']['STRESS_EXECUTION'] = 'FAIL'
    file = save_package(tmp_path / 'qualification.json', value)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file, runtime_role='API')) as client:
        setup(client, value)
        profit = client.post('/api/capabilities/grants', json=grant_command(value, 'profit'))
        assert profit.status_code == 201, profit.text
        risk = client.post('/api/capabilities/grants', json=grant_command(value['risk_qualification'], 'risk'))
        record(tmp_path, 'child-gate-refusal', risk.json())
        assert risk.status_code == 409, risk.text
        assert 'REQUIRED_GATES_NOT_PASS' in risk.json()['detail']['reasons']
        result = client.post('/api/actions/evaluate', json={}).json()
        assert [(d['instrument'], d['action']) for d in result['decisions']] == [('SSE:600001', 'BUY')]
        assert result['holding_risks'][0]['execution_eligibility'] == 'BLOCKED'
        assert result['holding_risks'][0]['capability_status']['state'] == 'UNGRANTED'


def test_paired_method_is_refused_in_production_and_changed_child_breaks_envelope(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    value = paired_package()
    file = save_package(tmp_path / 'qualification.json', value)
    monkeypatch.delenv('ROLL_ENV')
    with pytest.raises(ValueError, match='CAPABILITY_METHOD_HOST_TEST_ONLY'):
        create_app(tmp_path / 'prod', capability_method_file=file, runtime_role='API')
    monkeypatch.setenv('ROLL_ENV', 'test')
    envelope = json.loads(file.read_text(encoding='utf-8'))
    envelope['package']['risk_qualification']['deployment_fingerprints']['policy'] = 'f' * 64
    file.write_text(json.dumps(envelope), encoding='utf-8')
    with pytest.raises(ValueError, match='CAPABILITY_METHOD_PACKAGE_INVALID'):
        create_app(tmp_path / 'tampered', capability_method_file=file, runtime_role='API')
