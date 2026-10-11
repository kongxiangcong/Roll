from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_capability_monitoring import monitored_package
from test_actions import prepare
from datetime import datetime, timedelta, timezone
import time
import pytest


def test_real_maintenance_worker_checks_running_post_close_once_and_keeps_terminal_grant_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    instant = datetime(2026, 10, 9, 15, 31, tzinfo=timezone(timedelta(hours=8)))
    import capability_method_app
    monkeypatch.setattr(capability_method_app, 'ANCHOR', instant)
    clock = [instant]
    monkeypatch.setattr('roll.decisions.capabilities.now', lambda: clock[0].isoformat())
    monkeypatch.setattr('roll.decisions.monitoring.now', lambda: clock[0].isoformat())
    package = monitored_package(20)
    file = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file, review_clock=lambda: clock[0])) as client:
        grant = prepare(client, package)
        deadline = time.monotonic() + 8
        rows = []
        while time.monotonic() < deadline:
            rows = client.get('/api/capabilities/monitoring').json()
            if rows: break
            time.sleep(.05)
        assert len(rows) == 1, rows
        assert rows[0]['basis'] == 'RUNNING_POST_CLOSE'
        assert rows[0]['status'] == 'CHECKED'
        assert rows[0]['confirmation_pass_look'] is False
        assert rows[0]['maturity']['review_status'] == 'NOT_AT_REGISTERED_CHECKPOINT'
        assert client.get('/api/capabilities/grants').json() == [grant]
        assert client.post('/api/formal/evaluate', json={}).status_code == 403
        revoked = client.post('/api/capabilities/lifecycle', json={'grant_id':grant['grant_id'], 'scope':'MODEL',
            'state':'REVOKED','reason_code':'USER_REVOKE','reason':'终止原资格，后台不得重启监测',
            'expected_version':0,'idempotency_key':'revoke'})
        assert revoked.status_code == 200, revoked.text
        clock[0] += timedelta(days=3)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            sessions = client.get('/api/reviews/coverage').json()['sessions']
            if sessions[-1]['last_seen_at'] == clock[0].isoformat(): break
            time.sleep(.05)
        assert sessions[-1]['last_seen_at'] == clock[0].isoformat()
        # Observe several actual worker heartbeats after the monotone next day.
        for _ in range(5):
            time.sleep(.1)
            assert client.get('/api/capabilities/monitoring').json() == rows
        assert client.get('/api/capabilities/grants/' + grant['grant_id'] + '/status').json()['state'] == 'REVOKED'


def test_all_monitor_pause_invalidates_queued_observation_without_stopping_facts_or_backup(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    # Ordered request contract; no lifespan thread is started for this sequence.
    client = TestClient(create_app(tmp_path))
    try:
        queued = client.post('/api/reviews/tasks', json={'refresh_missing': False})
        assert queued.status_code == 202, queued.text
        task = queued.json()
        assert task['status'] == 'QUEUED'
        pause = client.post('/api/capabilities/lifecycle', json={'scope': 'ALL_MONITOR', 'state': 'SUSPENDED',
            'reason_code': 'USER_PAUSE', 'reason': '停止监测', 'expected_version': 0, 'idempotency_key': 'pause'})
        assert pause.status_code == 200, pause.text
        closed = client.get('/api/reviews/tasks/' + task['task_id']).json()
        assert closed['status'] == 'CANCELLED', closed
        assert closed['cancel_reason'] == 'ALL_MONITOR_SUSPENDED'
        assert closed['lifecycle_event_id'] == pause.json()['event_id']
        assert closed['attempts'] == 0
        assert client.get('/api/account').status_code == 200
        assert client.post('/api/runtime/backups').status_code == 201
        resume = client.post('/api/capabilities/lifecycle', json={'scope': 'ALL_MONITOR', 'state': 'ACTIVE',
            'reason_code': 'USER_PAUSE', 'reason': '恢复新监测', 'resume_event_id': pause.json()['event_id'],
            'expected_version': 1, 'idempotency_key': 'resume'})
        assert resume.status_code == 200
        assert client.get('/api/reviews/tasks/' + task['task_id']).json() == closed
        assert client.post('/api/reviews/tasks', json={'refresh_missing': False}).status_code == 202
    finally:
        client.close()


@pytest.mark.parametrize('targeted', [False, True])
def test_all_monitor_pause_refuses_direct_monitoring_without_new_records(tmp_path, monkeypatch, targeted):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = monitored_package(20)
    file = save_package(tmp_path / 'qualification.json', package)
    with TestClient(create_app(tmp_path / 'data', capability_method_file=file)) as client:
        grant = prepare(client, package)
        paused = client.post('/api/capabilities/lifecycle', json={'scope': 'ALL_MONITOR', 'state': 'SUSPENDED',
            'reason_code': 'USER_PAUSE', 'reason': '所有相关监测停止，保留事实和审计', 'expected_version': 0, 'idempotency_key': 'pause',
            **({'grant_id':grant['grant_id']} if targeted else {})})
        assert paused.status_code == 200
        before = client.get('/api/capabilities/monitoring').json()
        refused = client.post('/api/capabilities/monitoring/check', json={'grant_id': grant['grant_id'], 'basis': '直接请求也须守范围'})
        assert refused.status_code == 409, refused.text
        assert refused.json()['detail'] == 'ALL_MONITOR_SUSPENDED'
        assert client.get('/api/capabilities/monitoring').json() == before
        assert client.get('/api/account').status_code == 200
        assert client.post('/api/runtime/backups').status_code == 201
