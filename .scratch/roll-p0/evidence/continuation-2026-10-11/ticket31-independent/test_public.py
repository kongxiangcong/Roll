"""Independent METHOD public-API composition, real SQLite and OS worker."""
import os,sys,json,time,signal,subprocess
from pathlib import Path
import pytest,httpx
from fastapi.testclient import TestClient
SCOPE=Path(__file__).resolve().parent
ROOT=SCOPE.parents[4]
CHILD=Path('C:/Users/72449/.codex/worktrees/ticket31-delivery/Roll')
sys.path[:0]=[str(CHILD/'backend/src'),str(CHILD/'backend/tests/application')]
from roll.app import create_app
from test_post_close_packet import setup

def receipt(name,value):
    (SCOPE/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')

def test_role_precedence_and_original_post_close_archive_survive_reopen(tmp_path,monkeypatch):
    monkeypatch.setenv('ROLL_RUNTIME_ROLE','WORKER')
    clock='2026-10-12T15:06:00+08:00'
    for module in ['roll.research.prospective','roll.market.post_close_packet','roll.market.evidence']:
        monkeypatch.setattr(module+'.now',lambda:clock)
    calls=[]
    raw=json.dumps({'date':20261012,'time':150005,'list':[['600362','METHOD',100,101,99,100,1234,123400,100]]}).encode()
    def supplier(request):
        calls.append(str(request.url));return httpx.Response(200,content=raw)
    app=create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')
    with TestClient(app) as api:
        assert api.get('/api/health').json()['runtime_role']=='API'
        plan=setup(api);account=api.get('/api/account').json()
        jobpath='/api/research/collections/'+plan+'/post-close/check'
        response=api.post(jobpath,json={'basis':'independent METHOD original'})
        assert response.status_code==201,response.text
        job=response.json();assert job['state']=='RECORDED' and not job['actual_forward_start']
        batches=api.get('/api/research/collections/'+plan+'/batches').json()
        assert len(batches)==1 and len(calls)==1
        queued=api.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','refresh_missing':False}).json()
        recovered=api.post('/api/reviews/recover').json()
        for task in [queued,recovered]:assert api.get('/api/reviews/tasks/'+task['task_id']).json()['status']=='QUEUED'
        assert api.get('/api/reviews/coverage').json()['sessions']==[]
        assert app.state.reviews.thread is None and app.state.backups.thread is None
    # Explicit API still wins over inherited WORKER; no supplier call on restart/replay.
    with TestClient(create_app(tmp_path,market_transport=httpx.MockTransport(supplier),runtime_role='API')) as api:
        assert api.post(jobpath,json={'basis':'reopened bounded check'}).json()==job
        assert api.get('/api/research/collections/'+plan+'/batches').json()==batches
        assert api.get('/api/account').json()==account and len(calls)==1
        assert api.get('/api/reviews/health').json()['worker_state']=='STOPPED'
    receipt('source-role-results',{'status':'PASS','explicit_API_over_environment_WORKER':True,'scheduled_backup_thread_API':None,'worker_sessions_API':0,'bounded_source_reads':1,'same_job_and_batch_after_reopen':True,'actual_forward_start':False,'real_account_changes':0,'source_kind':'METHOD MockTransport','external_HTTP':0})

def wait(query,predicate,process):
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        result=query()
        if predicate(result):return result
        assert process.poll() is None,'owned worker stopped before public condition'
        time.sleep(.05)
    raise AssertionError('public worker condition timed out')

def test_actual_OS_worker_survives_normal_API_close_and_processes_same_durable_id(tmp_path,monkeypatch):
    directory=tmp_path/'runtime';empty=tmp_path/'empty.env';empty.write_text('')
    monkeypatch.setenv('ROLL_ENV_FILE',str(empty))
    monkeypatch.setenv('ROLL_RUNTIME_ROLE','WORKER')
    client=TestClient(create_app(directory,runtime_role='API'));client.__enter__()
    first=client.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','refresh_missing':False}).json()
    assert client.get('/api/reviews/tasks/'+first['task_id']).json()['status']=='QUEUED'
    env={k:v for k,v in os.environ.items() if not k.startswith('ROLL_')}
    env.update(ROLL_ENV='test',ROLL_ENV_FILE=str(empty),ROLL_DATA_DIR=str(directory),PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(CHILD/'backend/src'))
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    log=(tmp_path/'worker.log').open('w',encoding='utf-8')
    process=subprocess.Popen([sys.executable,'-B','-m','roll.worker'],cwd=ROOT/'backend',env=env,stdout=log,stderr=subprocess.STDOUT,startupinfo=startup,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NEW_CONSOLE)
    clients=[client];owner=None
    try:
        health=wait(lambda:client.get('/api/reviews/health').json(),lambda v:v['worker_state']=='RUNNING',process)
        owner=health['worker']['host_owner'];assert owner['pid']!=os.getpid()
        completed=wait(lambda:client.get('/api/reviews/tasks/'+first['task_id']).json(),lambda v:v['result'] is not None,process)
        assert completed['attempts']==1 and completed['result']['forecast'] is None and not completed['result']['forward_sample_created']
        account=client.get('/api/account').json()
        client.__exit__(None,None,None);clients.remove(client)
        # Actual worker is independent of the normally closed API lifecycle.
        reopened=TestClient(create_app(directory,runtime_role='API'));reopened.__enter__();clients.append(reopened)
        assert reopened.get('/api/reviews/health').json()['worker']['host_owner']==owner
        assert reopened.get('/api/reviews/tasks/'+first['task_id']).json()==completed
        second=reopened.post('/api/reviews/tasks',json={'mode':'ON_DEMAND','refresh_missing':False}).json()
        result=wait(lambda:reopened.get('/api/reviews/tasks/'+second['task_id']).json(),lambda v:v['result'] is not None,process)
        assert result['task_id']==second['task_id'] and result['attempts']==1
        assert result['result']['forecast'] is None and not result['result']['forward_sample_created']
        assert reopened.get('/api/account').json()==account
        # Private hidden console Ctrl+Break reaches only this exact owned worker.
        sender="""import ctypes,sys,time
k=ctypes.windll.kernel32;k.FreeConsole();assert k.AttachConsole(int(sys.argv[1]))
handler=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_uint)(lambda event:True)
assert k.SetConsoleCtrlHandler(handler,True);assert k.GenerateConsoleCtrlEvent(1,0);time.sleep(.2)
"""
        subprocess.run([sys.executable,'-B','-c',sender,str(owner['pid'])],check=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
        assert process.wait(timeout=25)==0
        assert reopened.get('/api/reviews/health').json()['worker_state']=='STOPPED'
        coverage=reopened.get('/api/reviews/coverage').json()
        assert coverage['sessions'][-1]['close_reason']=='NORMAL_CLOSE_NO_ALWAYS_ON_REQUIREMENT'
        assert not coverage['forward_predictions_reconstructed'] and not coverage['expired_opportunities_sent']
        receipt('OS-worker-results',{'status':'PASS','launcher_pid':process.pid,'worker_owner':owner,'worker_actual_exit':0,'normal_API_close_preserves_independent_worker':True,'first_task_id':first['task_id'],'second_task_id':second['task_id'],'attempts_each':1,'old_published_result_unchanged':True,'account_unchanged':True,'forecast':None,'forward_sample_created':False,'close_reason':coverage['sessions'][-1]['close_reason'],'external_HTTP':0,'provider_calls':0,'training_runs':0})
    finally:
        for c in clients:c.__exit__(None,None,None)
        if process.poll() is None:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
            process.wait(timeout=10)
        log.close()
