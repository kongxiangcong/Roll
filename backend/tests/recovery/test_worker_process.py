"""Independent OS worker consumes durable jobs; API never takes its lease."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from fastapi.testclient import TestClient
from roll.app import create_app
from test_account_process import Server


def wait_for(query, predicate, process=None):
    for _ in range(200):
        value = query()
        if predicate(value):
            return value
        if process is not None and process.poll() is not None:
            raise AssertionError(f'worker exited: {process.returncode}')
        time.sleep(.05)
    raise AssertionError(f'public receipt did not reach expected state: {value}')


def launch_worker(directory, log_path):
    env = {**os.environ, 'ROLL_ENV': 'test', 'ROLL_DATA_DIR': str(directory)}
    env.pop('ROLL_ENV_FILE', None)
    startup = subprocess.STARTUPINFO() if sys.platform == 'win32' else None
    if startup:
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
    log = log_path.open('w', encoding='utf-8')
    process = subprocess.Popen([sys.executable, '-m', 'roll.worker'], env=env,
        cwd=Path(__file__).resolve().parents[2], stdout=log, stderr=subprocess.STDOUT,
        startupinfo=startup, creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NEW_CONSOLE) if startup else 0)
    return process, log


def test_independent_worker_lease_survives_api_reads_and_recovers_real_death_without_backfill(tmp_path, monkeypatch):
    monkeypatch.setenv('ROLL_RUNTIME_ROLE', 'API')
    monkeypatch.delenv('ROLL_ENV_FILE', raising=False)
    directory = tmp_path / 'runtime'
    api = Server(directory)
    workers = []
    try:
        assert api.client.get('/api/health').json()['runtime_role'] == 'API'
        first = api.client.post('/api/reviews/tasks', json={'mode':'ON_DEMAND','cutoff':'2026-10-07T02:00:00+00:00'}).json()
        assert api.client.get('/api/reviews/tasks/' + first['task_id']).json()['status'] == 'QUEUED'
        worker, log = launch_worker(directory, tmp_path/'worker-first.log'); workers.append((worker,log))
        health = wait_for(lambda: api.client.get('/api/reviews/health').json(), lambda v: v['worker_state']=='RUNNING',worker)
        worker_pid = health['worker']['host_owner']['pid']
        assert worker_pid != api.process.pid
        completed = wait_for(lambda: api.client.get('/api/reviews/tasks/'+first['task_id']).json(),lambda v:v['result'] is not None,worker)
        with TestClient(create_app(directory,runtime_role='API')) as additional_api:
            assert additional_api.get('/api/reviews/health').json()['worker']['host_owner']['pid']==worker_pid
        assert api.client.get('/api/reviews/health').json()['worker']['host_owner']['pid']==worker_pid
        assert completed['result']['forecast'] is None
        duplicate, duplicate_log = launch_worker(directory,tmp_path/'worker-duplicate.log'); workers.append((duplicate,duplicate_log))
        assert duplicate.wait(timeout=30) != 0
        duplicate_log.flush()
        assert 'BACKGROUND_WORKER_ALREADY_RUNNING' in (tmp_path/'worker-duplicate.log').read_text(encoding='utf-8')
        assert api.client.get('/api/reviews/health').json()['worker']['host_owner']['pid'] == worker_pid
        os.kill(worker_pid, signal.SIGTERM); worker.wait(timeout=10)
        assert api.client.get('/api/reviews/health').json()['worker_state'] == 'STOPPED'
        second = api.client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','cutoff':'2026-10-08T00:00:00+08:00'}).json()
        time.sleep(.15)
        assert api.client.get('/api/reviews/tasks/'+second['task_id']).json()['status'] == 'QUEUED'
        restarted, restarted_log = launch_worker(directory,tmp_path/'worker-restarted.log'); workers.append((restarted,restarted_log))
        recovered = wait_for(lambda:api.client.get('/api/reviews/tasks/'+second['task_id']).json(),lambda v:v['result'] is not None,restarted)
        assert recovered['task_id']==second['task_id'] and recovered['attempts']==1
        assert api.client.get('/api/reviews/tasks/'+first['task_id']).json()==completed
        coverage=api.client.get('/api/reviews/coverage').json()
        assert coverage['gaps'][-1]['reason']=='PROCESS_OR_SLEEP_GAP_UNOBSERVED'
        assert coverage['forward_predictions_reconstructed'] is False
        assert coverage['expired_opportunities_sent'] is False
        assert all(v['result']['forward_sample_created'] is False for v in api.client.get('/api/reviews/history').json())
        assert api.client.get('/api/account').json()['version']==0
        if sys.platform == 'win32':
            # A hidden, separate console prevents broadcast reaching pytest.
            sender = """import ctypes,sys,time
k=ctypes.windll.kernel32
k.FreeConsole()
assert k.AttachConsole(int(sys.argv[1]))
handler=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_uint)(lambda event:True)
assert k.SetConsoleCtrlHandler(handler,True)
assert k.GenerateConsoleCtrlEvent(1,0)
time.sleep(.2)
"""
            owner = api.client.get('/api/reviews/health').json()['worker']['host_owner']['pid']
            subprocess.run([sys.executable, '-c', sender, str(owner)], check=True, timeout=10,
                startupinfo=subprocess.STARTUPINFO(), creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            restarted.send_signal(signal.SIGTERM)
        assert restarted.wait(timeout=20)==0
        assert api.client.get('/api/reviews/coverage').json()['sessions'][-1]['close_reason']=='NORMAL_CLOSE_NO_ALWAYS_ON_REQUIREMENT'
        assert api.client.get('/api/reviews/health').json()['worker_state']=='STOPPED'
        assert api.process.poll() is None
        backup=api.client.post('/api/runtime/backups').json()
        bundle=api.client.get('/api/runtime/backups/'+backup['backup_id']+'/export').content
        staged=api.client.post('/api/runtime/restores',content=bundle,headers={'content-type':'application/zip'})
        assert staged.status_code==202 and staged.json()['state']=='PENDING_RESTART'
        blocked, blocked_log=launch_worker(directory,tmp_path/'worker-restore-blocked.log');workers.append((blocked,blocked_log))
        assert blocked.wait(timeout=30)!=0
        assert 'RESTORE_PENDING_STOP_ALL_LOCAL_HOSTS' in (tmp_path/'worker-restore-blocked.log').read_text(encoding='utf-8')
        assert api.client.get('/api/account').json()['version']==0
        assert api.client.get('/api/runtime/backups/status').json()['pending_restore'] is not None
        api.stop()
        api=Server(directory)
        assert api.client.get('/api/runtime/backups/status').json()['recovery']['state']=='RECOVERY_LOCK'
        assert api.client.post('/api/formal/evaluate').json()['detail']['code']=='RECOVERY_LOCK'
        restored, restored_log=launch_worker(directory,tmp_path/'worker-restored.log');workers.append((restored,restored_log))
        wait_for(lambda:api.client.get('/api/reviews/health').json(),lambda v:v['worker_state']=='RUNNING',restored)
        assert api.client.get('/api/runtime/backups/status').json()['recovery']['state']=='RECOVERY_LOCK'
        assert api.client.get('/api/reviews/coverage').json()['forward_predictions_reconstructed'] is False
    finally:
        for process, log in workers:
            if process.poll() is None:
                if sys.platform=='win32':
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],
                        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
                else:
                    process.kill()
                process.wait(timeout=10)
            log.close()
        api.stop()
