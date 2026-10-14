from fastapi.testclient import TestClient
from roll.app import create_app
from test_shadow import setup, freeze


def migration(client, proposal, instrument, quantity, exit_session):
    return client.post('/api/research/policy-successors/'+proposal['proposal_id']+'/migrations', json={
        'idempotency_key': 'migrate-'+instrument, 'position_id': 'pos-'+instrument,
        'instrument': instrument, 'quantity': quantity, 'original_exit_session': exit_session,
        'effective_session': 2, 'basis': 'Explicit prospective research position migration'})


def evaluation(**changes):
    return {'idempotency_key': 'evaluate-1', 'completed_session': 3,
        'cash_yuan': '10000.00', 'reserved_yuan': '0.00', 'nav_yuan': '20000.00',
        'current_exposure_yuan': '4000.00', 'positions': [], 'opportunities': [],
        'history': [], **changes}


def opportunity(symbol, probability):
    return {'instrument': symbol, 'forecast_id': 'forecast-'+symbol,
        'probability': probability, 'upper_price_yuan': '10.00', 'fees_yuan': '5.00',
        'buy_minimum': 100, 'buy_increment': 100}


def position(symbol, quantity, receipt, exit_session=20):
    return {'position_id': 'pos-'+symbol, 'instrument': symbol, 'quantity': quantity,
        'sellable_quantity': quantity, 'original_exit_session': exit_session,
        'migration_id': receipt['migration_id']}


def predecessor(client, directory):
    _, protocol, model, _ = setup(client, directory)
    response = freeze(client, protocol, model)
    assert response.status_code == 201, response.text
    return response.json()


def register(client, frozen, **changes):
    return client.post('/api/research/policy-successors', json={
        'predecessor_freeze_id': frozen['freeze_id'],
        'predecessor_policy_fingerprint': frozen['fingerprints']['policy'],
        'version': '20-policy-v2-proposal', 'idempotency_key': 'register-v2',
        'basis': 'Research-only deterministic successor engineering', **changes})


