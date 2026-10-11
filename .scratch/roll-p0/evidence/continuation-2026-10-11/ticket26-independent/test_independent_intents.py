import json
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.decisions.actions import fingerprint
from roll.decisions.capabilities import source_inventory
from capability_method_app import save_package
from test_actions import action_package, prepare
from test_intents import intent_command, test_exact_500_proposal_300_actual_is_a_declared_method_policy_not_a_changed_real_freeze as method500_scenario
from test_fills import fill


def test_complete_method500_binding_independent_archive_and_production_refusal(tmp_path, monkeypatch):
    evidence = tmp_path / 'receipt'
    monkeypatch.setenv('ROLL_T26_EVIDENCE_DIR', str(evidence))
    method500_scenario(tmp_path, monkeypatch)
    value = json.loads((evidence / 'method-500-policy-bindings.json').read_text(encoding='utf-8'))
    declaration, grant = value['declaration'], value['grant']
    assert fingerprint(declaration) == grant['complete_protocol_fingerprint'] == grant['material_fingerprint'] == '52f7dfd085a49cc9a2e0884d12296d26f55064814c90e63165d42387ce2dc902'
    assert fingerprint(declaration['policy']) == grant['execution']['policy_fingerprint'] == 'eaa4a234588994a79b8ce570fad4fad376c5736025064952473cdb7ca8085e4f'
    assert grant['dependency_fingerprints'] == source_inventory()
    assert grant['system_usable'] is False and grant['protocol_id'] == 'method-execution-500-protocol-v1'
    assert value['remaining_intent']['remaining_quantity'] == '200'
    assert value['remaining_intent']['provisional_reservation_yuan'] == '2002.00'
    file = tmp_path / 'qualification.json'
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file, runtime_role='API')) as client:
        archived = client.get('/api/data/archives/' + value['evaluation']['input_archive']['sha256'])
        assert archived.status_code == 200, archived.text
        packet = json.loads(archived.content)['packet']
        assert packet['method_policy_binding']['declaration_fingerprint'] == fingerprint(declaration)
        assert packet['method_policy_binding']['policy_fingerprint'] == grant['execution']['policy_fingerprint']
        assert client.get('/api/intents').json()['intents'][0] == value['remaining_intent']
        assert client.post('/api/actions/evaluations/' + value['evaluation']['evaluation_id'] + '/replay').json()['matches_original'] is True
    monkeypatch.setenv('ROLL_ENV', 'local')
    with TestClient(create_app(tmp_path / 'data', runtime_role='API')) as client:
        assert client.post('/api/formal/evaluate', json={}).status_code == 403
        assert client.get('/api/actions/current').json()['decisions'] == []


def test_generic200_cannot_silently_admit500(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    p['action_packet']['policy'].update(version='METHOD_EXECUTION_500_V1', quantity='500')
    for row in p['action_packet']['opportunities']:
        row.update(price_lower_yuan='9.00', price_upper_yuan='10.00')
    file = save_package(tmp_path / 'qualification.json', p)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file, runtime_role='API')) as client:
        prepare(client, p)
        response = client.post('/api/actions/evaluate', json={})
        assert response.status_code == 409 and response.json()['detail'] == 'METHOD_POLICY_BINDING_MISMATCH'
        assert client.get('/api/intents').json()['intents'] == []


