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


def test_api_post_close_job_and_independent_worker_share_bounded_archive_without_forward(tmp_path, monkeypatch):
    import json
    import httpx
    from test_post_close_packet import setup

    clock='2026-10-12T15:06:00+08:00'
    for module in ['roll.research.prospective','roll.market.post_close_packet','roll.market.evidence']:
        monkeypatch.setattr(module+'.now',lambda:clock)
    calls=[]
    raw=json.dumps({'date':20261012,'time':150005,'list':[
        ['600362','江西铜业',100,101,99,100,1234,123400,100]]},ensure_ascii=False).encode()
    def supplier(request):
        calls.append(str(request.url))
        return httpx.Response(200,content=raw)
    transport=httpx.MockTransport(supplier)
    api=create_app(tmp_path,market_transport=transport,runtime_role='API')
    with TestClient(api) as client:
        plan=setup(client)
        path='/api/research/collections/'+plan+'/post-close/check'
        account=client.get('/api/account').json()
        response=client.post(path,json={'basis':'METHOD API role composition'})
        assert response.status_code==201,response.text
        job=response.json()
        assert job['state']=='RECORDED' and job['actual_forward_start'] is False
        assert client.get('/api/reviews/health').json()['worker_state']=='STOPPED'
        assert client.get('/api/reviews/coverage').json()['sessions']==[]
        worker=create_app(tmp_path,market_transport=transport,runtime_role='WORKER')
        with TestClient(worker) as worker_client:
            assert worker_client.get('/api/health').json()['runtime_role']=='WORKER'
            assert client.get('/api/reviews/health').json()['worker_state']=='RUNNING'
            queued=client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','refresh_missing':False}).json()
            for _ in range(200):
                task=client.get('/api/reviews/tasks/'+queued['task_id']).json()
                if task['result'] is not None:break
                time.sleep(.02)
            assert task['status'] in {'COMPLETE','PARTIAL'}
            assert task['result']['forecast'] is None and task['result']['forward_sample_created'] is False
            assert client.post(path,json={'basis':'repeated composition check'}).json()==job
            assert len(client.get('/api/research/collections/'+plan+'/batches').json())==1
            assert len(calls)==1
            assert client.get('/api/account').json()==account
        assert client.get('/api/reviews/health').json()['worker_state']=='STOPPED'
