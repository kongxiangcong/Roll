"""Owned finite three-process/UI/HTTP acceptance. No original DB connection."""
from pathlib import Path
import json,os,socket,subprocess,sys,time,hashlib,ctypes
import httpx
TREE=Path(__file__).resolve().parents[5]
OID='076e67d53e4e550d4027b4f76909fb693c952957'
assert os.environ.get('ROLL_FINAL31_BEHAVIOR_RELEASE')=='1'
subprocess.run(['git','merge-base','--is-ancestor',OID,'HEAD'],cwd=TREE,check=True)
run=time.strftime('%Y%m%d-%H%M%S')
ROOT=TREE/'.roll-data'/('f31-live-'+run)
OUT=TREE/'.scratch/roll-p0/evidence/31-final/runs'/('live-'+run)
assert not ROOT.exists() and not OUT.exists()
ROOT.mkdir(parents=True);OUT.mkdir(parents=True)
env={**os.environ,'ROLL_ENV':'test','PYTHONPATH':';'.join(str(TREE/'backend'/p) for p in ['src','tests/support','tests/application']),'PYTHONDONTWRITEBYTECODE':'1'}
for key in ['ROLL_ENV_FILE','ROLL_CODEX_AUTH_FILE','ROLL_DEEPSEEK_API_KEY_FILE','DEEPSEEK_API_KEY','OPENAI_API_KEY','FUYAO_API_KEY','ROLL_TEST_CRASH_POINT','ROLL_TEST_BOOTSTRAP_FAULT','ROLL_TECHNICAL_REVIEW_METHOD_FILE','ROLL_CAPABILITY_METHOD_FILE']:
    env.pop(key,None)
NODE=subprocess.check_output(['where.exe','node'],text=True).splitlines()[0]
receipt={'owner':'final31','source_root':str(TREE),'source_oid':subprocess.check_output(['git','rev-parse','HEAD'],cwd=TREE,text=True).strip(),'accepted_fix_oid':OID,'namespace':'METHOD_ENGINEERING','system_usable':False,'original_sqlite_connections':0,'status':'RUNNING','runtime_union_roots':[str(ROOT)],'processes':[],'checks':{}}
children=[]
def cim(pid):
    query=f"Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}' | Select-Object ProcessId,ParentProcessId,CreationDate,ExecutablePath,CommandLine | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell','-NoProfile','-Command',query],capture_output=True,text=True,check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None
def descendants(pid):
    result=[]
    frontier=[pid]
    for _ in range(4):
        next_pids=[]
        for owner in frontier:
            value=cim(owner)
            if value:result.append(value)
            query=f"@(Get-CimInstance Win32_Process -Filter 'ParentProcessId={int(owner)}' | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress"
            raw=subprocess.check_output(['powershell','-NoProfile','-Command',query],text=True).strip()
            if raw:
                values=json.loads(raw);next_pids.extend(values if isinstance(values,list) else [values])
        frontier=next_pids
        if not frontier:break
    return result
def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def launch(role,args,cwd,extra=None):
    log=(OUT/(role+'.log')).open('w',encoding='utf-8')
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    child=subprocess.Popen(args,cwd=cwd,env={**env,**(extra or {})},stdout=log,stderr=subprocess.STDOUT,startupinfo=startup,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NEW_CONSOLE)
    item={'role':role,'launcher_pid':child.pid,'argv':args,'cwd':str(cwd)}
    receipt['processes'].append(item);children.append((child,log,item));return child,item
def wait(client,path,predicate):
    for _ in range(400):
        try:
            response=client.get(path);response.raise_for_status();value=response.json()
            if predicate(value):return value
        except (httpx.HTTPError,ValueError):pass
        time.sleep(.1)
    raise AssertionError('PUBLIC_HEALTH_TIMEOUT '+path)
def post(client,path,body):
    response=client.post(path,json=body);response.raise_for_status();return response.json()
def identify(item):
    item['cim_at_start']=descendants(item['launcher_pid']);assert item['cim_at_start']
def verify_owner(item):
    for row in item['cim_at_start']:
        value=cim(row['ProcessId'])
        if value:assert value['CreationDate']==row['CreationDate'] and value['ExecutablePath']==row['ExecutablePath']
def graceful(item):
    verify_owner(item)
    owner=item['cim_at_start'][-1]['ProcessId']
    sender="""import ctypes,sys,time
k=ctypes.windll.kernel32
k.FreeConsole()
assert k.AttachConsole(int(sys.argv[1]))
h=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_uint)(lambda event:True)
assert k.SetConsoleCtrlHandler(h,True)
assert k.GenerateConsoleCtrlEvent(1,0)
time.sleep(.2)
"""
    subprocess.run([sys.executable,'-B','-c',sender,str(owner)],check=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=10)
