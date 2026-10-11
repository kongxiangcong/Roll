"""Frozen literal monitoring METHOD cases via public API; no real qualification."""
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package, prepare
from test_intents import intent_command
from roll.research.design import proposal as frozen_design
from test_fills import fill


def monitored_package(count=20, outside=0, missing=0):
    package = action_package()
    end = datetime.fromisoformat(package['required_as_of'])
    sessions = [(end - timedelta(days=count-i-1)).date().isoformat() for i in range(count)]
    # Literal frozen DEVELOPMENT percentiles are .99 and 98.01; incoming data
    # must never refit these. All supplied source identities are METHOD inputs.
    dev = [{'observation_date': f'2025-01-{i%28+1:02d}', 'feature_snapshot': {'features': {'x': i}}} for i in range(100)]
    observations = [{'observation_date': day, 'known_at': package['required_as_of'],
        'instrument': 'SSE:600000', 'features': None if i < missing else {'x': 200 if i < missing+outside else 50},
        'source_binding': 'literal-method-input-' + str(i)} for i, day in enumerate(sessions)]
    package['monitoring_basis'] = {'namespace': 'METHOD_ENGINEERING', 'frozen': {
        'complete_protocol_fingerprint': package['complete_protocol_fingerprint'], 'scope': package['scope'],
        'policy': package['action_packet']['policy'],
        'design': frozen_design({'scope': package['scope'], 'partitions': {
            'DEVELOPMENT': {'rows': 100}, 'CALIBRATION': {'rows': 100}, 'SEALED': {'rows': 0}}})},
        'model_input': {'examples': {'DEVELOPMENT': dev}}, 'eligible_sessions': sessions,
        'observations': observations, 'results': [], 'registered_review_sessions': sessions,
        'method_execution_facts': []}
    return package


@pytest.mark.parametrize('count,expected',[ (29,'CHECKED'), (30,'RESTRICTED') ])
def test_literal_mature_risk_violation_is_only_reviewed_at_registered_boundary(tmp_path, monkeypatch, count, expected):
    monkeypatch.setenv('ROLL_ENV','test')
    package=monitored_package(count)
    basis=package['monitoring_basis']
    def trajectory(exposure):
        return {'curve':[{'date':day,'nav_yuan':'100000','gross_exposure_fraction':exposure,'realized_gain_yuan':'0'}
            for day in basis['eligible_sessions']], 'opportunities':[{'opportunity_key':'literal','action':'BUY'}], 'events':[], 'missing':[]}
    basis['utility_basis']={'namespace':'METHOD_ENGINEERING_LITERAL_CASH_CHAIN',
        'candidate':trajectory('.75'),'comparators':{name:trajectory('0') for name in ['CASH','START_HOLD','MA5_MA20']}}
    file=save_package(tmp_path/'qualification.json',package)
    with TestClient(create_app(tmp_path/'data',capability_method_file=file)) as client:
        grant=prepare(client,package)
        before=client.get('/api/capabilities/grants').json()
        check=client.post('/api/capabilities/monitoring/check',json={'grant_id':grant['grant_id'],'basis':'独立固定METHOD财务暴露 .75，不是实际头寸'}).json()
        assert check['status']==expected,check
        assert check['confirmation_pass_look'] is False
        if count==30:
            assert 'MATURE_RISK_CONSTRAINT_MAXIMUM_EXPOSURE_EXCEEDED' in check['reasons']
            assert check['correction_class']=='MODEL_RESEARCH'
            assert check['mature_review']['utility']['maximum_gross_exposure']==pytest.approx(.75)
            assert check['statistical_verdict']=='INCONCLUSIVE'
            events=client.get('/api/capabilities/events').json()
            event=next(e for e in events if e.get('event_id')==check['restriction_event_id'])
            assert event['reason_code']=='MATURE_EVIDENCE_DETERIORATION'
            assert client.get('/api/actions/current').json()['decisions']==[]
        else:
            assert check['mature_review'] is None and check['statistical_verdict']=='NOT_REVIEWED'
        assert client.get('/api/capabilities/grants').json()==before


