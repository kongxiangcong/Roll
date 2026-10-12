"""Finite current-day METHOD no-trade flow; only own fresh runtime, actual clock."""
from pathlib import Path
from datetime import datetime, timezone
import json,os,socket,subprocess,sys,time,ctypes
import httpx
TREE=Path(__file__).resolve().parents[5]
assert os.environ.get('ROLL_FINAL31_BEHAVIOR_RELEASE')=='1'
subprocess.run(['git','merge-base','--is-ancestor','aaf1929','HEAD'],cwd=TREE,check=True)
run=datetime.now().strftime('%Y%m%d-%H%M%S')
ROOT=TREE/'.roll-data'/('f31-flow-r02-'+run)
OUT=Path(__file__).resolve().parent/('run-'+run)
assert not ROOT.exists() and not OUT.exists()
ROOT.mkdir(parents=True);OUT.mkdir(parents=True)
env={**os.environ,'ROLL_ENV':'test','PYTHONPATH':';'.join([str(TREE/'backend/src'),str(Path(__file__).resolve().parent)]),'PYTHONDONTWRITEBYTECODE':'1'}
for key in ['ROLL_ENV_FILE','ROLL_CODEX_AUTH_FILE','ROLL_DEEPSEEK_API_KEY_FILE','DEEPSEEK_API_KEY','OPENAI_API_KEY','FUYAO_API_KEY','ROLL_TEST_CRASH_POINT','ROLL_TEST_BOOTSTRAP_FAULT','ROLL_TECHNICAL_REVIEW_METHOD_FILE','ROLL_CAPABILITY_METHOD_FILE']:
    env.pop(key,None)
NODE=subprocess.check_output(['where.exe','node'],text=True).splitlines()[0]
receipt={'owner':'final31-flow-r02','source_root':str(TREE),'source_oid':subprocess.check_output(['git','rev-parse','HEAD'],cwd=TREE,text=True).strip(),'namespace':'METHOD_ENGINEERING','system_usable':False,'original_sqlite_connections':0,'runtime_union_roots':[str(ROOT)],'processes':[],'clock_modified':False,'started_at':datetime.now(timezone.utc).isoformat(),'local_started_at':datetime.now().astimezone().isoformat(),'status':'RUNNING'}
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
    api_port,ui_port=port(),port();api_url=f'http://127.0.0.1:{api_port}';ui_url=f'http://127.0.0.1:{ui_port}'
    api,api_item=launch('api-method-in-process',[sys.executable,'-B','-X','utf8','-m','uvicorn','offline_app:factory','--factory','--host','127.0.0.1','--port',str(api_port)],TREE/'backend',{'ROLL_DATA_DIR':str(ROOT/'runtime'),'ROLL_RUNTIME_ROLE':'IN_PROCESS'})
    client=httpx.Client(base_url=api_url,timeout=15,trust_env=False)
    receipt['api_health']=wait(client,'/api/health',lambda v:v['status']=='ok');identify(api_item)
    receipt['initial_summary']=wait(client,'/api/reviews/summary',lambda v:v['health']['worker_state']=='RUNNING')
    ui,ui_item=launch('ui',[NODE,str(TREE/'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port',str(ui_port),'--strictPort'],TREE/'frontend',{'ROLL_API_PORT':str(api_port)})
    for _ in range(200):
        try:
            if httpx.get(ui_url,trust_env=False).status_code==200:break
        except httpx.HTTPError:pass
        time.sleep(.1)
    else:raise AssertionError('VITE_TIMEOUT')
    identify(ui_item)
    browser_env={**env,'ROLL_FINAL31_API':api_url,'ROLL_FINAL31_UI':ui_url,'ROLL_FINAL31_UI_OUTPUT':str(OUT/'browser')}
    with (OUT/'browser.log').open('w',encoding='utf-8') as log:
        subprocess.run([NODE,str(Path(__file__).with_name('no-trade.mjs'))],cwd=TREE,env=browser_env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    receipt['browser']=json.loads((OUT/'browser/browser-receipt.json').read_bytes())
    receipt['after_browser_close']={'api':client.get('/api/health').json(),'worker':client.get('/api/reviews/health').json(),'ui_alive':ui.poll() is None}
    assert receipt['after_browser_close']['worker']['worker_state']=='RUNNING'
    receipt['external_attempt_log_exists']=(ROOT/'forbidden-external-attempts.jsonl').exists()
    assert not receipt['external_attempt_log_exists']
    receipt['status']=receipt['browser']['status']
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
    receipt['completed_at']=datetime.now(timezone.utc).isoformat()
    receipt['local_completed_at']=datetime.now().astimezone().isoformat()
    (OUT/'flow-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'status':receipt['status'],'receipt':str(OUT/'flow-receipt.json'),'runtime':str(ROOT)}))
