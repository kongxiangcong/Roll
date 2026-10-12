from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package, prepare
from test_fills import fill
from test_account import permission_change, submit, baseline
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_funding import funding
from datetime import datetime, timedelta
from test_reviews import wait_result
from test_capabilities import ready, method_command
from roll.decisions.actions import fingerprint
import json
import os
from pathlib import Path


@pytest.mark.parametrize('status', ['NOT_OPEN', 'UNKNOWN'])
def test_permission_change_rejects_old_prepare_but_external_pending_survives(tmp_path, monkeypatch, status):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        command = intent_command(evaluation)
        intent = client.post('/api/intents/prepare', json=command).json()
        assert client.post('/api/intents/' + intent['intent_id'] + '/declare', json={
            'state': 'OPERATION_PENDING', 'idempotency_key': 'pending'}).status_code == 200
        assert submit(client, permission_change(evaluation['account_version'], status), 'permissions').status_code == 200
        assert client.post('/api/intents/prepare', json=command).json() == intent
        assert client.post('/api/intents/prepare', json={**command, 'idempotency_key': 'new-prepare'}).status_code == 409
        pending = client.get('/api/intents').json()
        assert pending['pending_attribution'] is True
        assert pending['intents'][0]['status'] == 'OPERATION_PENDING'
        assert pending['unreflected_reservation_yuan'] == '30005.00'
        assert client.post('/api/intents/' + intent['intent_id'] + '/declare', json={
            'state': 'NOT_EXECUTED', 'reason': '未继续操作', 'idempotency_key': 'false-cancel'}).status_code == 409


def test_competing_prepare_has_one_active_entry_and_current_evaluation_consumes_intent_budget(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        command = intent_command(evaluation)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda k: client.post('/api/intents/prepare', json={**command, 'idempotency_key': k}), ['one', 'two']))
        assert sorted(r.status_code for r in responses) == [201, 409]
        assert len(client.get('/api/intents').json()['intents']) == 1
        fresh = client.post('/api/actions/evaluate', json={}).json()
        assert fresh['decisions'] == []
        assert fresh['joint_budget']['unreflected_intent_reservation_yuan'] == '30005.00'


def intent_command(evaluation):
    d = evaluation['decisions'][0]
    return {'decision_id': d['decision_id'], 'expected_evaluation_id': evaluation['evaluation_id'],
            'expected_account_version': evaluation['account_version'], 'expected_funding_version': evaluation['funding_version'],
            'expected_grant_version': 1, 'price_yuan': '140.00', 'idempotency_key': 'prepare-1'}


