"""Lifecycle through HTTP and real persisted METHOD evidence, not actual qualification."""
import pytest
import json
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package, prepare
from test_intents import intent_command


@pytest.mark.parametrize('scope,observations,model,new_risk', [
    ('NEW_RISK', True, True, False),
    ('MODEL', True, False, False),
    ('ALL_MONITOR', False, False, False),
])
def test_user_pause_scope_survives_restart_and_closes_old_prepare_without_rewriting_history(tmp_path, monkeypatch, scope, observations, model, new_risk):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    file = save_package(tmp_path / 'qualification.json', package)
    directory = tmp_path / 'data'
    with TestClient(create_app(directory, capability_method_file=file)) as client:
        prepare(client, package)
        original_grants = client.get('/api/capabilities/grants').json()
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        assert len(evaluation['decisions']) == 1
        old_prepare = intent_command(evaluation)
        account = client.get('/api/account').json()
        command = {'scope': scope, 'state': 'SUSPENDED', 'reason_code': 'USER_PAUSE',
                   'reason': '用户主动暂停本范围', 'expected_version': 0, 'idempotency_key': 'pause'}
        response = client.post('/api/capabilities/lifecycle', json=command)
        assert response.status_code == 200, response.text
        receipt = response.json()
        assert receipt['version'] == 1 and receipt['effective_at']
        assert client.post('/api/capabilities/lifecycle', json=command).json() == receipt
        control = client.get('/api/capabilities/lifecycle').json()
        assert (control['observations_allowed'], control['model_judgments_allowed'], control['new_risk_allowed']) == (observations, model, new_risk)
        assert control['scopes'][scope]['reason_code'] == 'USER_PAUSE'
        assert client.post('/api/intents/prepare', json=old_prepare).status_code == 409
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert client.post('/api/actions/evaluate', json={}).json()['decisions'] == []
        assert client.get('/api/actions/evaluations/' + evaluation['evaluation_id']).json() == evaluation
        assert client.get('/api/capabilities/grants').json() == original_grants
        assert client.get('/api/account').json() == account
        draft = client.post('/api/account/drafts', json={'kind': 'CASH_IN', 'expected_account_version': account['version'],
            'payload': {'effective_at': package['required_as_of'], 'source': 'METHOD用户资金凭证', 'record_id': 'cash-after-pause', 'amount': '1.00', 'instrument': None,
                        'broker_available_after': None, 'basis': '事实同步不受暂停控制'}})
        assert draft.status_code == 201, draft.text
        confirmed = client.post('/api/account/confirm', json={'draft_id': draft.json()['draft_id'], 'idempotency_key': 'cash'})
        assert confirmed.status_code == 200, confirmed.text
        assert client.get('/api/account').json()['version'] == account['version'] + 1
    with TestClient(create_app(directory, capability_method_file=file)) as client:
        control = client.get('/api/capabilities/lifecycle').json()
        assert control['version'] == 1 and control['scopes'][scope]['state'] == 'SUSPENDED'
        assert client.post('/api/intents/prepare', json=old_prepare).status_code == 409
        assert client.get('/api/actions/evaluations/' + evaluation['evaluation_id']).json() == evaluation


@pytest.mark.parametrize('scope,expected', [('NEW_RISK', 202), ('MODEL', 202), ('ALL_MONITOR', 409)])
def test_scope_controls_actual_observation_admission_but_not_audits_and_backup(tmp_path, monkeypatch, scope, expected):
    monkeypatch.setenv('ROLL_ENV', 'test')
    with TestClient(create_app(tmp_path)) as client:
        response = client.post('/api/capabilities/lifecycle', json={'scope': scope, 'state': 'SUSPENDED',
            'reason_code': 'USER_PAUSE', 'reason': '仅暂停选定范围', 'expected_version': 0, 'idempotency_key': 'pause'})
        assert response.status_code == 200, response.text
        before = client.get('/api/reviews/history').json()
        observation = client.post('/api/reviews/tasks', json={'refresh_missing': False})
        assert observation.status_code == expected, observation.text
        if expected == 409:
            assert observation.json()['detail'] == 'ALL_MONITOR_SUSPENDED'
            assert client.get('/api/reviews/history').json() == before
        else:
            assert observation.json()['refresh_missing'] is False
        assert client.get('/api/reviews/audits').status_code == 200
        assert client.get('/api/runtime/backups/status').status_code == 200


