"""Actual API/Agents SDK OS death and recovery with a synthetic provider credential."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

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
        code=wintypes.DWORD();assert kernel.GetExitCodeProcess(handle,ctypes.byref(code));return code.value==259
    finally:kernel.CloseHandle(handle)


@pytest.mark.parametrize('tamper',['NONE','MARKER','JUNCTION'])
def test_actual_sdk_host_crash_active_peer_and_precise_recovery(tmp_path,tamper):
    with socket.socket() as connection:
        connection.bind(('127.0.0.1',0));port=connection.getsockname()[1]
    support=Path(__file__).parents[1]/'support'
    env={**os.environ,'ROLL_ENV':'test','ROLL_DATA_DIR':str(tmp_path/'data'),
        'DEEPSEEK_API_KEY':'ROLL_METHOD_CASE_ONLY','PYTHONPATH':str(support)}
    env.pop('ROLL_DEEPSEEK_API_KEY_FILE',None)
    def start():
        process=subprocess.Popen([sys.executable,'-m','uvicorn','deepseek_method_app:factory','--factory',
            '--host','127.0.0.1','--port',str(port),'--log-level','error'],env=env,
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
                'effective_at':'2026-10-08T00:00:00+08:00','source':'12 SDK OS fault method case','cash_balance':'10000.00',
                'broker_available':None,'broker_frozen':None,'withdrawable':None,'permission_profile':[],
                'positions':[{'instrument':'SSE:600519','quantity':'100','sellable_quantity':None,'reference_cost':None}]}}).json()
            assert client.post('/api/account/confirm',json={'draft_id':draft['draft_id'],'idempotency_key':'baseline'}).status_code==200
            parent=client.post('/api/data/requests',json={'instruments':['SSE:600519'],'groups':['QUOTE'],'purpose':'OBSERVATION',
                'start_date':'2026-10-07','end_date':'2026-10-07'}).json()
            run_id=client.post('/api/data/requests/'+parent['request_id']+'/deepseek',json={'question':'WAIT_METHOD'}).json()['run_id']
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                run=client.get('/api/data/runs/'+run_id).json()
                if run.get('model_requests'):break
                time.sleep(.05)
            assert run['status']=='RUNNING' and len(run['model_requests'])==1
            pids=run['process']['observed_pids'];assert len(pids)>=2
            task_root=Path(run['process']['task_root']);assert not (task_root/'home'/'auth.json').exists()
            # A peer host may query the same DB, without interrupting or cleaning this live owner.
            from roll.app import create_app
            peer=create_app(tmp_path/'data')
            assert peer.state.evidence.get('retrieval_runs',run_id)['status']=='RUNNING'
            from roll.agents.deepseek_evidence import DeepSeekQuestion
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as blocked:
                peer.state.deepseek.start(parent['request_id'],DeepSeekQuestion(question='peer'))
            assert blocked.value.status_code==409
            marker=task_root/'.roll-owner.json';original=marker.read_bytes()
            if tamper=='MARKER':marker.write_text('{}')
            if tamper=='JUNCTION':
                target=tmp_path/'outside';target.mkdir();(target/'preserve.txt').write_text('outside root')
                link=task_root/'escape';powershell=Path(os.environ['SYSTEMROOT'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
                subprocess.run([str(powershell),'-NoProfile','-Command',
                    'New-Item -ItemType Junction -Path $env:ROLL_TEST_LINK -Target $env:ROLL_TEST_TARGET | Out-Null'],
                    env={**os.environ,'ROLL_TEST_LINK':str(link),'ROLL_TEST_TARGET':str(target)},
                    check=True,creationflags=subprocess.CREATE_NO_WINDOW)
            process.kill();process.wait(timeout=5)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline and any(alive(pid) for pid in pids):time.sleep(.05)
            assert not any(alive(pid) for pid in pids)
            process=start();recovered=client.get('/api/data/runs/'+run_id).json()
            assert recovered['status']=='INTERRUPTED' and recovered['evidence_kind']=='METHOD_CASE_DEEPSEEK'
            if tamper!='NONE':
                assert recovered['recovery_cleanup']['status']=='REFUSED_OR_FAILED'
                assert task_root.exists()
                marker.write_bytes(original)
                if tamper=='JUNCTION':
                    os.rmdir(link);assert (target/'preserve.txt').read_text()=='outside root'
                process.kill();process.wait(timeout=5);process=start()
                recovered=client.get('/api/data/runs/'+run_id).json()
            assert recovered['recovery_cleanup']['status']=='REMOVED' and not task_root.exists()
    finally:process.kill();process.wait(timeout=5)
