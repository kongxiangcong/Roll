from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import prepare
from test_capability_monitoring import monitored_package


def test_registered_maintenance_consumes_monitoring_and_expiry_without_training_or_extra_pass(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV', 'test')
    package = monitored_package(20, outside=4)
    instant = datetime.fromisoformat(package['required_as_of'])
    clock = [instant]
    file = save_package(tmp_path / 'qualification.json', package)
    # Ordered public request contract; maintenance is explicitly driven here.
    client = TestClient(create_app(tmp_path / 'data', capability_method_file=file, review_clock=lambda: clock[0]))
    try:
        prepare(client, package)
        grant = client.get('/api/capabilities/grants').json()[0]
        scheduled = client.post('/api/reviews/maintenance', json={'kind': 'WEEKLY', 'exchange': 'SSE',
            'first_due_at': '2026-10-09T15:30:00+08:00'})
        assert scheduled.status_code == 201, scheduled.text
        checked = client.post('/api/reviews/maintenance/check')
        assert checked.status_code == 200, checked.text
        rows = checked.json()
        assert len(rows) == 1 and rows[0]['status'] == 'OVERDUE_CHECKED'
        checks = rows[0]['business_checks']
        assert checks['mature_labels']['status'] == 'CHECKED', checks
        assert checks['qualification_expiry']['status'] == 'CHECKED'
        assert checks['new_experiment_conditions']['automatic_fit'] is False
        assert rows[0]['statistical_pass_checks_added'] == 0 and rows[0]['retrained'] is False
        monitor = client.get('/api/capabilities/monitoring').json()
        assert len(monitor) == 1 and monitor[0]['status'] == 'RESTRICTED'
        assert monitor[0]['check_id'] in checks['mature_labels']['check_ids']
        assert client.get('/api/actions/current').json()['decisions'] == []
        assert client.post('/api/reviews/maintenance/check').json() == rows
        assert client.get('/api/capabilities/grants').json() == [grant]
    finally:
        client.close()
