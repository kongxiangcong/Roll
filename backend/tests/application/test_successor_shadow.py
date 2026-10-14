from fastapi.testclient import TestClient
from roll.app import create_app
from test_policy_successors import predecessor, register, migration, position
import json
import sqlite3


def freeze_successor(client, proposal, positions=None, **changes):
    return client.post('/api/research/policy-successors/'+proposal['proposal_id']+'/freezes', json={
        'idempotency_key': 'freeze-v2', 'policy_fingerprint': proposal['policy_fingerprint'],
        'starting_session': 0, 'cash_yuan': '10000.00', 'positions': positions or [],
        'basis': 'Isolated METHOD continuous successor; not formal qualification', **changes})


def frame(session, probability='0.80', **changes):
    return {'idempotency_key': 'session-'+str(session), 'expected_revision': session-1,
        'session': session, 'calendar_previous_session': session-1,
        'source_snapshot_id': 'method-session-'+str(session), 'evidence_kind': 'METHOD_CASE',
        'bars': [{'instrument': 'SSE:600519', 'open_yuan': '10.00', 'high_yuan': '10.50',
                  'low_yuan': '9.50', 'close_yuan': '10.00', 'volume_shares': 10000,
                  'reference_close_yuan': '10.00', 'completion': 'COMPLETE',
                  'market_state': 'NORMAL', 'company_actions': 'NONE'}],
        'signals': [{'instrument': 'SSE:600519', 'forecast_id': 'signal-'+str(session),
                     'probability': probability}], **changes}


