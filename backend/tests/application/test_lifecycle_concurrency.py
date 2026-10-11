"""Real concurrent public permission writers/readers, without a worker mock."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from fastapi.testclient import TestClient
from roll.app import create_app
from capability_method_app import save_package
from test_actions import action_package, prepare


def test_live_committing_permission_writer_does_not_leave_a_false_recovery_lock(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_ENV','test')
    package=action_package()
    file=save_package(tmp_path/'qualification.json',package)
    client=TestClient(create_app(tmp_path/'data',capability_method_file=file))
    try:
        grant=prepare(client,package)
        barrier=Barrier(4)
        def read_current():
            barrier.wait()
            states=[]
            for _ in range(12):
                response=client.get('/api/capabilities')
                assert response.status_code==200,response.text
                states.append(response.json()['runtime_state'])
            return states
        with ThreadPoolExecutor(max_workers=3) as pool:
            readers=[pool.submit(read_current) for _ in range(3)]
            barrier.wait()
            for index in range(12):
                pause=client.post('/api/capabilities/lifecycle',json={'scope':'NEW_RISK','state':'SUSPENDED',
                    'reason_code':'USER_PAUSE','reason':'真实公开并发写入','expected_version':index*2,'idempotency_key':f'pause-{index}'})
                assert pause.status_code==200,pause.text
                resume=client.post('/api/capabilities/lifecycle',json={'scope':'NEW_RISK','state':'ACTIVE',
                    'reason_code':'USER_PAUSE','reason':'原主动原因已核对','resume_event_id':pause.json()['event_id'],
                    'expected_version':index*2+1,'idempotency_key':f'resume-{index}'})
                assert resume.status_code==200,resume.text
            observed=[state for task in readers for state in task.result()]
        assert observed and 'RECOVERY_LOCK' not in observed,observed
        assert client.get('/api/capabilities/recovery').json()['state']=='NOT_RESTORED'
        assert not (tmp_path/'data/backups/recovery-lock.json').exists()
        assert client.get('/api/capabilities/grants').json()==[grant]
        assert len([e for e in client.get('/api/capabilities/events').json() if e.get('scope')=='NEW_RISK'])==24
    finally: client.close()
