from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import package, save_package
from test_capabilities import ready, method_command
from test_funding import funding
from datetime import datetime, timezone, timedelta
import pytest
import copy
from concurrent.futures import ThreadPoolExecutor
import time
import httpx


def test_shrink_during_computation_does_not_wait_for_a_writer_lock_or_publish_old_boundary(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    p['action_packet']['method_publish_delay_ms'] = 1500
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        existing = client.post('/api/actions/evaluate', json={}).json()
        assert len(existing['decisions']) == 1
        with ThreadPoolExecutor(max_workers=2) as pool:
            computing = pool.submit(client.post, '/api/actions/evaluate', json={})
            time.sleep(.4)
            started = time.monotonic()
            shrunk = client.post('/api/funding/confirm', json=funding(2, total_exposure='10000.00', single_exposure='10000.00', cash_reserve='90000.00'))
            assert shrunk.status_code == 200
            assert time.monotonic() - started < 1.0
            result = computing.result().json()
        assert result['decisions'] == []
        assert result['limitations'] == ['CURRENT_VERSION_CHANGED_BEFORE_PUBLICATION']
        assert result['evaluation_id'] != existing['evaluation_id']
        assert client.get(f"/api/actions/evaluations/{existing['evaluation_id']}").json() == existing
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert client.post(f"/api/actions/evaluations/{result['evaluation_id']}/replay").json()['matches_original'] is True


def test_method_host_without_user_funding_stays_facts_only_and_production_reopening_cannot_use_it(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        result = client.post('/api/actions/evaluate', json={})
        assert result.status_code == 201
        assert result.json()['decisions'] == []
        assert 'FUNDING_NOT_ENABLED' in result.json()['limitations']
        prepare(client, p)
        assert len(client.post('/api/actions/evaluate', json={}).json()['decisions']) == 1
    monkeypatch.delenv('ROLL_ENV', raising=False)
    with TestClient(create_app(tmp_path / 'data')) as client:
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert client.post('/api/actions/evaluate', json={}).json()['decisions'] == []


@pytest.mark.parametrize('change,reason', [
    ({'fees_yuan': None}, 'PRICE_OR_FEES_UNKNOWN'),
    ({'rule_status': 'UNSUPPORTED'}, 'RULE_UNKNOWN_OR_UNSUPPORTED'),
    ({'market_status': 'UNKNOWN'}, 'CURRENT_SPECIAL_STATUS_UNKNOWN_OR_NOT_NORMAL'),
    ({'daily_completion': 'UNCONFIRMED_CURRENT_DAY'}, 'DAILY_INPUT_INCOMPLETE_INTRADAY_VOLUME_EXCLUDED'),
    ({'quote_at': '2026-10-07T10:00:00+08:00'}, 'QUOTE_STALE_FOR_PURPOSE'),
    ({'forecast_horizon': 10}, 'FORECAST_HORIZON_OUTSIDE_POLICY'),
])
def test_hard_data_failures_do_not_get_scored_away_and_keep_separate_quote_daily_times(tmp_path, monkeypatch, change, reason):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    for row in p['action_packet']['opportunities']: row.update(change)
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        value = client.post('/api/actions/evaluate', json={}).json()
        assert value['decisions'] == []
        assert reason in value['refusals'][0]['reasons']
        assert value['refusals'][0]['cumulative_volume'] == '12345'
        assert value['refusals'][0]['forecast_cutoff'] == p['required_as_of']
        assert client.post('/api/actions/evaluate', json={'probability': 1, 'gates': {'G7': 'PASS'}}).status_code == 422


def test_stale_action_valuation_never_assumes_zero_loss_even_if_qualification_is_active(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    p['action_packet']['loss_facts'] = {**p['loss_facts'], 'valuation_status': 'STALE', 'net_assets': None}
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        result = client.post('/api/actions/evaluate', json={}).json()
        assert result['decisions'] == []
        assert result['joint_budget']['loss']['remaining_loss_allowance'] is None
        assert 'LOSS_BOUNDARY_UNAVAILABLE_OR_PAUSED' in result['limitations']


@pytest.mark.parametrize('sellable', ['300', '0'])
@pytest.mark.parametrize('permission_status', ['NOT_OPEN', 'UNKNOWN'])
def test_independently_qualified_reduction_with_purchase_permission_not_open_keeps_all_holding_risks(tmp_path, monkeypatch, sellable, permission_status):
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
    rule_id = 'SSE-MAIN-A-2026-07-06'
    p['action_packet'] = {'namespace': 'METHOD_ENGINEERING', 'as_of': p['required_as_of'], 'expires_at': p['expires_at'],
        'opportunities': [], 'loss_facts': p['loss_facts'], 'risk_inputs': {
            'policy': {'policy_id': 'risk-method', 'policy_fingerprint': 'e' * 64, 'authorization': {**funding()['authorization'], 'version': 1, 'loss_origin_at': '2026-10-07T02:00:00+00:00'},
                       'scope': p['scope'], 'rule_ids': {'SSE:600000': rule_id}},
            'required_as_of': p['required_as_of'], 'consumer_knowledge_cutoff': clock,
            'quotes': {'SSE:600000': {'last': '100', 'adjustment': 'RAW', 'currency': 'CNY', 'errors': [], 'upstream_at': p['required_as_of'],
                    'available_at': p['required_as_of'], 'method_status': 'NORMAL', 'evidence_kind': 'METHOD_CASE'}},
            'identities': {'SSE:600000': {'exchange': 'SSE', 'board': 'MAIN', 'instrument_type': 'STOCK'}},
            'rules': {'SSE:600000': {'implementation_status': 'ADAPTED', 'rule_id': rule_id, 'normal_price_limit_percent': '10', 'price_tick_yuan': '.01'}},
            'calendars': {'SSE:600000': {'is_trading_day': True}}, 'evidence_kind': 'METHOD_CASE'}}
    file = save_package(tmp_path / 'qualification.json', p)
    positions = [{'instrument': 'SSE:600000', 'quantity': '300', 'sellable_quantity': sellable, 'reference_cost': '100'},
                 {'instrument': 'SSE:600099', 'quantity': '50', 'sellable_quantity': None, 'reference_cost': None}]
    # A quantity-unknown unrelated holding would block the grant; retain a known outside-scope holding here.
    positions[1]['sellable_quantity'] = '50'
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client, permission_status=permission_status, positions=positions)
        command = {**method_command(), 'allowed_actions': ['REDUCE', 'EXIT'], 'deployment_fingerprints': p['deployment_fingerprints']}
        granted = client.post('/api/capabilities/grants', json=command)
        assert granted.status_code == 201, granted.text
        result = client.post('/api/actions/evaluate', json={}).json()
        assert [(d['action'], d['quantity'], d['target_quantity']) for d in result['decisions']] == ([('REDUCE', '100', '200')] if sellable == '300' else [])
        if sellable == '300': assert result['decisions'][0]['basis_type'] == 'RISK_POLICY'
        else: assert 'NO_CONFIRMED_SELLABLE_LOT' in result['holding_risks'][0]['reasons']
        assert len(result['holding_risks']) == 2
        assert 'OUTSIDE_FROZEN_POLICY_SCOPE_FACTS_RETAINED' in result['holding_risks'][1]['reasons']
        assert client.post(f"/api/actions/evaluations/{result['evaluation_id']}/replay").json()['matches_original'] is True


def action_package():
    p = package()
    p['scope']['instruments'] = ['SSE:600000', 'SSE:600001']
    p['current_data']['instruments'] = p['scope']['instruments']
    p['action_packet'] = {'namespace': 'METHOD_ENGINEERING', 'complete_protocol_fingerprint': p['complete_protocol_fingerprint'],
        'policy': {'version': '20-policy-v1', 'probability_threshold': '0.60', 'quantity': '200', 'maximum_gross_exposure': '0.50',
                   'ordering': 'descending_probability_then_instrument_then_forecast_id', 'exit': 'HORIZON_SESSION20_CLOSE'},
        'as_of': p['required_as_of'], 'expires_at': p['expires_at'], 'loss_facts': p['loss_facts'],
        'opportunities': [{'instrument': i, 'forecast_id': 'forecast-' + i, 'probability': probability,
            'quantity': '200', 'price_lower_yuan': '135.00', 'price_upper_yuan': '150.00', 'fees_yuan': '5.00',
            'quote_at': p['required_as_of'], 'quote_available_at': p['required_as_of'], 'cumulative_volume': '12345',
            'forecast_cutoff': p['required_as_of'], 'forecast_horizon': 20, 'daily_completion': 'COMPLETE',
            'rule_id': 'MAIN-A-2026', 'rule_status': 'ADAPTED', 'market_status': 'CONFIRMED_NORMAL',
            'calendar_open': True, 'market': 'SSE', 'board': 'MAIN', 'input_gaps': []}
            for i, probability in [('SSE:600001', '.70'), ('SSE:600000', '.80')]]}
    return p


def prepare(client, p, positions=None):
    ready(client, positions=positions)
    for instrument in p['scope']['instruments']:
        listing = client.get('/api/market/list').json()
        if instrument not in {m['instrument'] for m in listing['members']}:
            assert client.post('/api/market/watch', json={'instrument': instrument, 'operation': 'ADD', 'expected_list_version': listing['version']}).status_code == 200
    assert client.post('/api/funding/confirm', json=funding(1, capital_amount='100000.00', total_exposure='60000.00', single_exposure='40000.00')).status_code == 200
    command = {**method_command(), 'scope': p['scope'], 'allowed_actions': ['BUY'], 'expected_funding_version': 2}
    response = client.post('/api/capabilities/grants', json=command)
    assert response.status_code == 201, response.text
    return response.json()


def test_qualified_host_packet_allocates_stable_joint_cash_with_fees_without_double_broker_freeze(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        grant = prepare(client, p)
        before = client.get('/api/account').json()
        response = client.post('/api/actions/evaluate', json={})
        assert response.status_code == 201, response.text
        value = response.json()
        assert [(r['instrument'], r['action'], r['quantity']) for r in value['decisions']] == [('SSE:600000', 'BUY', '200')]
        assert value['joint_budget']['available_after_user_reserve_yuan'] == '50000.10'
        assert value['joint_budget']['reserved_yuan'] == '30005.00'
        assert 'INSUFFICIENT_JOINT_CASH' in value['refusals'][0]['reasons']
        assert value['decisions'][0]['grant_id'] == grant['grant_id']
        assert value['namespace'] == 'METHOD_ENGINEERING' and value['system_usable'] is False
        assert client.get('/api/account').json() == before
        assert client.post(f"/api/actions/evaluations/{value['evaluation_id']}/replay").json()['matches_original'] is True
        assert client.post('/api/actions/evaluate', json={}).json() == value


def test_funding_shrink_invalidates_current_card_but_keeps_original_revision_and_one_audit(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        value = client.post('/api/actions/evaluate', json={}).json()
        assert len(value['decisions']) == 1
        assert client.post('/api/funding/confirm', json=funding(2, total_exposure='10000.00', single_exposure='10000.00', cash_reserve='90000.00')).status_code == 200
        current = client.get('/api/actions/current').json()
        assert current['decisions'] == []
        assert current['invalidated'][0]['reasons'] == ['FUNDING_VERSION_CHANGE', 'GRANT_RESTRICTED']
        assert client.get(f"/api/actions/evaluations/{value['evaluation_id']}").json() == value
        client.get('/api/actions/current')
        assert len([e for e in client.get('/api/actions/events').json() if e['event_type'] == 'ACTION_INVALIDATED']) == 1
        audit = client.get('/api/actions/audit').json()
        assert audit['invalidated_actions'] == {'status': 'CHECKED', 'value': 1}
        assert audit['action_flips'] == {'status': 'CHECKED', 'value': 0}


def test_ungranted_evaluation_retains_observations_and_immutable_refusal(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        first = client.post('/api/actions/evaluate', json={})
        assert first.status_code == 201, first.text
        value = first.json()
        assert value['decisions'] == []
        assert 'TECHNICAL_CAPABILITY_UNGRANTED' in value['limitations']
        assert client.get('/api/actions/current').json()['evaluation']['evaluation_id'] == value['evaluation_id']
        assert client.post('/api/actions/evaluate', json={}).json() == value
        assert client.post(f"/api/actions/evaluations/{value['evaluation_id']}/replay").json()['matches_original'] is True
        assert len(client.get('/api/actions/events').json()) == 1


def test_current_list_removal_invalidates_old_card_and_refuses_new_entry_outside_list(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        for instrument in p['scope']['instruments']:
            listing = client.get('/api/market/list').json()
            assert client.post('/api/market/watch', json={'instrument': instrument, 'operation': 'ADD', 'expected_list_version': listing['version']}).status_code == 200
        original = client.post('/api/actions/evaluate', json={}).json()
        assert [(d['instrument'], d['quantity']) for d in original['decisions']] == [('SSE:600000', '200')]
        listing = client.get('/api/market/list').json()
        assert client.post('/api/market/watch', json={'instrument': 'SSE:600000', 'operation': 'REMOVE', 'expected_list_version': listing['version']}).status_code == 200
        current = client.get('/api/actions/current').json()
        assert current['decisions'] == []
        assert current['invalidated'][0]['reasons'] == ['DATA_OR_LIST_CHANGE']
        assert client.get(f"/api/actions/evaluations/{original['evaluation_id']}").json() == original
        client.get('/api/actions/current')
        assert len([e for e in client.get('/api/actions/events').json() if e['event_type'] == 'ACTION_INVALIDATED']) == 1
        successor = client.post('/api/actions/evaluate', json={}).json()
        refusal = next(r for r in successor['refusals'] if r['instrument'] == 'SSE:600000')
        assert 'OUTSIDE_CURRENT_FINITE_LIST' in refusal['reasons']
        assert client.post(f"/api/actions/evaluations/{original['evaluation_id']}/replay").json()['matches_original'] is True


def test_current_expiry_keeps_original_conditions_and_replay(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        original = client.post('/api/actions/evaluate', json={}).json()
        monkeypatch.setattr('roll.decisions.actions.now', lambda: p['expires_at'])
        current = client.get('/api/actions/current').json()
        assert current['decisions'] == []
        assert current['invalidated'][0]['reasons'] == ['EXPIRED']
        assert client.get(f"/api/actions/evaluations/{original['evaluation_id']}").json() == original
        assert client.post(f"/api/actions/evaluations/{original['evaluation_id']}/replay").json()['matches_original'] is True
        expired = client.post('/api/actions/evaluate', json={}).json()
        assert expired['decisions'] == []
        assert expired['limitations'] == ['ACTION_EXPIRED_BEFORE_PUBLICATION']
        assert expired['evaluation_id'] != original['evaluation_id']
        assert client.post('/api/actions/evaluate', json={}).json() == expired


def test_new_public_quote_evidence_invalidates_current_card_without_changing_account(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    quote = [''] * 60
    for i, v in {2: '600000', 3: '136', 4: '135', 5: '135', 6: '100', 30: '20261009103000', 33: '137', 34: '134'}.items(): quote[i] = v
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=('v_sh600000="' + '~'.join(quote) + '";').encode('gbk')))
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file, market_transport=transport)) as client:
        prepare(client, p)
        original = client.post('/api/actions/evaluate', json={}).json()
        account = client.get('/api/account').json()
        request = client.post('/api/data/requests', json={'instruments': ['SSE:600000'], 'groups': ['QUOTE'], 'purpose': 'OBSERVATION', 'start_date': '2026-10-09', 'end_date': '2026-10-09'}).json()
        retrieved = client.post(f"/api/data/requests/{request['request_id']}/retrieve")
        assert retrieved.status_code == 200, retrieved.text
        current = client.get('/api/actions/current').json()
        assert current['decisions'] == []
        assert current['invalidated'][0]['reasons'] == ['DATA_OR_LIST_CHANGE']
        assert client.get('/api/account').json() == account
        assert client.post(f"/api/actions/evaluations/{original['evaluation_id']}/replay").json()['matches_original'] is True


def test_list_change_during_compute_rejects_publication_under_latest_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    p['action_packet']['method_publish_delay_ms'] = 1500
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        existing = client.post('/api/actions/evaluate', json={}).json()
        assert len(existing['decisions']) == 1
        with ThreadPoolExecutor(max_workers=2) as pool:
            computing = pool.submit(client.post, '/api/actions/evaluate', json={})
            time.sleep(.4)
            listing = client.get('/api/market/list').json()
            assert client.post('/api/market/watch', json={'instrument': 'SSE:600000', 'operation': 'REMOVE', 'expected_list_version': listing['version']}).status_code == 200
            result = computing.result().json()
        assert result['decisions'] == []
        assert result['limitations'] == ['CURRENT_DATA_OR_LIST_CHANGED_BEFORE_PUBLICATION']
        assert result['evaluation_id'] != existing['evaluation_id']
        assert client.get(f"/api/actions/evaluations/{existing['evaluation_id']}").json() == existing
        assert client.post(f"/api/actions/evaluations/{result['evaluation_id']}/replay").json()['matches_original'] is True


def test_existing_receipt_does_not_bypass_expiry_during_repeated_computation(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    p['action_packet']['method_publish_delay_ms'] = 1500
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        existing = client.post('/api/actions/evaluate', json={}).json()
        with ThreadPoolExecutor(max_workers=2) as pool:
            computing = pool.submit(client.post, '/api/actions/evaluate', json={})
            time.sleep(.4)
            monkeypatch.setattr('roll.decisions.actions.now', lambda: p['expires_at'])
            result = computing.result().json()
        assert result['decisions'] == []
        assert result['limitations'] == ['ACTION_EXPIRED_BEFORE_PUBLICATION']
        assert result['evaluation_id'] != existing['evaluation_id']
        assert client.get(f"/api/actions/evaluations/{existing['evaluation_id']}").json() == existing
        assert client.post(f"/api/actions/evaluations/{result['evaluation_id']}/replay").json()['matches_original'] is True


def test_new_public_valuation_invalidates_current_action_even_with_same_account_and_funding(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        existing = client.post('/api/actions/evaluate', json={}).json()
        before = client.get('/api/account').json()
        response = client.post('/api/account/valuations', json={'as_of': p['required_as_of'], 'origin_at': '2026-10-07T10:00:00+08:00', 'scope_kind': 'ACCOUNT', 'scope_id': 'account-1', 'baseline_account_version': 2})
        assert response.status_code == 201, response.text
        assert client.get('/api/account').json() == before
        assert client.get('/api/funding').json()['version'] == 2
        current = client.get('/api/actions/current').json()
        assert current['decisions'] == []
        assert current['invalidated'][0]['reasons'] == ['DATA_OR_LIST_CHANGE']
        assert client.get(f"/api/actions/evaluations/{existing['evaluation_id']}").json() == existing


def test_persisted_loss_peak_survives_restart_and_funding_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    # Confirmed cash100000.10 +1 METHOD share originally marked6135 =106135.10;
    # that share marked135 now gives100135.10 and exactly6000 drawdown.
    p['loss_facts'] = {**p['loss_facts'], 'baseline_assets': '106135.10', 'net_assets': '100135.10', 'unrealized_pnl': '-6000.00'}
    p['action_packet']['loss_facts'] = p['loss_facts']
    file = save_package(tmp_path / 'decline.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client, positions=[{'instrument': 'SSE:600000', 'quantity': '1', 'sellable_quantity': '1', 'reference_cost': '6135.00'}])
        listing = client.get('/api/market/list').json()
        assert client.post('/api/market/watch', json={'instrument': 'SSE:600001', 'operation': 'ADD', 'expected_list_version': listing['version']}).status_code == 200
        assert client.post('/api/funding/confirm', json=funding(1, single_exposure='40000.00')).status_code == 200
        decline = client.post('/api/actions/evaluate', json={}).json()
        assert decline['joint_budget']['loss']['peak_loss'] == '6000.00'
        assert decline['decisions'] == []
    # Keep the host packet immutable. Public restart/expansion verifies stored
    # state; the existing pure loss calculation separately verifies rebound.
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        assert client.post('/api/funding/confirm', json=funding(2, single_exposure='40000.00', loss_threshold='10000.00')).status_code == 200
        result = client.post('/api/actions/evaluate', json={}).json()
        assert result['joint_budget']['loss']['peak_loss'] == '6000.00'
        assert result['joint_budget']['loss']['remaining_loss_allowance'] == '4000.00'
        assert result['joint_budget']['loss']['triggered'] is True
        assert result['joint_budget']['loss']['status'] == 'PAUSED'
        assert result['decisions'] == []
        assert 'LOSS_BOUNDARY_UNAVAILABLE_OR_PAUSED' in result['limitations']
        assert client.post(f"/api/actions/evaluations/{result['evaluation_id']}/replay").json()['matches_original'] is True
        from roll.decisions.funding import LossFacts, evaluate_loss
        rebound = LossFacts(**{**p['loss_facts'], 'net_assets': '106135.10', 'unrealized_pnl': '0.00'})
        numeric = evaluate_loss(client.get('/api/funding').json(), rebound, result['joint_budget']['loss'])
        assert numeric['loss'] == '0.00' and numeric['peak_loss'] == '6000.00'
        assert numeric['remaining_loss_allowance'] == '4000.00' and numeric['triggered'] is True
        assert numeric['status'] == 'PAUSED'
