"""Real process interruption at source raw/snapshot boundaries; inputs stay METHOD."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import httpx
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app


class Server:
    def __init__(self,directory,fault=None):
        backend=Path(__file__).resolve().parents[2]
        with socket.socket() as port_socket:
            port_socket.bind(('127.0.0.1',0));port=port_socket.getsockname()[1]
        env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA'}}
        env.update(ROLL_ENV='test',ROLL_DATA_DIR=str(directory),ROLL_POST_CLOSE_METHOD_CLOCK='2026-10-12T15:06:00+08:00',
            PYTHONPATH=str(backend/'src')+os.pathsep+str(backend/'tests/support'),PYTHONDONTWRITEBYTECODE='1')
        if fault:env['ROLL_TEST_CRASH_POINT']=fault
        self.log=(directory.parent/('source-process-'+str(port)+'.log')).open('wb')
        self.process=subprocess.Popen([sys.executable,'-B','-X','utf8','-m','uvicorn','post_close_method_app:factory',
            '--factory','--host','127.0.0.1','--port',str(port)],cwd=backend,env=env,stdout=self.log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.client=httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=20)
        for _ in range(200):
            if self.process.poll() is not None:break
            try:
                if self.client.get('/api/health').status_code==200:return
            except httpx.TransportError:pass
            time.sleep(.05)
        self.close();raise AssertionError('post-close METHOD child failed to start')

    def close(self):
        if self.process.poll() is None:self.process.kill();self.process.wait(timeout=10)
        self.client.close();self.log.close()


@pytest.mark.parametrize('fault',['post_close_after_raw','post_close_before_snapshot_commit'])
def test_source_crash_retains_original_without_normalized_version_or_automatic_retry(tmp_path,monkeypatch,fault):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'application'))
    from test_post_close_packet import setup
    directory=tmp_path/'data'
    monkeypatch.setattr('roll.research.prospective.now',lambda:'2026-10-12T15:06:00+08:00')
    with TestClient(create_app(directory)) as client:pid=setup(client)
    server=Server(directory,fault)
    path='/api/research/collections/'+pid+'/post-close/check'
    try:
        try:server.client.post(path,json={'basis':'METHOD real process fault'})
        except httpx.TransportError:pass
        assert server.process.wait(timeout=20)==86
    finally:server.close()
    recovered=Server(directory)
    try:
        job=recovered.client.post(path,json={'basis':'recovery must retain interruption'}).json()
        assert job['state']=='INTERRUPTED' and job['gaps']==['PROCESS_STOPPED_BEFORE_SOURCE_JOB_COMPLETION']
        assert job['actual_forward_start'] is False
        batches=recovered.client.get('/api/research/collections/'+pid+'/batches').json()
        assert len(batches)==1 and batches[0]['status']=='INTERRUPTED' and batches[0]['fact_count']==0
        asof=recovered.client.get('/api/research/collections/'+pid+'/as-of',params={'cutoff':'2026-10-12T15:06:00+08:00'}).json()
        assert asof['versions']==[] and asof['network_calls']==0
        assert list((directory/'raw').glob('*.raw'))
        assert recovered.client.get('/api/research/collections/'+pid+'/readiness').json()['real_recorded_sessions']==0
    finally:recovered.close()
