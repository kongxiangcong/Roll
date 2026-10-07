"""Real OS server death/restart; external worker is a labelled method case."""
import ctypes
from ctypes import wintypes
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


def alive(pid):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return False
    try:
        code=wintypes.DWORD()
        assert kernel.GetExitCodeProcess(handle,ctypes.byref(code))
        return code.value==259
    finally:kernel.CloseHandle(handle)


@pytest.mark.parametrize('tamper', ['NONE','MARKER','JUNCTION'])
def test_api_process_death_closes_job_and_restart_marks_interrupted(tmp_path,tamper):
    with socket.socket() as connection:
        connection.bind(('127.0.0.1',0));port=connection.getsockname()[1]
    worker=tmp_path/'worker.py'
    worker.write_text('''import json,sys,subprocess,time
json.loads(sys.stdin.readline())
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)'])
print(json.dumps({'kind':'turn','turn_id':'method-case-turn'}),flush=True)
time.sleep(120)
''')
    server=tmp_path/'server.py'
    server.write_text('''import sys,uvicorn
from pathlib import Path
from roll.app import create_app
uvicorn.run(create_app(Path(sys.argv[1]),codex_worker=Path(sys.argv[2])),host='127.0.0.1',port=int(sys.argv[3]),log_level='error')
''')
    auth=tmp_path/'auth.json';auth.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    env={**os.environ,'ROLL_ENV':'test','ROLL_CODEX_AUTH_FILE':str(auth)}
    def start():
        process=subprocess.Popen([sys.executable,str(server),str(tmp_path/'data'),str(worker),str(port)],env=env,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            try:
                if httpx.get(f'http://127.0.0.1:{port}/api/health',timeout=.5).status_code==200:return process
            except httpx.HTTPError:pass
            time.sleep(.05)
        process.kill();process.wait();raise AssertionError('Server startup failed')
    process=start()
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}') as client:
            draft=client.post('/api/account/drafts',json={'kind':'BASELINE','expected_account_version':0,'payload':{
                'effective_at':'2026-10-08T00:00:00+08:00','source':'11 OS fault method case','cash_balance':'10000.00',
                'broker_available':None,'broker_frozen':None,'withdrawable':None,'permission_profile':[],
                'positions':[{'instrument':'SSE:600519','quantity':'100','sellable_quantity':None,'reference_cost':None}]}}).json()
            assert client.post('/api/account/confirm',json={'draft_id':draft['draft_id'],'idempotency_key':'baseline'}).status_code==200
            request=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['QUOTE'],'purpose':'OBSERVATION',
                'start_date':'2026-10-07','end_date':'2026-10-07'}).json()
            run_id=client.post('/api/data/requests/'+request['request_id']+'/codex',json={'question':'WAIT'}).json()['run_id']
            for _ in range(200):
                run=client.get('/api/data/runs/'+run_id).json()
                if run.get('runtime_turn_id') and len(run['process'].get('observed_pids',[]))>=2:break
                time.sleep(.025)
            assert run['status']=='RUNNING'
            pids=run['process']['observed_pids'];assert len(pids)>=2
            task_root=Path(run['process']['task_root'])
            assert (task_root/'home'/'auth.json').is_file()
            marker=task_root/'.roll-owner.json'
            original_marker=marker.read_bytes()
            if tamper=='MARKER':marker.write_text('{}')
            if tamper=='JUNCTION':
                target=tmp_path/'outside';target.mkdir();(target/'preserve.txt').write_text('outside task root')
                link=task_root/'escape'
                powershell=Path(os.environ['SYSTEMROOT'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
                subprocess.run([str(powershell),'-NoProfile','-Command',
                    'New-Item -ItemType Junction -Path $env:ROLL_TEST_LINK -Target $env:ROLL_TEST_TARGET | Out-Null'],
                    env={**os.environ,'ROLL_TEST_LINK':str(link),'ROLL_TEST_TARGET':str(target)},
                    check=True,creationflags=subprocess.CREATE_NO_WINDOW)
            process.kill();process.wait(timeout=5)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline and any(alive(pid) for pid in pids):time.sleep(.05)
            assert not any(alive(pid) for pid in pids)
            process=start()
            recovered=client.get('/api/data/runs/'+run_id).json()
            assert recovered['status']=='INTERRUPTED'
            assert recovered['recovery_reason']=='PROCESS_RESTART_BEFORE_SNAPSHOT_COMMIT'
            assert recovered['evidence_kind']=='METHOD_CASE_CODEX'
            if tamper!='NONE':
                reason='OWNER_MARKER_MISMATCH' if tamper=='MARKER' else 'TASK_ROOT_REPARSE_POINT'
                assert recovered['recovery_cleanup']=={'status':'REFUSED_OR_FAILED','reason':reason}
                assert (task_root/'home'/'auth.json').is_file()
                # This test owns only a synthetic token. Repair its precise marker and
                # restart through the public API to finish the registered cleanup.
                marker.write_bytes(original_marker)
                if tamper=='JUNCTION':
                    os.rmdir(link)  # Remove this exact junction, never its target.
                    assert (target/'preserve.txt').read_text()=='outside task root'
                process.kill();process.wait(timeout=5);process=start()
                recovered=client.get('/api/data/runs/'+run_id).json()
            assert recovered['recovery_cleanup']['status']=='REMOVED'
            assert not task_root.exists()
    finally:
        process.kill();process.wait(timeout=5)