def test_revoke_one_grant_preserves_external_pending_and_original_records_after_restart(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    file = save_package(tmp_path / 'qualification.json', package)
    directory = tmp_path / 'data'
    with TestClient(create_app(directory, capability_method_file=file)) as client:
        prepare(client, package)
        original = client.get('/api/capabilities/grants').json()[0]
        evaluation = client.post('/api/actions/evaluate', json={}).json()
        intent = client.post('/api/intents/prepare', json=intent_command(evaluation)).json()
        pending = client.post('/api/intents/' + intent['intent_id'] + '/declare', json={
            'state': 'OPERATION_PENDING', 'idempotency_key': 'pending', 'external_order_id': 'METHOD-external-1'}).json()
        response = client.post('/api/capabilities/lifecycle', json={'grant_id': original['grant_id'], 'scope': 'MODEL', 'state': 'REVOKED',
            'reason_code': 'USER_REVOKE', 'reason': '用户撤回本项资格', 'expected_version': 0, 'idempotency_key': 'revoke'})
        assert response.status_code == 200, response.text
        receipt = response.json()
        status = client.get('/api/capabilities/grants/' + original['grant_id'] + '/status').json()
        assert status['state'] == 'REVOKED' and status['allowed_actions'] == []
        assert client.post('/api/intents/prepare', json={**intent_command(evaluation), 'idempotency_key': 'old-retry'}).status_code == 409
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert client.get('/api/intents').json()['intents'] == [pending]
        assert client.get('/api/intents').json()['unreflected_reservation_yuan'] == '30005.00'
        assert client.get('/api/capabilities/grants').json() == [original]
        assert client.get('/api/actions/evaluations/' + evaluation['evaluation_id']).json() == evaluation
        resume = client.post('/api/capabilities/lifecycle', json={'grant_id': original['grant_id'], 'scope': 'MODEL', 'state': 'ACTIVE',
            'reason_code': 'USER_REVOKE', 'reason': '不可复活已撤回原记录', 'expected_version': 1,
            'resume_event_id': receipt['event_id'], 'idempotency_key': 'resume-revoked'})
        assert resume.status_code == 409, resume.text
        assert resume.json()['detail'] == 'REVOKED_REQUIRES_SUCCESSOR_GRANT'
    with TestClient(create_app(directory, capability_method_file=file)) as client:
        assert client.get('/api/capabilities/grants/' + original['grant_id'] + '/status').json()['state'] == 'REVOKED'
        assert client.get('/api/capabilities/grants').json() == [original]
        assert client.get('/api/intents').json()['intents'] == [pending]


def test_reason_bound_resume_rechecks_current_evidence_and_requires_a_new_action(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = action_package()
    file = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        prepare(client, package)
        original = client.get('/api/capabilities/grants').json()[0]
        old = client.post('/api/actions/evaluate', json={}).json()
        paused = client.post('/api/capabilities/lifecycle', json={'grant_id': original['grant_id'], 'scope': 'MODEL', 'state': 'SUSPENDED',
            'reason_code': 'USER_PAUSE', 'reason': '主动暂停', 'expected_version': 0, 'idempotency_key': 'pause'}).json()
        resume = {'grant_id': original['grant_id'], 'scope': 'MODEL', 'state': 'ACTIVE', 'reason_code': 'USER_PAUSE',
            'reason': '恢复当前有效资格范围', 'expected_version': 1, 'resume_event_id': paused['event_id'], 'idempotency_key': 'resume'}
        wrong = client.post('/api/capabilities/lifecycle', json={**resume, 'resume_event_id': 'other-event', 'idempotency_key': 'wrong'})
        assert wrong.status_code == 409
        restored = client.post('/api/capabilities/lifecycle', json=resume)
        assert restored.status_code == 200, restored.text
        assert restored.json()['version'] == 2 and restored.json()['resume_event_id'] == paused['event_id']
        assert client.get('/api/capabilities/grants/' + original['grant_id'] + '/status').json()['state'] == 'METHOD_GRANTED'
        current = client.get('/api/actions/current').json()
        (tmp_path / 'resume-public-payload.json').write_text(json.dumps({'original': old, 'paused': paused,
            'restored': restored.json(), 'current_after_resume': current,
            'action_events': client.get('/api/actions/events').json()}, ensure_ascii=False, indent=2), encoding='utf-8')
        assert current['decisions'] == [], current
        assert client.post('/api/intents/prepare', json=intent_command(old)).status_code == 409
        fresh = client.post('/api/actions/evaluate', json={}).json()
        assert len(fresh['decisions']) == 1
        assert fresh['evaluation_id'] != old['evaluation_id']
        assert client.get('/api/actions/evaluations/' + old['evaluation_id']).json() == old
        assert client.get('/api/capabilities/grants').json() == [original]
