import time
from fastapi.testclient import TestClient
from roll.app import create_app


def test_api_role_enqueues_without_starting_worker_even_on_health_or_recovery(tmp_path):
    with TestClient(create_app(tmp_path, runtime_role='API')) as client:
        assert client.get('/api/health').json()['runtime_role'] == 'API'
        queued = client.post('/api/reviews/tasks', json={'mode': 'ON_DEMAND'}).json()
        recovery = client.post('/api/reviews/recover').json()
        for identifier in [queued['task_id'], recovery['task_id']]:
            assert client.get('/api/reviews/tasks/' + identifier).json()['status'] == 'QUEUED'
        assert client.get('/api/reviews/health').json()['worker_state'] == 'STOPPED'
        assert client.get('/api/reviews/coverage').json()['sessions'] == []
        assert client.get('/api/account').json()['version'] == 0
    with TestClient(create_app(tmp_path)) as client:
        for _ in range(200):
            task = client.get('/api/reviews/tasks/' + queued['task_id']).json()
            if task['result'] is not None:
                break
            time.sleep(.02)
        assert task['status'] in {'COMPLETE', 'PARTIAL'}
        assert task['result']['forecast'] is None
        assert task['result']['forward_sample_created'] is False
        assert client.get('/api/account').json()['version'] == 0



def test_production_factory_defaults_to_api_with_explicit_empty_environment_file(tmp_path, monkeypatch):
    env_file=tmp_path/'empty-runtime.env'
    env_file.write_text('',encoding='utf-8')
    monkeypatch.setenv('ROLL_ENV','local')
    monkeypatch.setenv('ROLL_ENV_FILE',str(env_file))
    monkeypatch.setenv('ROLL_DATA_DIR',str(tmp_path/'p'))
    monkeypatch.delenv('ROLL_RUNTIME_ROLE',raising=False)
    with TestClient(create_app()) as client:
        assert client.get('/api/health').json()['runtime_role']=='API'
        assert client.get('/api/reviews/health').json()['worker_state']=='STOPPED'
        assert client.get('/api/reviews/coverage').json()['sessions']==[]


def test_invalid_runtime_role_fails_before_creating_runtime_files(tmp_path):
    import pytest
    directory=tmp_path/'must-not-be-created'
    with pytest.raises(ValueError,match='INVALID_RUNTIME_ROLE'):
        create_app(directory,runtime_role='UNKNOWN')
    assert not directory.exists()
