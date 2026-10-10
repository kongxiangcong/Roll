"""Actual process crashes/races at forward file and SQLite commit boundaries."""
import os
import subprocess
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from test_account_process import free_port


class ForwardServer:
    def __init__(self,directory,clock,fault=None):
        port=free_port(); backend=Path(__file__).resolve().parents[2]
        env={**os.environ,'ROLL_ENV':'test','ROLL_DATA_DIR':str(directory),'ROLL_FORWARD_METHOD_NOW':clock,
            'PYTHONPATH':str(backend/'src')+os.pathsep+str(backend/'tests/support')}
        env.pop('ROLL_TEST_CRASH_POINT',None)
        if fault:env['ROLL_TEST_CRASH_POINT']=fault
        self.log=open(directory.parent/f'forward-server-{port}.log','w',encoding='utf-8')
        self.process=subprocess.Popen([sys.executable,'-B','-X','utf8','-m','uvicorn','forward_method_app:factory','--factory',
            '--host','127.0.0.1','--port',str(port)],cwd=backend,env=env,stdout=self.log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.client=httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=30)
        for _ in range(200):
            if self.process.poll() is not None:break
            try:
                if self.client.get('/api/health').status_code==200:return
            except httpx.TransportError:pass
            time.sleep(.05)
        if fault and self.process.poll()==86:return  # Worker can hit the same common use case before health.
        self.stop();raise AssertionError('forward server failed to start')

    def stop(self):
        if self.process.poll() is None:self.process.kill();self.process.wait(timeout=10)
        self.client.close();self.log.close()


def prepared(directory):
    from datetime import datetime
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'application'))
    from test_shadow import setup,freeze
    clock=datetime.fromisoformat('2026-06-10T14:00:00+08:00')
    with TestClient(create_app(directory,review_clock=lambda:clock)) as client:
        _,protocol,model,dates=setup(client,directory)
        frozen=freeze(client,protocol,model).json()
        path='/api/research/complete-freezes/'+frozen['freeze_id']+'/forward'
        # Registration is before the controlled checkpoint; host-only factory later advances it.
        client.post(path,json={'purpose':'METHOD_VALIDATION','basis':'OS fault METHOD archive'})
    return path,dates[110]+'T16:00:00+08:00'


@pytest.mark.parametrize('fault,committed',[('forward_after_archive',False),('forward_before_commit',False),('forward_after_commit',True)])
def test_real_process_archive_and_first_clock_commit_are_atomic(tmp_path,fault,committed):
    directory=tmp_path/'data';path,clock=prepared(directory)
    server=ForwardServer(directory,clock,fault)
    try:
        if server.process.poll() is None:
            try:server.client.post(path+'/check',json={'basis':'Fault at shared public use case'})
            except httpx.TransportError:pass
        assert server.process.wait(timeout=20)==86
    finally:server.stop()
    # A before-checkpoint recovery cannot fabricate success from an orphan file.
    recovered=ForwardServer(directory,clock[:11]+'14:00:00+08:00')
    try:
        state=recovered.client.get(path).json()
        assert len(state['samples'])==int(committed)
        assert bool(state['method_started_at']) is committed
        assert state['forward_started_at'] is None
        assert recovered.client.get('/api/account').json()['version']==0
    finally:recovered.stop()
    final=ForwardServer(directory,clock)
    try:
        state=final.client.post(path+'/check',json={'basis':'Retry original checkpoint'}).json()
        assert len(state['samples'])==1 and state['shadow']['revision']==1
        assert final.client.post(path+'/replay').json()['matches_original'] is True
        assert state['forward_started_at'] is None
    finally:final.stop()


def test_real_http_concurrent_triggers_keep_one_sample_after_abrupt_stop(tmp_path):
    directory=tmp_path/'data';path,clock=prepared(directory)
    server=ForwardServer(directory,clock)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses=list(pool.map(lambda i:server.client.post(path+'/check',json={'basis':f'Distinct snapshot/account trigger {i}'}),range(4)))
        assert all(r.status_code==201 for r in responses)
        samples=[r.json()['samples'] for r in responses]
        assert all(s==samples[0] for s in samples) and len(samples[0])==1
        original=server.client.get(path).json()
    finally:server.stop()
    restarted=ForwardServer(directory,clock)
    try:
        state=restarted.client.get(path).json()
        assert state['samples']==original['samples'] and state['method_deadline']==original['method_deadline']
        assert restarted.client.post(path+'/replay').json()['matches_original'] is True
    finally:restarted.stop()