@pytest.mark.parametrize('count,outside,missing,expected,reason', [
    (19, 0, 0, 'PENDING', None), (20, 3, 0, 'CHECKED', None),
    (20, 4, 0, 'RESTRICTED', 'FEATURE_OUTSIDE_DEV_REFERENCE_AT_LEAST20_PERCENT'),
    (20, 0, 5, 'RESTRICTED', 'REQUIRED_FEATURE_COVERAGE_BELOW80_PERCENT'),
])
def test_frozen_drift_support_and_normal_warmup_preserve_old_verdict(tmp_path, monkeypatch, count, outside, missing, expected, reason):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = monitored_package(count, outside, missing)
    file = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, package)
        grant = client.get('/api/capabilities/grants').json()[0]
        old = client.post('/api/actions/evaluate', json={}).json()
        response = client.post('/api/capabilities/monitoring/check', json={'grant_id': grant['grant_id'], 'basis': 'literal frozen monitor'})
        assert response.status_code == 201, response.text
        check = response.json()
        assert check['status'] == expected, check
        assert check['reference']['bounds']['x'] == pytest.approx([.99, 98.01])
        assert check['historic_verdict_mutated'] is False and check['confirmation_pass_look'] is False
        assert check['system_usable'] is False and check['evidence_kind'] == 'METHOD_ENGINEERING'
        assert check['complete_protocol_fingerprint'] == grant['complete_protocol_fingerprint']
        assert check['actual_execution_count'] == 0
        assert check['maturity']['review_status'] == 'NOT_AT_REGISTERED_CHECKPOINT'
        if reason:
            assert reason in check['reasons']
            assert client.get('/api/actions/current').json()['decisions'] == []
            assert client.post('/api/intents/prepare', json=intent_command(old)).status_code == 409
            events = client.get('/api/capabilities/events').json()
            restriction = [e for e in events if e.get('reason_code') == 'DATA_DRIFT']
            assert len(restriction) == 1 and restriction[0]['monitoring_check_id'] == check['check_id']
        else:
            assert client.get('/api/capabilities/grants/' + grant['grant_id'] + '/status').json()['state'] == 'METHOD_GRANTED'
        assert client.get('/api/capabilities/grants').json() == [grant]
        assert client.get('/api/actions/evaluations/' + old['evaluation_id']).json() == old
        replay = client.post('/api/capabilities/monitoring/' + check['check_id'] + '/replay')
        assert replay.status_code == 200 and replay.json()['matches_original'] is True, replay.text


@pytest.mark.parametrize('count,status', [(29, 'NOT_AT_REGISTERED_CHECKPOINT'), (30, 'INCONCLUSIVE'), (31, 'MISSED_REGISTERED_CHECKPOINT_GAP')])
def test_registered_maturity_is_unique_never_an_early_pass_or_unmatured_score(tmp_path, monkeypatch, count, status):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = monitored_package(count)
    package['monitoring_basis']['results'] = [
        {'known_at': package['required_as_of'], 'mature_at': package['required_as_of'], 'mature': True, 'label': 1},
        {'known_at': package['required_as_of'], 'mature': False, 'label': None}]
    file = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, package)
        grant = client.get('/api/capabilities/grants').json()[0]
        command = {'grant_id': grant['grant_id'], 'basis': 'registered maturity boundary'}
        check = client.post('/api/capabilities/monitoring/check', json=command)
        assert check.status_code == 201, check.text
        value = check.json()
        assert value['maturity']['review_status'] == status, value
        assert value['maturity']['excluded_unmatured'] == 1
        assert value['maturity']['mature_count'] == (1 if count == 30 else None)
        assert value['statistical_verdict'] == ('INCONCLUSIVE' if count == 30 else 'NOT_REVIEWED')
        assert value['confirmation_pass_look'] is False
        if count == 30:
            repeat = client.post('/api/capabilities/monitoring/check', json=command).json()
            assert repeat['maturity']['review_status'] == 'REGISTERED_CHECKPOINT_ALREADY_CONSUMED'
            assert repeat['maturity']['original_check_id'] == value['check_id']
            assert repeat['statistical_verdict'] == 'NOT_REVIEWED'
        assert client.get('/api/capabilities/grants').json() == [grant]
        assert client.get('/api/capabilities/grants/' + grant['grant_id'] + '/status').json()['state'] == 'METHOD_GRANTED'