def test_partial_confirm_uses_same_writer_latest_facts_and_preserves_four_times(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    p = action_package()
    file = save_package(tmp_path / 'qualification.json', p)
    app = create_app(tmp_path / 'data', capability_method_file=file, runtime_role='API')
    with TestClient(app) as client:
        prepare(client, p)
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        command = intent_command(evaluation)
        before = client.get('/api/account').json()
        intent_response = client.post('/api/intents/prepare', json=command)
        assert intent_response.status_code == 201, intent_response.text
        intent = intent_response.json()
        assert client.get('/api/account').json() == before
        assert client.post('/api/intents/prepare', json=command).json() == intent
        declaration = client.post('/api/intents/' + intent['intent_id'] + '/declare', json={
            'state': 'OPERATION_PENDING', 'external_order_id': 'own-order-1', 'broker_reflection': 'CONFIRMED_REFLECTED',
            'occurred_at': p['required_as_of'], 'idempotency_key': 'own-pending'})
        assert declaration.status_code == 200
        assert client.get('/api/intents').json()['unreflected_reservation_yuan'] == '0.00'
        actual = fill(evaluation['account_version'], 'own-partial')
        actual['payload'].update(quantity='100', price='140.00', effective_at=p['required_as_of'], order_id='own-order-1', broker_available_after='76000.10')
        draft = client.post('/api/account/drafts', json=actual).json()
        with_draft = client.get('/api/account').json()
        assert with_draft['state'] == 'UPDATE_PENDING'
        for key in ['version', 'cash_balance', 'positions']:
            assert with_draft[key] == before[key]
        allocation = {'intent_id': intent['intent_id'], 'fill_record_id': 'own-partial', 'allocated_quantity': '100', 'association_status': 'USER_CONFIRMED'}
        rejected = client.post('/api/account/confirm', json={'draft_id': draft['draft_id'], 'idempotency_key': 'own-excess', 'fill_allocations': [{**allocation, 'allocated_quantity': '101'}]})
        assert rejected.status_code == 422
        assert client.get('/api/account').json() == with_draft
        assert client.get('/api/intents/allocations').json() == []
        assert not any(event['event_type'] == 'ACTION_INVALIDATED' for event in client.get('/api/actions/events').json())
        observed = []
        original = app.state.intents.account_confirmed
        def check_writer(db, confirm_command, events, receipt):
            assert db.in_transaction
            assert app.state.ledger.account(db=db)['version'] == receipt['account_version'] == 3
            # A separate reader still sees version2 until the enclosing writer commits.
            with app.state.ledger.connection() as reader:
                assert app.state.ledger.account(db=reader)['version'] == 2
            current = app.state.actions.current
            def same_db(instrument=None, db=None):
                assert db is writer and db.in_transaction
                observed.append('same_uncommitted_writer')
                return current(instrument, db)
            writer = db
            with monkeypatch.context() as scoped:
                scoped.setattr(app.state.actions, 'current', same_db)
                original(db, confirm_command, events, receipt)
                assert db.in_transaction
        monkeypatch.setattr(app.state.intents, 'account_confirmed', check_writer)
        confirm = {'draft_id': draft['draft_id'], 'idempotency_key': 'own-confirm', 'fill_allocations': [allocation]}
        response = client.post('/api/account/confirm', json=confirm)
        assert response.status_code == 200, response.text
        assert observed == ['same_uncommitted_writer']
        receipt = response.json()
        account = client.get('/api/account').json()
        assert account['version'] == 3 and account['cash_balance'] == '85995.10'
        assert account['positions'][0]['quantity'] == '100'
        pending = client.get('/api/intents').json()['intents'][0]
        assert (pending['synced_quantity'], pending['remaining_quantity'], pending['provisional_reservation_yuan']) == ('100', '100', '15002.50')
        assert pending['effective_broker_reflection'] == 'UNKNOWN'
        assert client.get('/api/intents').json()['unreflected_reservation_yuan'] == '15002.50'
        assert pending['remaining_action_state'] == 'REEVALUATION_REQUIRED'
        allocated = client.get('/api/intents/allocations').json()[0]
        assert allocated['occurred_at'] == p['required_as_of'] and allocated['occurred_source'] == actual['payload']['source']
        assert allocated['reported_at'] == draft['created_at'] and allocated['reported_source'] == 'USER_ACCOUNT_DRAFT'
        assert allocated['known_at'] == receipt['confirmed_at'] and allocated['known_source'] == 'HOST_ACCOUNT_CONFIRM'
        assert allocated['decision_time_chain']['decision_issued_at'] == evaluation['registered_at']
        assert allocated['decision_time_chain']['prepared_at'] == intent['time_chain']['prepared_at']
        assert allocated['decision_time_chain']['sent_at'] is None and allocated['decision_time_chain']['read_at'] is None
        assert any(event['event_type'] == 'ACTION_INVALIDATED' for event in client.get('/api/actions/events').json())
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert client.post('/api/intents/prepare', json=command).status_code == 409
        assert client.post('/api/account/confirm', json=confirm).json() == receipt
        assert len(client.get('/api/intents/allocations').json()) == 1
