"""Actual OS termination at observation/maintenance transaction boundaries."""
import time
import httpx
import pytest
import os
import subprocess
import sys
import signal
from test_account_process import Server,free_port


def result(client,identifier):
    for _ in range(100):
        value=client.get('/api/reviews/tasks/'+identifier).json()
        if value['result'] is not None:return value
        time.sleep(.05)
    raise AssertionError('recovered observation did not complete')


@pytest.mark.parametrize('fault,attempts',[('review_before_commit',2),('review_after_commit',1),('after_receipt',1)])
def test_actual_review_process_commit_and_identity_recover_without_duplicate_audit_or_account_write(tmp_path,fault,attempts):
    server=Server(tmp_path/'data',None if fault=='after_receipt' else fault)
    original=None
    command={'mode':'ON_DEMAND','cutoff':'2026-10-08T00:00:00+08:00'}
    try:
        try:
            response=server.client.post('/api/reviews/tasks',json=command)
            assert response.status_code==202,response.text
            identifier=response.json()['task_id']
        except httpx.TransportError:identifier=None
        if fault=='after_receipt':original=result(server.client,identifier)
        else:assert server.process.wait(timeout=10)==86
    finally:server.stop()
    recovered=Server(tmp_path/'data')
    try:
        history=recovered.client.get('/api/reviews/history').json()
        assert len(history)==1
        value=result(recovered.client,history[0]['task_id'])
        assert value['attempts']==attempts
        assert value['result']['forward_sample_created'] is False
        assert value['result']['cutoff']==command['cutoff']
        audit=recovered.client.get('/api/reviews/audits/'+value['audit_id']).json()
        assert audit['task_id']==value['task_id']
        assert recovered.client.post('/api/reviews/tasks',json=command).json()['task_id']==value['task_id']
        assert len(recovered.client.get('/api/reviews/history').json())==1
        assert recovered.client.get('/api/account').json()['version']==0
        if original:assert value==original
        gaps=recovered.client.get('/api/reviews/coverage').json()['gaps']
        assert gaps and gaps[-1]['monitoring_fault'] is False
    finally:recovered.stop()


@pytest.mark.skipif(sys.platform!='win32',reason='actual Windows uvicorn graceful shutdown boundary')
def test_actual_windows_graceful_shutdown_keeps_normal_gap_without_fault_or_new_prediction(tmp_path):
    port=free_port();directory=tmp_path/'data'
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    with open(tmp_path/'normal-service-close.log','w',encoding='utf-8') as log:
        process=subprocess.Popen([sys.executable,'-m','uvicorn','roll.app:create_app','--factory','--host','127.0.0.1','--port',str(port)],
            env={**os.environ,'ROLL_DATA_DIR':str(directory),'ROLL_ENV':'test'},stdout=log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,startupinfo=startup)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=10) as client:
                for _ in range(200):
                    try:
                        if client.get('/api/health').status_code==200:break
                    except httpx.TransportError:pass
                    time.sleep(.05)
                task=client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND'}).json()
                original=result(client,task['task_id'])
            process.send_signal(signal.CTRL_BREAK_EVENT)
            process.wait(timeout=15)
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=10)
    recovered=Server(directory)
    try:
        coverage=recovered.client.get('/api/reviews/coverage').json()
        assert coverage['sessions'][-2]['close_reason']=='NORMAL_CLOSE_NO_ALWAYS_ON_REQUIREMENT'
        assert coverage['gaps'][-1]['reason']=='NORMAL_OFFLINE_NO_COVERAGE_PROMISED'
        assert coverage['gaps'][-1]['monitoring_fault'] is False
        assert recovered.client.get('/api/reviews/tasks/'+original['task_id']).json()==original
        assert len(recovered.client.get('/api/reviews/history').json())==1
    finally:recovered.stop()


@pytest.mark.parametrize('fault',['maintenance_before_commit','maintenance_after_commit'])
def test_actual_process_maintenance_trigger_is_atomic_and_recovery_checks_original_due_once(tmp_path,fault):
    server=Server(tmp_path/'data',fault)
    command={'kind':'WEEKLY','exchange':'SSE','first_due_at':'2026-09-30T16:00:00+08:00'}
    try:
        try:
            response=server.client.post('/api/reviews/maintenance',json=command)
            assert response.status_code==201,response.text
        except httpx.TransportError:pass
        assert server.process.wait(timeout=10)==86
    finally:server.stop()
    recovered=Server(tmp_path/'data')
    try:
        for _ in range(100):
            checks=recovered.client.get('/api/reviews/maintenance/checks').json()
            if checks:break
            time.sleep(.05)
        assert len(checks)==1
        assert checks[0]['scheduled_at']=='2026-09-30T16:00:00+08:00'
        assert checks[0]['business_checks']['mature_labels']['value'] is None
        assert recovered.client.post('/api/reviews/maintenance/check').json()==checks
        assert len(recovered.client.get('/api/reviews/maintenance').json())==1
        assert recovered.client.get('/api/account').json()['version']==0
    finally:recovered.stop()


def test_three_actual_process_interruptions_exhaust_same_task_without_fourth_attempt(tmp_path):
    directory=tmp_path/'data'
    identifier=None
    for attempt in range(3):
        if attempt:
            with open(tmp_path/f'interruption-{attempt}.log','w',encoding='utf-8') as log:
                process=subprocess.Popen([sys.executable,'-m','uvicorn','roll.app:create_app','--factory','--host','127.0.0.1','--port','0'],
                    env={**os.environ,'ROLL_DATA_DIR':str(directory),'ROLL_ENV':'test','ROLL_TEST_CRASH_POINT':'review_before_commit'},stdout=log,stderr=subprocess.STDOUT)
                assert process.wait(timeout=20)==86
            continue
        server=Server(directory,'review_before_commit')
        try:
            if identifier is None:
                response=server.client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','cutoff':'2026-10-08T00:00:00+08:00'})
                if response.status_code==202:identifier=response.json()['task_id']
            assert server.process.wait(timeout=10)==86
        finally:server.stop()
    recovered=Server(directory)
    try:
        for _ in range(100):
            task=recovered.client.get('/api/reviews/history').json()[0]
            if task['status']=='FAILED':break
            time.sleep(.02)
        assert task['status']=='FAILED' and task['attempts']==3,task
        assert task['recovery_reason']=='ATTEMPT_LIMIT_AFTER_INTERRUPTION'
        assert task['result'] is None
        assert recovered.client.get('/api/reviews/audits/'+task['audit_id']).json()['metrics']['module_errors']['errors'][-1]['code']=='ATTEMPT_LIMIT_AFTER_INTERRUPTION'
        assert len(recovered.client.get('/api/reviews/history').json())==1
    finally:recovered.stop()
