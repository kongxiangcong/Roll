"""Current host truth, independent basis and METHOD-only presentation."""
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from action_order_method import paired_package, grant_command
from test_action_risk_priority import method_clock, setup, record
from datetime import datetime, timedelta
import pytest
from roll.decisions.capabilities import current_presentation


def test_today_reflects_current_method_scope_without_actual_enablement(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    value = paired_package()
    file = save_package(tmp_path / 'qualification.json', value)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file, runtime_role='API')) as client:
        setup(client, value)
        grant = client.post('/api/capabilities/grants', json=grant_command(value, 'profit'))
        assert grant.status_code == 201, grant.text
        current = client.get('/api/capabilities').json()
        record(tmp_path, 'current-capability', current)
        assert current['state'] == 'METHOD_GRANTED'
        assert current['formal_judgment'] == 'DISABLED'
        assert current.get('headline') == 'METHOD 工程能力有效，实际交易判断未启用'
        assert current['formal_capabilities'] == []
        assert [(row['basis_type'], row['scope']['instruments'], row['system_usable']) for row in current['method_capabilities']] == [
            ('PROFIT_MODEL', ['SSE:600000', 'SSE:600001', 'SSE:600002'], False)]
        today = client.get('/api/today').json()
        record(tmp_path, 'today-capability', today)
        assert today['formal_judgment'] == current['formal_judgment']
        assert today['technical_capability']['headline'] == current['headline']


def test_independent_method_risk_remains_visible_when_profit_paused_then_revoke_and_expire(tmp_path, monkeypatch):
    method_clock(monkeypatch)
    value = paired_package()
    file = save_package(tmp_path / 'qualification.json', value)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file, runtime_role='API')) as client:
        setup(client, value)
        grants = []
        for candidate, key in [(value, 'profit'), (value['risk_qualification'], 'risk')]:
            response = client.post('/api/capabilities/grants', json=grant_command(candidate, key))
            assert response.status_code == 201, response.text
            grants.append(response.json())
        pause = client.post('/api/capabilities/lifecycle', json={'grant_id': grants[0]['grant_id'], 'scope': 'MODEL', 'state': 'SUSPENDED',
            'reason_code': 'USER_PAUSE', 'reason': 'METHOD profit pause', 'expected_version': 0, 'idempotency_key': 'pause'})
        assert pause.status_code == 200, pause.text
        paused = client.get('/api/capabilities/grants/' + grants[0]['grant_id'] + '/status').json()
        assert paused['headline'] == '能力已暂停，交易判断未启用'
        current = client.get('/api/capabilities').json()
        assert current['formal_judgment'] == 'DISABLED'
        assert [row['basis_type'] for row in current['method_capabilities']] == ['RISK_POLICY']
        assert current['method_capabilities'][0]['scope']['instruments'] == ['SSE:600000']
        revoke = client.post('/api/capabilities/lifecycle', json={'grant_id': grants[1]['grant_id'], 'scope': 'MODEL', 'state': 'REVOKED',
            'reason_code': 'USER_REVOKE', 'reason': 'METHOD risk revoke', 'expected_version': 1, 'idempotency_key': 'revoke'})
        assert revoke.status_code == 200, revoke.text
        current = client.get('/api/capabilities').json()
        assert current['headline'] == '能力已撤回，交易判断未启用'
        assert current['method_capabilities'] == []
        after = (datetime.fromisoformat(value['expires_at']) + timedelta(minutes=1)).isoformat()
        monkeypatch.setattr('roll.decisions.capabilities.now', lambda: after)
        current = client.get('/api/capabilities/grants/' + grants[0]['grant_id'] + '/status').json()
        assert current['headline'] == '能力已到期，交易判断未启用'
        record(tmp_path, 'lifecycle-summary', current)


@pytest.mark.parametrize('kinds,headline', [
    (['PROFIT_MODEL'], '收益判断能力有效'),
    (['RISK_POLICY'], '独立降风险能力有效，收益判断未启用'),
    (['PROFIT_MODEL', 'RISK_POLICY'], '收益判断与独立降风险能力有效'),
])
def test_display_projection_of_already_granted_host_facts_is_not_admission(kinds, headline):
    # Pure approved presentation contract only. These are no archived evidence,
    # registered grants, real G gates or production admission success.
    statuses = [{'state': 'GRANTED', 'reasons': [], 'allowed_actions': ['BUY'] if kind == 'PROFIT_MODEL' else ['REDUCE', 'EXIT'],
        'grant': {'candidate_kind': kind, 'grant_id': 'PURE-' + kind, 'scope': {'instruments': ['SSE:600000']},
                  'expires_at': '2026-12-01T15:05:00+08:00', 'system_usable': True}} for kind in kinds]
    statuses.append({'state': 'METHOD_GRANTED', 'reasons': [], 'allowed_actions': ['BUY'],
        'grant': {'candidate_kind': 'PROFIT_MODEL', 'grant_id': 'PURE-METHOD', 'scope': {'instruments': ['SSE:600099']},
                  'expires_at': '2026-12-01T15:05:00+08:00', 'system_usable': False}})
    result = current_presentation({'grant_statuses': statuses, 'state': 'METHOD_GRANTED', 'runtime_state': 'NORMAL',
        'lifecycle': {'scopes': {scope: {'state': 'ACTIVE'} for scope in ['NEW_RISK', 'MODEL', 'ALL_MONITOR']}}})
    assert result['formal_judgment'] == 'ENABLED'
    assert result['headline'] == headline
    assert [row['basis_type'] for row in result['formal_capabilities']] == kinds
    assert all(row['scope'] == {'instruments': ['SSE:600000']} for row in result['formal_capabilities'])
    assert result['method_capabilities'][0]['system_usable'] is False


def test_ungranted_and_public_restore_lock_headlines_use_host_truth(tmp_path):
    with TestClient(create_app(tmp_path / 'data', runtime_role='API')) as client:
        initial = client.get('/api/capabilities').json()
        assert initial['headline'] == '交易判断未启用'
        assert initial['formal_capabilities'] == initial['method_capabilities'] == []
        backup = client.post('/api/runtime/backups')
        assert backup.status_code == 201, backup.text
        exported = client.get('/api/runtime/backups/' + backup.json()['backup_id'] + '/export')
        assert exported.status_code == 200
        staged = client.post('/api/runtime/restores', content=exported.content, headers={'content-type': 'application/zip'})
        assert staged.status_code == 202, staged.text
    with TestClient(create_app(tmp_path / 'data', runtime_role='API')) as client:
        current = client.get('/api/capabilities').json()
        record(tmp_path, 'recovery-summary', current)
        assert current['runtime_state'] == 'RECOVERY_LOCK'
        assert current['headline'] == '恢复锁生效，交易判断未启用'
        assert current['formal_judgment'] == 'DISABLED'
        assert current['formal_capabilities'] == current['method_capabilities'] == []
        assert client.get('/api/today').json()['technical_capability']['headline'] == current['headline']