def stop(child,item):
    if child.poll() is None:
        graceful(item)
        try:child.wait(timeout=20);item['stop']='CTRL_BREAK_NORMAL'
        except subprocess.TimeoutExpired:
            verify_owner(item)
            subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],check=True,capture_output=True)
            child.wait(timeout=10);item['stop']='FORCED_AFTER_TIMEOUT'
    item['exit_code']=child.returncode
    item['cim_after_stop']=[cim(r['ProcessId']) for r in item.get('cim_at_start',[])]
    assert all(r is None for r in item['cim_after_stop'])
client=None
try:
    data=ROOT/'runtime';api_port,ui_port=port(),port()
    api_url=f'http://127.0.0.1:{api_port}';ui_url=f'http://127.0.0.1:{ui_port}'
    api,api_item=launch('api',[sys.executable,'-B','-X','utf8','-m','uvicorn','roll.app:create_app','--factory','--host','127.0.0.1','--port',str(api_port)],TREE/'backend',{'ROLL_DATA_DIR':str(data),'ROLL_RUNTIME_ROLE':'API'})
    client=httpx.Client(base_url=api_url,timeout=15,trust_env=False)
    receipt['api_health']=wait(client,'/api/health',lambda v:v['status']=='ok');identify(api_item)
    assert receipt['api_health']['runtime_role']=='API'
    assert client.get('/api/reviews/health').json()['worker_state']=='STOPPED'
    worker,worker_item=launch('worker',[sys.executable,'-B','-m','roll.worker'],TREE/'backend',{'ROLL_DATA_DIR':str(data),'ROLL_RUNTIME_ROLE':'WORKER'})
    receipt['worker_health']=wait(client,'/api/reviews/health',lambda v:v['worker_state']=='RUNNING');identify(worker_item)
    owner=receipt['worker_health']['worker']['host_owner'];assert owner['pid'] in [r['ProcessId'] for r in worker_item['cim_at_start']]
    duplicate,duplicate_item=launch('worker-duplicate',[sys.executable,'-B','-m','roll.worker'],TREE/'backend',{'ROLL_DATA_DIR':str(data),'ROLL_RUNTIME_ROLE':'WORKER'})
    assert duplicate.wait(timeout=30)!=0
    children[-1][1].flush();assert 'BACKGROUND_WORKER_ALREADY_RUNNING' in (OUT/'worker-duplicate.log').read_text()
    ui,ui_item=launch('ui',[NODE,str(TREE/'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port',str(ui_port),'--strictPort'],TREE/'frontend',{'ROLL_API_PORT':str(api_port)})
    for _ in range(200):
        try:
            if httpx.get(ui_url,trust_env=False).status_code==200:break
        except httpx.HTTPError:pass
        time.sleep(.1)
    else:raise AssertionError('VITE_TIMEOUT')
    identify(ui_item)
    ui_env={**env,'ROLL_FINAL31_API':api_url,'ROLL_FINAL31_UI':ui_url,'ROLL_FINAL31_UI_OUTPUT':str(OUT/'five-entry')}
    with (OUT/'five-entry.log').open('w',encoding='utf-8') as log:
        subprocess.run([NODE,str(Path(__file__).with_name('five-entry.mjs'))],cwd=TREE,env=ui_env,stdout=log,stderr=subprocess.STDOUT,check=True)
    receipt['after_browser_close']={'api':client.get('/api/health').json(),'worker':client.get('/api/reviews/health').json(),'ui_alive':ui.poll() is None}
    assert receipt['after_browser_close']['worker']['worker']['host_owner']==owner
    assert receipt['after_browser_close']['worker']['worker_state']=='RUNNING'
    verify_owner(api_item);verify_owner(worker_item);verify_owner(ui_item)
    server_receipt={**receipt,'environment':'test','api_url':api_url,'runtime':str(data),'runtime_is_new_owned_copy':True,'process_pid':api_item['cim_at_start'][-1]['ProcessId'],'process_creation_time':api_item['cim_at_start'][-1]['CreationDate']}
    server_path=OUT/'owned-server.json';server_path.write_text(json.dumps(server_receipt,indent=2)+'\n',encoding='utf-8')
    for stage in ['home','confirmation']:
        verify_owner(api_item)
        with (OUT/(stage+'-p95.log')).open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-B','-X','utf8',str(Path(__file__).with_name('http-p95.py')),'--execute','--accepted-fix-oid',OID,'--owned-server-receipt',str(server_path),'--stage',stage,'--output',str(OUT/(stage+'-p95.json'))],cwd=TREE,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    # No review task is submitted: process/lease proof is independent of acquisition.
    stop(worker,worker_item)
    receipt['after_normal_worker_stop']=wait(client,'/api/reviews/health',lambda v:v['worker_state']=='STOPPED')
    receipt['coverage']=client.get('/api/reviews/coverage').json()
    assert receipt['coverage']['sessions'][-1]['close_reason']=='NORMAL_CLOSE_NO_ALWAYS_ON_REQUIREMENT'
    backup=post(client,'/api/runtime/backups',{})
    bundle=client.get('/api/runtime/backups/'+backup['backup_id']+'/export').content
    (ROOT/'owned-backup.zip').write_bytes(bundle)
    staged=client.post('/api/runtime/restores',content=bundle,headers={'content-type':'application/zip'});assert staged.status_code==202
    stop(api,api_item)
    api2,api2_item=launch('api-restored',[sys.executable,'-B','-X','utf8','-m','uvicorn','roll.app:create_app','--factory','--host','127.0.0.1','--port',str(api_port)],TREE/'backend',{'ROLL_DATA_DIR':str(data),'ROLL_RUNTIME_ROLE':'API'})
    wait(client,'/api/health',lambda v:v['status']=='ok');identify(api2_item)
    receipt['recovery']=client.get('/api/runtime/backups/status').json()['recovery'];assert receipt['recovery']['state']=='RECOVERY_LOCK'
    assert client.post('/api/formal/evaluate',json={}).json()['detail']['code']=='RECOVERY_LOCK'
    worker2,worker2_item=launch('worker-restored',[sys.executable,'-B','-m','roll.worker'],TREE/'backend',{'ROLL_DATA_DIR':str(data),'ROLL_RUNTIME_ROLE':'WORKER'})
    wait(client,'/api/reviews/health',lambda v:v['worker_state']=='RUNNING');identify(worker2_item)
    assert client.get('/api/runtime/backups/status').json()['recovery']['state']=='RECOVERY_LOCK'
    stop(worker2,worker2_item);stop(api2,api2_item);stop(ui,ui_item)
    client.close();client=None
    # Independent report API opens only copy_donor's newly verified disposable copy.
    report_port,report_ui_port=port(),port();report_data=ROOT/'report-runtime'
    rapi,rapi_item=launch('report-api',[sys.executable,'-B','-X','utf8','-m','uvicorn','report_method_app:factory','--factory','--host','127.0.0.1','--port',str(report_port)],TREE/'backend',{'ROLL_DATA_DIR':str(report_data),'ROLL_RUNTIME_ROLE':'API'})
    client=httpx.Client(base_url=f'http://127.0.0.1:{report_port}',trust_env=False,timeout=15)
    wait(client,'/api/health',lambda v:v['status']=='ok');identify(rapi_item)
    rui,rui_item=launch('report-ui',[NODE,str(TREE/'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port',str(report_ui_port),'--strictPort'],TREE/'frontend',{'ROLL_API_PORT':str(report_port)})
    for _ in range(200):
        try:
            if httpx.get(f'http://127.0.0.1:{report_ui_port}',trust_env=False).status_code==200:break
        except httpx.HTTPError:pass
        time.sleep(.1)
    else:raise AssertionError('REPORT_VITE_TIMEOUT')
    identify(rui_item)
    report_env={**env,'ROLL_FINAL31_REPORT_UI':f'http://127.0.0.1:{report_ui_port}','ROLL_FINAL31_REPORT_OUTPUT':str(OUT/'report-browser')}
    with (OUT/'report-browser.log').open('w',encoding='utf-8') as log:
        subprocess.run([NODE,str(TREE/'frontend/node_modules/@playwright/test/cli.js'),'test','--config','playwright.final31-report.config.ts'],cwd=TREE/'frontend',env=report_env,stdout=log,stderr=subprocess.STDOUT,check=True)
    stop(rapi,rapi_item);stop(rui,rui_item)
    receipt['checks']={'five_entry':True,'three_independent_processes':True,'worker_unique_lease':True,'browser_close_keeps_services':True,'worker_normal_close':True,'recovery_lock_survives_worker_restart':True,'two_http_p95':True,'four_namespace_report_browser':True}
    receipt['status']='PASS'
except BaseException as error:
    receipt['status']='FAIL';receipt['failure']=repr(error);raise
finally:
    if client:client.close()
    for child,log,item in reversed(children):
        if child.poll() is None:
            try:
                if 'cim_at_start' not in item:identify(item)
                stop(child,item)
            except BaseException as error:item['stop_failure']=repr(error)
        log.close()
    receipt['completed_at']=time.strftime('%Y-%m-%dT%H:%M:%S')
    (OUT/'live-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':receipt['status'],'receipt':str(OUT/'live-receipt.json'),'runtime':str(ROOT)}))