def test_exact_500_proposal_300_actual_is_a_declared_method_policy_not_a_changed_real_freeze(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    p['action_packet']['policy'].update(version='METHOD_EXECUTION_500_V1', quantity='500')
    declaration = {'namespace': 'METHOD_ENGINEERING', 'protocol_id': 'method-execution-500-protocol-v1',
        'scope': p['scope'], 'policy': p['action_packet']['policy'], 'model_fingerprint': p['deployment_fingerprints']['model'],
        'calibrator_fingerprint': p['deployment_fingerprints']['calibrator']}
    p.update(protocol_id=declaration['protocol_id'], complete_protocol_fingerprint=fingerprint(declaration), method_policy_declaration=declaration,
        execution={'version': 'METHOD_EXECUTION_500_V1', 'policy_fingerprint': fingerprint(declaration['policy'])},
        material_id='method-execution-500-material', review_run_id='method-execution-500-review', material_fingerprint=fingerprint(declaration))
    p['review'].update(material_id=p['material_id'], material_fingerprint=p['material_fingerprint'])
    p['action_packet']['complete_protocol_fingerprint'] = p['complete_protocol_fingerprint']
    for row in p['action_packet']['opportunities']:
        row.update(quantity='500', price_lower_yuan='9.00', price_upper_yuan='10.00')
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        ready(client)
        for instrument in p['scope']['instruments']:
            listing = client.get('/api/market/list').json()
            assert client.post('/api/market/watch', json={'instrument': instrument, 'operation': 'ADD', 'expected_list_version': listing['version']}).status_code == 200
        assert client.post('/api/funding/confirm', json=funding(1, single_exposure='40000.00')).status_code == 200
        proposal = client.get('/api/capabilities/proposal', params={'material_id': p['material_id'], 'review_run_id': p['review_run_id']}).json()
        grant = client.post('/api/capabilities/grants', json={**proposal, 'allowed_actions': ['BUY'], 'idempotency_key': 'method-500-grant', 'basis': 'explicit METHOD 500-share execution fixture'})
        assert grant.status_code == 201, grant.text
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        assert len(evaluation['decisions']) == 1, evaluation
        assert evaluation['namespace'] == 'METHOD_ENGINEERING'
        assert evaluation['system_usable'] is False
        assert evaluation['decisions'][0]['quantity'] == '500'
        intent = client.post('/api/intents/prepare', json={**intent_command(evaluation), 'price_yuan': '10.00'}).json()
        actual = fill(evaluation['account_version'], 'at05-300')
        actual['payload'].update(effective_at=p['required_as_of'], broker_available_after='86995.10')
        draft = client.post('/api/account/drafts', json=actual).json()
        result = client.post('/api/account/confirm', json={'draft_id': draft['draft_id'], 'idempotency_key': 'at05',
            'fill_allocations': [{'intent_id': intent['intent_id'], 'fill_record_id': 'at05-300', 'allocated_quantity': '300', 'association_status': 'USER_CONFIRMED'}]})
        assert result.status_code == 200, result.text
        assert client.get('/api/account').json()['positions'][0]['quantity'] == '300'
        pending = client.get('/api/intents').json()['intents'][0]
        assert pending['remaining_quantity'] == '200'
        assert pending['provisional_reservation_yuan'] == '2002.00'
        assert pending['remaining_action_state'] == 'REEVALUATION_REQUIRED'
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert grant.json()['protocol_id'] == declaration['protocol_id']
        assert grant.json()['complete_protocol_fingerprint'] == fingerprint(declaration)
        assert grant.json()['execution']['policy_fingerprint'] == fingerprint(declaration['policy'])
        if output := os.environ.get('ROLL_T26_EVIDENCE_DIR'):
            Path(output).mkdir(parents=True, exist_ok=True)
            (Path(output) / 'method-500-policy-bindings.json').write_text(json.dumps({'declaration': declaration,
                'method_envelope_sha256': json.loads(file.read_text(encoding='utf-8'))['sha256'],
                'grant': grant.json(), 'host_proofs': client.get('/api/capabilities/proofs').json(), 'evaluation': evaluation,
                'intent': intent, 'actual_receipt': result.json(), 'remaining_intent': pending}, indent=2) + '\n', encoding='utf-8')


def test_method500_packet_cannot_override_the_generic_method200_qualification(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    p['action_packet']['policy'].update(version='METHOD_EXECUTION_500_V1', quantity='500')
    for row in p['action_packet']['opportunities']: row.update(price_lower_yuan='9.00', price_upper_yuan='10.00')
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        response = client.post('/api/actions/evaluate', json={})
        assert response.status_code == 409
        assert response.json()['detail'] == 'METHOD_POLICY_BINDING_MISMATCH'


def test_expiry_never_releases_external_unknown_or_turns_it_into_unexecuted(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        command = intent_command(evaluation)
        intent = client.post('/api/intents/prepare', json=command).json()
        client.post('/api/intents/' + intent['intent_id'] + '/declare', json={'state': 'OPERATION_PENDING', 'idempotency_key': 'pending'})
        monkeypatch.setattr('roll.decisions.actions.now', lambda: (datetime.fromisoformat(p['expires_at']) + timedelta(seconds=1)).isoformat())
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert client.post('/api/intents/prepare', json=command).json() == intent
        assert client.post('/api/intents/prepare', json={**command, 'idempotency_key': 'new-prepare'}).status_code == 409
        value = client.get('/api/intents').json()
        assert value['pending_attribution'] is True
        assert value['unreflected_reservation_yuan'] == '30005.00'
        assert value['intents'][0]['time_chain']['occurred_at'] is None
        assert value['intents'][0]['status'] == 'OPERATION_PENDING'


def test_run_audit_consumes_real_intent_count_and_invalid_allocation_rolls_back_all_account_changes(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    clock = lambda: datetime.fromisoformat('2026-10-07T10:00:00+08:00')
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file, review_clock=clock)) as client:
        prepare(client, p)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        command = intent_command(evaluation)
        intent = client.post('/api/intents/prepare', json=command).json()
        assert client.post('/api/intents/prepare', json=command).json() == intent
        task = wait_result(client, client.post('/api/reviews/tasks', json={'mode': 'ON_DEMAND'}).json()['task_id'])
        metrics = client.get('/api/reviews/audits/' + task['audit_id']).json()['metrics']
        assert metrics['unfinished_execution_intents'] == {'status': 'CHECKED', 'value': 1}
        assert metrics['partially_synced_intents'] == {'status': 'CHECKED', 'value': 0}
        actual = fill(evaluation['account_version'], 'bad-allocation')
        actual['payload'].update(quantity='100', price='140.00', effective_at=p['required_as_of'])
        draft = client.post('/api/account/drafts', json=actual).json()
        before = client.get('/api/account').json()
        response = client.post('/api/account/confirm', json={'draft_id': draft['draft_id'], 'idempotency_key': 'bad', 'fill_allocations': [
            {'intent_id': intent['intent_id'], 'fill_record_id': 'bad-allocation', 'allocated_quantity': '200', 'association_status': 'USER_CONFIRMED'}]})
        assert response.status_code == 422
        assert client.get('/api/account').json() == before
        assert client.get('/api/intents/allocations').json() == []
        assert client.get('/api/intents').json()['intents'][0]['synced_quantity'] == '0'
        assert not any(e['event_type'] == 'ACTION_INVALIDATED' for e in client.get('/api/actions/events').json())


@pytest.mark.parametrize('available', ['1000.00', None])
def test_independent_reduction_prepare_does_not_require_new_risk_reserve_cash_or_purchase_permission(tmp_path, monkeypatch, available):
    monkeypatch.setenv('ROLL_ENV', 'test')
    import capability_method_app
    import roll.decisions.actions
    import roll.decisions.capabilities
    monkeypatch.setattr(capability_method_app, 'ANCHOR', capability_method_app.ANCHOR)
    monkeypatch.setattr(roll.decisions.actions, 'now', roll.decisions.actions.now)
    monkeypatch.setattr(roll.decisions.capabilities, 'now', roll.decisions.capabilities.now)
    from actions_method_app import risk_package
    p = risk_package()
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        value = baseline()
        value['payload'].update(broker_available=available, broker_frozen='99000.10' if available else None,
            positions=[{'instrument': 'SSE:600000', 'quantity': '300', 'sellable_quantity': '300', 'reference_cost': '100'}])
        value['payload']['permission_profile'][0]['status'] = 'NOT_OPEN'
        assert submit(client, value, 'baseline').status_code == 200
        assert submit(client, {'kind': 'ACCOUNT_DECLARATION', 'expected_account_version': 1, 'payload': {
            'effective_at': p['required_as_of'], 'source': 'METHOD', 'record_id': 'declaration',
            'scope': ['TRADES', 'ORDERS', 'CASH', 'EQUITY'], 'changes': 'NONE', 'basis': 'METHOD'}}, 'declaration').status_code == 200
        assert client.post('/api/funding/confirm', json=funding()).status_code == 200
        command = {**method_command(), 'allowed_actions': ['REDUCE', 'EXIT'], 'deployment_fingerprints': p['deployment_fingerprints']}
        granted = client.post('/api/capabilities/grants', json=command)
        assert granted.status_code == 201, granted.text
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        assert [(d['action'], d['quantity']) for d in evaluation['decisions']] == [('REDUCE', '100')], evaluation
        response = client.post('/api/intents/prepare', json={**intent_command(evaluation), 'price_yuan': '100.00'})
        assert response.status_code == 201, response.text
        assert response.json()['provisional_reservation_yuan'] == '0.00'
        assert client.get('/api/account').json()['positions'][0]['quantity'] == '300'


def test_unknown_unlinked_excess_facts_and_multito_multi_allocations_do_not_merge_actual_fills(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        one = client.post('/api/intents/prepare', json=intent_command(evaluation)).json()
        client.post('/api/intents/' + one['intent_id'] + '/declare', json={'state': 'NOT_EXECUTED', 'reason': '当时未操作', 'idempotency_key': 'not-done'})
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        two = client.post('/api/intents/prepare', json={**intent_command(evaluation), 'idempotency_key': 'prepare-2'}).json()
        for idx in range(2):
            actual = fill(2 + idx, 'same-price-' + str(idx), fee_status='PROVISIONAL' if idx == 0 else 'KNOWN')
            actual['payload'].update(quantity='300', price='10.00', effective_at=p['required_as_of'], fill_id='different-fill-' + str(idx))
            draft = client.post('/api/account/drafts', json=actual).json()
            allocations = [{'intent_id': one['intent_id'], 'fill_record_id': actual['payload']['record_id'], 'allocated_quantity': '100', 'association_status': 'USER_CONFIRMED'},
                           {'intent_id': two['intent_id'], 'fill_record_id': actual['payload']['record_id'], 'allocated_quantity': '200', 'association_status': 'USER_CONFIRMED'}]
            response = client.post('/api/account/confirm', json={'draft_id': draft['draft_id'], 'idempotency_key': 'actual-' + str(idx), 'fill_allocations': allocations})
            assert response.status_code == 200, response.text
        assert len(client.get('/api/account').json()['fills']) == 2
        assert client.get('/api/account').json()['positions'][0]['quantity'] == '600'
        records = client.get('/api/intents/allocations').json()
        assert len(records) == 4
        assert len({v['fill_event_id'] for v in records}) == 2
        assert len({v['decision_id'] for v in records}) == 2
        assert records[0]['fee']['status'] == 'PROVISIONAL'
        values = client.get('/api/intents').json()['intents']
        assert values[1]['excess_quantity'] == '200'
        actual = fill(4, 'unlinked')
        actual['payload'].update(effective_at=p['required_as_of'], quantity='100', behavior_context='NO_RECOMMENDATION')
        assert submit(client, actual, 'unlinked').status_code == 200
        assert len(client.get('/api/intents/allocations').json()) == 4
        assert client.get('/api/account').json()['fills'][-1]['action_association']['status'] == 'UNKNOWN'


def test_prepare_records_reservation_without_changing_actual_account_and_retry_is_identical(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        before = client.get('/api/account').json()
        response = client.post('/api/intents/prepare', json=intent_command(evaluation))
        assert response.status_code == 201, response.text
        value = response.json()
        assert value['status'] == 'PREPARED'
        assert value['remaining_quantity'] == '200'
        assert value['provisional_reservation_yuan'] == '30005.00'
        assert value['time_chain']['delivered_at'] is None
        assert client.get('/api/account').json() == before
        assert client.post('/api/intents/prepare', json=intent_command(evaluation)).json() == value
        assert client.get('/api/intents').json()['intents'] == [value]


def test_partial_fill_is_atomic_with_allocations_remaining_external_order_and_action_invalidation(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, p)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        command = intent_command(evaluation)
        intent = client.post('/api/intents/prepare', json=command).json()
        declared = client.post('/api/intents/' + intent['intent_id'] + '/declare', json={
            'state': 'OPERATION_PENDING', 'external_order_id': 'broker-order-1', 'broker_reflection': 'CONFIRMED_REFLECTED',
            'occurred_at': p['required_as_of'], 'reason': None, 'idempotency_key': 'operated-1'})
        assert declared.status_code == 200, declared.text
        assert client.get('/api/intents').json()['unreflected_reservation_yuan'] == '0.00'
        actual = fill(evaluation['account_version'], 'partial-1')
        actual['payload'].update(quantity='100', price='140.00', effective_at=p['required_as_of'], order_id='broker-order-1', broker_available_after='76000.10')
        draft = client.post('/api/account/drafts', json=actual).json()
        confirmation = {'draft_id': draft['draft_id'], 'idempotency_key': 'partial-confirm', 'fill_allocations': [
            {'intent_id': intent['intent_id'], 'fill_record_id': 'partial-1', 'allocated_quantity': '100', 'association_status': 'USER_CONFIRMED'}]}
        receipt = client.post('/api/account/confirm', json=confirmation)
        assert receipt.status_code == 200, receipt.text
        account = client.get('/api/account').json()
        assert account['cash_balance'] == '85995.10'
        assert account['positions'][0]['quantity'] == '100'
        pending = client.get('/api/intents').json()['intents'][0]
        assert pending['status'] == 'OPERATION_PENDING'
        assert pending['synced_quantity'] == '100'
        assert pending['remaining_quantity'] == '100'
        assert pending['provisional_reservation_yuan'] == '15002.50'
        assert pending['time_chain']['read_at'] is None
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert any(e['event_type'] == 'ACTION_INVALIDATED' for e in client.get('/api/actions/events').json())
        assert len(client.get('/api/intents/allocations').json()) == 1
        allocated = client.get('/api/intents/allocations').json()[0]
        assert allocated['reported_at'] == draft['created_at']
        assert allocated['reported_source'] == 'USER_ACCOUNT_DRAFT'
        assert allocated['known_at'] == receipt.json()['confirmed_at']
        assert allocated['known_source'] == 'HOST_ACCOUNT_CONFIRM'
        assert allocated['occurred_at'] == p['required_as_of']
        assert allocated['occurred_source'] == actual['payload']['source']
        assert allocated['decision_time_chain']['read_at'] is None
        assert client.post('/api/account/confirm', json=confirmation).json() == receipt.json()
        assert len(client.get('/api/intents/allocations').json()) == 1
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        assert client.get('/api/intents').json()['intents'][0] == pending
        assert client.get('/api/account').json()['version'] == account['version']