def test_successor_registration_is_immutable_predecessor_bound_and_never_formal(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        frozen = predecessor(client, tmp_path)
        response = register(client, frozen)
        assert response.status_code == 201, response.text
        proposal = response.json()
        assert proposal['namespace'] == 'RESEARCH_POLICY_PROPOSAL'
        assert proposal['system_usable'] is False and proposal['capability'] == 'NOT_GRANTED'
        assert proposal['validation_status'] == 'UNVALIDATED'
        assert proposal['policy']['entry_threshold'] == '0.60'
        assert proposal['policy']['target_quantity'] == '200'
        assert register(client, frozen).json() == proposal
        assert register(client, frozen, basis='changed').status_code == 409
        assert register(client, frozen, idempotency_key='wrong', predecessor_policy_fingerprint='0'*64).status_code == 409
        assert client.get('/api/research/complete-freezes/'+frozen['freeze_id']).json() == frozen
        path = '/api/research/policy-successors/'+proposal['proposal_id']
        assert client.get(path).json() == proposal
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(path).json() == proposal


def test_research_evaluation_covers_hold_add_wait_exit_and_preserves_migration_horizon(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        frozen = predecessor(client, tmp_path)
        proposal = register(client, frozen).json()
        a = migration(client, proposal, 'A', 100, 20)
        assert a.status_code == 201, a.text
        b = migration(client, proposal, 'B', 200, 20).json()
        c = migration(client, proposal, 'C', 200, 3).json()
        path = '/api/research/policy-successors/'+proposal['proposal_id']
        response = client.post(path+'/evaluations', json=evaluation(
            positions=[position('A', 100, a.json()), position('B', 200, b), position('C', 200, c, 3)],
            opportunities=[opportunity('A', '0.80'), opportunity('B', '0.80'),
                           opportunity('C', '0.90'), opportunity('D', '0.40')]))
        assert response.status_code == 201, response.text
        result = response.json()
        actions = {row['instrument']: row for row in result['actions']}
        assert (actions['A']['action'], actions['A']['quantity']) == ('ADD', 100)
        assert (actions['B']['action'], actions['B']['quantity']) == ('HOLD', 0)
        assert (actions['C']['action'], actions['C']['quantity']) == ('EXIT', 200)
        assert actions['C']['reasons'] == ['ORIGINAL_HORIZON_REACHED']
        assert actions['D']['action'] == 'WAIT'
        assert result['available_cash_after_reservations_yuan'] == '8995.00'
        assert result['system_usable'] is False and result['capability'] == 'NOT_GRANTED'
        saved_path = path+'/evaluations/'+result['evaluation_id']
        assert client.post(saved_path+'/replay').json()['matches_original'] is True
        assert client.get('/api/research/complete-freezes/'+frozen['freeze_id']).json() == frozen
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(saved_path).json() == result
        assert client.post(saved_path+'/replay').json()['matches_original'] is True


def test_migration_cannot_rewrite_original_exit_or_apply_before_its_effective_session(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        frozen = predecessor(client, tmp_path)
        proposal = register(client, frozen).json()
        receipt = migration(client, proposal, 'A', 100, 20).json()
        path = '/api/research/policy-successors/'+proposal['proposal_id']
        altered = position('A', 100, receipt, 3)
        response = client.post(path+'/evaluations', json=evaluation(
            positions=[altered], opportunities=[opportunity('A', '0.80')]))
        assert response.status_code == 409, response.text
        assert response.json()['detail'] == 'POSITION_MIGRATION_FACTS_MISMATCH'
        response = client.post(path+'/evaluations', json=evaluation(completed_session=1,
            positions=[position('A', 100, receipt)], opportunities=[opportunity('A', '0.80')]))
        assert response.status_code == 409, response.text
        assert response.json()['detail'] == 'POSITION_MIGRATION_NOT_YET_EFFECTIVE'
        assert client.post(path+'/migrations', json={
            'idempotency_key': 'replace-position', 'position_id': 'pos-A', 'instrument': 'A',
            'quantity': 100, 'original_exit_session': 30, 'effective_session': 2,
            'basis': 'attempt to silently extend exit'}).status_code == 409
        assert client.get('/api/research/complete-freezes/'+frozen['freeze_id']).json() == frozen


def test_research_reversal_budget_unknown_support_and_conflicting_history_are_explicit(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        frozen = predecessor(client, tmp_path)
        proposal = register(client, frozen).json()
        path = '/api/research/policy-successors/'+proposal['proposal_id']
        response = client.post(path+'/evaluations', json=evaluation(
            history=[{'instrument': 'A', 'action': 'BUY', 'completed_session': 2},
                     {'instrument': 'A', 'action': 'EXIT', 'completed_session': 2}],
            opportunities=[opportunity('A', '0.80')]))
        assert response.status_code == 422, response.text
        assert response.json()['detail'] == 'AMBIGUOUS_ACTION_HISTORY'
        response = client.post(path+'/evaluations', json=evaluation(
            history=[{'instrument': 'A', 'action': 'EXIT', 'completed_session': 2}],
            opportunities=[opportunity('A', '0.90'), opportunity('B', '0.80'), opportunity('C', '0.80')]))
        assert response.status_code == 201, response.text
        result = response.json()
        assert [(r['instrument'], r['action']) for r in result['actions']] == [('A', 'REFUSE'), ('B', 'BUY'), ('C', 'REFUSE')]
        assert result['actions'][0]['reasons'] == ['OPPOSITE_ACTION_COOLDOWN']
        assert result['actions'][2]['reasons'] == ['ONE_NEW_ENTRY_LIMIT']
        assert result['available_cash_after_reservations_yuan'] == '7995.00'
        assert client.post(path+'/evaluations', json=evaluation(
            opportunities=[opportunity('A', '0.80')])).status_code == 409
        assert client.post(path+'/evaluations', json=evaluation(
            idempotency_key='after-cooldown', completed_session=4,
            history=[{'instrument': 'A', 'action': 'EXIT', 'completed_session': 2}],
            opportunities=[opportunity('A', '0.80')])).json()['actions'][0]['action'] == 'BUY'
        no_migration = position('D', 100, {'migration_id': None})
        unknown = position('E', 200, {'migration_id': None})
        low = position('F', 200, {'migration_id': None}); low['sellable_quantity'] = None
        response = client.post(path+'/evaluations', json=evaluation(idempotency_key='unknowns',
            positions=[no_migration, unknown, low],
            opportunities=[opportunity('D', '0.80'), opportunity('F', '0.40')]))
        rows = {r['instrument']: r for r in response.json()['actions']}
        assert rows['D']['reasons'] == ['POSITION_MIGRATION_REQUIRED']
        assert rows['E']['reasons'] == ['PREDICTION_SUPPORT_UNKNOWN_NO_DEFAULT_HOLD']
        assert rows['F']['action'] == 'REFUSE' and 'SELLABLE_QUANTITY_UNKNOWN_OR_INSUFFICIENT' in rows['F']['reasons']
        budget = client.post(path+'/evaluations', json=evaluation(idempotency_key='joint-budget',
            cash_yuan='1000.00', opportunities=[opportunity('G', '0.80')])).json()
        assert budget['actions'][0]['reasons'] == ['JOINT_CASH_BUDGET']
        assert budget['available_cash_after_reservations_yuan'] == '1000.00'
        assert client.post(path+'/evaluations', json=evaluation(idempotency_key='malicious', system_usable=True)).status_code == 422