def test_separate_successor_freeze_binds_original_model_and_sequential_shadow_never_actual(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        frozen = predecessor(client, tmp_path)
        proposal = register(client, frozen).json()
        receipt = migration(client, proposal, 'SSE:600519', 100, 20).json()
        baseline = position('SSE:600519', 100, receipt)
        response = freeze_successor(client, proposal, [baseline])
        assert response.status_code == 201, response.text
        successor = response.json()
        assert successor['model_freeze_manifest'] == frozen['model_freeze_manifest']
        assert successor['model_artifact_fingerprints'] == frozen['model_freeze']['artifact_fingerprints']
        assert successor['validation_status'] == 'UNVALIDATED'
        assert successor['validation_verdict'] == 'INCONCLUSIVE'
        assert successor['system_usable'] is False and successor['capability'] == 'NOT_GRANTED'
        assert freeze_successor(client, proposal, [baseline]).json() == successor
        path = '/api/research/policy-successor-freezes/'+successor['successor_freeze_id']
        one = client.post(path+'/shadow/advance', json=frame(1))
        assert one.status_code == 201, one.text
        assert one.json()['evaluations'][-1]['actions'][0]['action'] == 'REFUSE'  # migration effective at session2
        two = client.post(path+'/shadow/advance', json=frame(2))
        assert two.status_code == 201, two.text
        assert two.json()['evaluations'][-1]['actions'][0]['action'] == 'ADD'
        three = client.post(path+'/shadow/advance', json=frame(3))
        assert three.status_code == 201, three.text
        state = three.json()
        assert sum(p['quantity'] for p in state['positions']) == 200
        assert [p['exit_session'] for p in state['positions']] == [20, 23]
        assert state['cash_yuan'] == '8993.99'
        assert state['evaluations'][-1]['actions'][0]['action'] == 'HOLD'
        four = client.post(path+'/shadow/advance', json=frame(4, '0.40')).json()
        assert four['evaluations'][-1]['actions'][0]['reasons'] == ['UNVALIDATED_LOW_SUPPORT_EXIT_CLAUSE', 'OPPOSITE_ACTION_COOLDOWN']
        five = client.post(path+'/shadow/advance', json=frame(5, '0.40')).json()
        assert five['evaluations'][-1]['actions'][0]['action'] == 'EXIT'
        final = client.post(path+'/shadow/advance', json=frame(6, '0.40')).json()
        assert final['positions'] == [] and final['cash_yuan'] == '10987.97'
        assert final['evaluations'][-1]['actions'][0]['action'] == 'WAIT'
        assert client.post(path+'/shadow/replay').json()['matches_original'] is True
        assert client.get('/api/account').json()['version'] == 0
        assert client.get('/api/research/complete-freezes/'+frozen['freeze_id']).json() == frozen
        assert client.post(path+'/shadow/advance', json=frame(6, '0.40')).json() == final
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(path+'/shadow').json() == final
        assert client.post(path+'/shadow/replay').json()['matches_original'] is True


def test_next_open_rechecks_exposure_instead_of_reusing_previous_close_budget(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        frozen = predecessor(client, tmp_path)
        proposal = register(client, frozen).json()
        receipt = migration(client, proposal, 'SSE:600519', 100, 20).json()
        successor = freeze_successor(client, proposal, [position('SSE:600519', 100, receipt)], cash_yuan='3220.00').json()
        path = '/api/research/policy-successor-freezes/'+successor['successor_freeze_id']
        assert client.post(path+'/shadow/advance', json=frame(1)).status_code == 201
        two = client.post(path+'/shadow/advance', json=frame(2)).json()
        assert two['evaluations'][-1]['actions'][0]['action'] == 'ADD'
        next_frame = frame(3)
        next_frame['bars'][0].update(open_yuan='10.99', high_yuan='11.00', low_yuan='10.50', close_yuan='10.99')
        response = client.post(path+'/shadow/advance', json=next_frame)
        assert response.status_code == 201, response.text
        state = response.json()
        assert state['cash_yuan'] == '3220.00'
        assert sum(p['quantity'] for p in state['positions']) == 100
        assert state['events'][0]['kind'] == 'NO_FILL'
        assert state['events'][0]['reason'] == 'OPEN_EXPOSURE_LIMIT_RECHECK_FAILED'
        assert client.post(path+'/shadow/replay').json()['matches_original'] is True
        assert client.get('/api/account').json()['version'] == 0
        assert client.get('/api/research/complete-freezes/'+frozen['freeze_id']).json() == frozen


def test_original_migrated_horizon_closes_only_original_lot_after_same_session_add(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        frozen = predecessor(client, tmp_path)
        proposal = register(client, frozen).json()
        receipt = migration(client, proposal, 'SSE:600519', 100, 3).json()
        successor = freeze_successor(client, proposal, [position('SSE:600519', 100, receipt, 3)]).json()
        path = '/api/research/policy-successor-freezes/'+successor['successor_freeze_id']
        assert client.post(path+'/shadow/advance', json=frame(1)).status_code == 201
        assert client.post(path+'/shadow/advance', json=frame(2)).status_code == 201
        response = client.post(path+'/shadow/advance', json=frame(3))
        assert response.status_code == 201, response.text
        state = response.json()
        assert [(event['kind'], event['point'], event['quantity']) for event in state['events']] == [
            ('BUY_FILL', 'open_yuan', 100), ('SELL_FILL', 'close_yuan', 100)]
        assert state['cash_yuan'] == '9988.48'
        assert [(p['quantity'], p['exit_session'], p['baseline']) for p in state['positions']] == [(100, 23, False)]
        assert state['evaluations'][-1]['actions'][0]['reasons'] == ['OPPOSITE_ACTION_COOLDOWN']
        assert client.get(path).json()['migrations'][receipt['migration_id']]['original_exit_session'] == 3
        assert client.post(path+'/shadow/replay').json()['matches_original'] is True


def test_current_and_replay_refuse_corrupted_owned_method_frame_after_restart(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        frozen = predecessor(client, tmp_path)
        proposal = register(client, frozen).json()
        successor = freeze_successor(client, proposal).json()
        path = '/api/research/policy-successor-freezes/'+successor['successor_freeze_id']
        assert client.post(path+'/shadow/advance', json=frame(1)).status_code == 201
        assert client.post(path+'/shadow/advance', json=frame(2)).status_code == 201
    # Deliberate storage fault at the approved owned synthetic file boundary.
    with sqlite3.connect(tmp_path/'roll.sqlite3') as db:
        raw = db.execute('SELECT value FROM research_successor_frames WHERE revision=1').fetchone()[0]
        corrupt = json.loads(raw)
        corrupt['command']['signals'][0]['probability'] = '0.40'
        db.execute('UPDATE research_successor_frames SET value=? WHERE revision=1', (json.dumps(corrupt),))
    with TestClient(create_app(tmp_path)) as client:
        response = client.get(path+'/shadow')
        assert response.status_code == 409, response.text
        assert response.json()['detail'] == 'SUCCESSOR_FRAME_INPUT_BINDING_MISMATCH'
        assert client.post(path+'/shadow/replay').status_code == 409


def test_unknown_state_and_calendar_gaps_never_become_hold_or_distant_open_fills(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        frozen = predecessor(client, tmp_path)
        proposal = register(client, frozen).json()
        receipt = migration(client, proposal, 'SSE:600519', 200, 20).json()
        successor = freeze_successor(client, proposal, [position('SSE:600519', 200, receipt)]).json()
        path = '/api/research/policy-successor-freezes/'+successor['successor_freeze_id']
        unknown = frame(1); unknown['bars'][0]['market_state'] = 'UNKNOWN'
        response = client.post(path+'/shadow/advance', json=unknown)
        assert response.status_code == 201, response.text
        assert response.json()['evaluations'][-1]['actions'][0]['action'] == 'REFUSE'
        assert 'CURRENT_EXECUTION_SUPPORT_UNKNOWN' in response.json()['evaluations'][-1]['actions'][0]['reasons']
        gap_proposal = register(client, frozen, version='v2-gap-case', idempotency_key='v2-gap').json()
        gap_freeze = freeze_successor(client, gap_proposal).json()
        gap_path = '/api/research/policy-successor-freezes/'+gap_freeze['successor_freeze_id']
        first = client.post(gap_path+'/shadow/advance', json=frame(1)).json()
        assert first['pending'][0]['expected_session'] == 2
        distant = client.post(gap_path+'/shadow/advance', json=frame(3, '0.40', expected_revision=1)).json()
        assert distant['positions'] == [] and distant['cash_yuan'] == '10000.00'
        assert distant['events'][0]['reason'] == 'MISSED_NEXT_SESSION_NO_DISTANT_BAR_SUBSTITUTION'
        assert distant['evaluations'][-1]['actions'][0]['action'] == 'WAIT'
        assert client.post(gap_path+'/shadow/replay').json()['matches_original'] is True
        assert client.post(gap_path+'/shadow/advance', json=frame(4, evidence_kind='REAL_ACQUISITION')).status_code == 422