def test_registered_review_reports_literal_probability_utility_and_frozen_support_without_pass(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = monitored_package(30)
    basis = package['monitoring_basis']
    basis['development_base_rate'] = .5
    basis['qualified_model_run_id'] = 'literal-method-no-fit-model'
    basis['results'] = [{'known_at': package['required_as_of'], 'mature_at': package['required_as_of'],
        'mature': True, 'label': i % 2, 'forecast_id': 'literal-' + str(i), 'instrument': 'SSE:600000',
        'observation_date': day, 'probability': .8} for i, day in enumerate(basis['eligible_sessions'])]
    def trajectory(last):
        return {'curve': [{'date': day, 'nav_yuan': '100000' if i < 29 else last,
            'gross_exposure_fraction': '0.10', 'realized_gain_yuan': '0'} for i, day in enumerate(basis['eligible_sessions'])],
            'opportunities': [{'opportunity_key': 'literal-opportunity', 'action': 'BUY'}], 'events': [], 'missing': []}
    basis['utility_basis'] = {'namespace': 'METHOD_ENGINEERING_LITERAL_CASH_CHAIN',
        'candidate': trajectory('101000'), 'comparators': {'CASH': trajectory('100000'),
            'START_HOLD': trajectory('100500'), 'MA5_MA20': trajectory('100200')}}
    file = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        grant = prepare(client, package)
        response = client.post('/api/capabilities/monitoring/check', json={'grant_id': grant['grant_id'], 'basis': 'registered literal financial checks'})
        assert response.status_code == 201, response.text
        result = response.json()
        report = result['mature_review']
        assert report['probability']['mature_unique'] == 30
        assert report['probability']['brier'] == pytest.approx(.34)
        assert report['probability']['baseline_brier'] == pytest.approx(.25)
        assert report['utility']['candidate']['net_return'] == pytest.approx(.01)
        assert report['utility']['candidate']['maximum_drawdown'] == 0
        assert report['support']['minimum_effective_time_blocks'] == 30
        assert report['support']['minimum_selected_mature_examples'] == 40
        assert report['support']['effective_time_block_upper_bound'] == 1
        assert report['support']['meets_design_support'] is False
        assert report['status'] == result['statistical_verdict'] == 'INCONCLUSIVE'
        assert result['status'] == 'CHECKED' and result['confirmation_pass_look'] is False
        assert client.get('/api/capabilities/grants/' + grant['grant_id'] + '/status').json()['state'] == 'METHOD_GRANTED'
        assert client.post('/api/capabilities/monitoring/' + result['check_id'] + '/replay').json()['matches_original'] is True
        repeated = client.post('/api/capabilities/monitoring/check', json={'grant_id': grant['grant_id'], 'basis': 'same registered point consumed'}).json()
        assert repeated['maturity']['review_status'] == 'REGISTERED_CHECKPOINT_ALREADY_CONSUMED'
        assert repeated['mature_review'] is None
        assert repeated['statistical_verdict'] == 'NOT_REVIEWED'


def test_required_source_unknown_during_warmup_restricts_and_cannot_use_user_resume(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = monitored_package(3)
    package['monitoring_basis']['observations'][0]['source_binding'] = None
    file = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, package)
        grant = client.get('/api/capabilities/grants').json()[0]
        check = client.post('/api/capabilities/monitoring/check', json={'grant_id': grant['grant_id'], 'basis': 'missing required source'}).json()
        assert check['status'] == 'RESTRICTED'
        assert 'REQUIRED_MONITORING_SOURCE_UNVERIFIED' in check['reasons']
        assert check['maturity']['review_status'] == 'NOT_AT_REGISTERED_CHECKPOINT'
        control = client.get('/api/capabilities/lifecycle').json()
        response = client.post('/api/capabilities/lifecycle', json={'grant_id': grant['grant_id'], 'scope': 'MODEL', 'state': 'ACTIVE',
            'reason_code': 'USER_PAUSE', 'resume_event_id': check['restriction_event_id'], 'reason': '不能伪装成主动暂停',
            'expected_version': control['version'], 'idempotency_key': 'wrong'})
        assert response.status_code == 409
        assert client.get('/api/actions/current').json()['decisions'] == []


def test_claimed_mature_label_after_evidence_cutoff_stays_unscored(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = monitored_package(30)
    package['monitoring_basis']['results'] = [{'known_at': package['required_as_of'],
        'mature_at': (datetime.fromisoformat(package['required_as_of']) + timedelta(days=1)).isoformat(),
        'mature': True, 'label': 1}]
    file = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        grant = prepare(client, package)
        result = client.post('/api/capabilities/monitoring/check', json={'grant_id': grant['grant_id'], 'basis': 'fixed future label cutoff'})
        assert result.status_code == 201, result.text
        value = result.json()
        assert value['maturity']['mature_count'] == 0
        assert value['maturity']['excluded_unmatured'] == 1
        assert value['statistical_verdict'] == 'INCONCLUSIVE'
        assert client.get('/api/capabilities/grants/' + grant['grant_id'] + '/status').json()['state'] == 'METHOD_GRANTED'


def test_actual_26_partial_fill_keeps_exact_fee_time_and_unknown_scenario_components(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = monitored_package(20)
    file = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        grant = prepare(client, package)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        intent = client.post('/api/intents/prepare', json=intent_command(evaluation)).json()
        actual = fill(2, 'method-partial-outside-band')
        actual['payload'].update(quantity='100', price='155.00', effective_at=package['required_as_of'])
        actual['payload']['fee']['amount'] = '7.00'
        draft = client.post('/api/account/drafts', json=actual).json()
        confirmed = client.post('/api/account/confirm', json={'draft_id': draft['draft_id'], 'idempotency_key': 'partial-fill',
            'fill_allocations': [{'intent_id': intent['intent_id'], 'fill_record_id': 'method-partial-outside-band',
                'allocated_quantity': '100', 'association_status': 'USER_CONFIRMED'}]})
        assert confirmed.status_code == 200, confirmed.text
        allocations = client.get('/api/intents/allocations').json()
        result = client.post('/api/capabilities/monitoring/check', json={'grant_id': grant['grant_id'], 'basis': '实际26回报字段与冻结假设比较'})
        assert result.status_code == 201, result.text
        value = result.json()
        assert value['status'] == 'RESTRICTED' and value['actual_execution_count'] == 1
        observation = value['actual_execution_observations'][0]
        assert observation['allocation'] == allocations[0]
        assert observation['fill_fraction'] == '0.5'
        assert observation['actual_fee_yuan']['amount'] == '7.00'
        assert observation['price_in_frozen_window'] is False
        assert observation['delay'] is None
        assert observation['commission_scenario_rate'] is None and observation['slippage_each_side_rate'] is None
        assert observation['decision_time_chain']['delivered_at'] is None
        assert 'PRICE_OUTSIDE_FROZEN_WINDOW' in value['reasons']
        assert 'ACTUAL_EXECUTION_ASSUMPTIONS_UNKNOWN' in value['reasons']
        assert value['correction_class'] == 'EXECUTION_ASSUMPTION'
        assert client.get('/api/intents/allocations').json() == allocations
        assert client.get('/api/actions/evaluations/' + evaluation['evaluation_id']).json() == evaluation
