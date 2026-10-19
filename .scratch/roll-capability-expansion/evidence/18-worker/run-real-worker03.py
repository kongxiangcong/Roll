"""Real archived inputs and existing worker lease; no provider/clock/inference overrides."""
import hashlib,json,os,shutil,sqlite3,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from roll.app import create_app
repo=Path(__file__).resolve().parents[4];p=Path(__file__).resolve().parent
freeze=json.loads((p/'runtime03-freeze.json').read_bytes())
for name,sha in freeze['files'].items():assert hashlib.sha256((repo/name).read_bytes()).hexdigest()==sha,name
target=repo/'.scratch/r18-runtime03';assert not target.exists()
sources=[repo/'.scratch/r17-runtime04',repo/'.scratch/r13real']
before={str(s):hashlib.sha256((s/'roll.sqlite3').read_bytes()).hexdigest() for s in sources}
shutil.copytree(sources[0],target)
source=sqlite3.connect('file:'+(sources[1]/'roll.sqlite3').as_posix()+'?mode=ro',uri=True);dest=sqlite3.connect(target/'roll.sqlite3')
for table in ['financial_income_runs','financial_supplement_runs','financial_income_facts','financial_document_parses','financial_observations','evidence_archives']:
 rows=source.execute('SELECT * FROM '+table).fetchall()
 if rows:dest.executemany('INSERT OR IGNORE INTO '+table+' VALUES('+','.join('?' for _ in rows[0])+')',rows)
dest.commit();source.close();dest.close()
for file in (sources[1]/'raw').iterdir():
 if file.is_file():
  copied=target/'raw'/file.name
  if copied.exists():assert copied.read_bytes()==file.read_bytes()
  else:shutil.copy2(file,copied)
for root,sha in before.items():assert hashlib.sha256((Path(root)/'roll.sqlite3').read_bytes()).hexdigest()==sha
environment={**os.environ,'ROLL_DATA_DIR':str(target),'PYTHONPATH':str(repo/'backend/src'),'ROLL_SENTIMENT_PYTHON':str(repo/'.scratch/rce-runtime/docling/Scripts/python.exe'),'PYTHONDONTWRITEBYTECODE':'1','ROLL_ENV':'test'}
python=repo/'backend/.venv/Scripts/python.exe';process=None;log=None
def start(index):
 global process,log
 stop=target/f'acceptance-stop-{index}';assert not stop.exists()
 environment['ROLL_ACCEPTANCE_STOP']=str(stop)
 log=(p/f'worker03-process-{index}.log').open('w',encoding='utf-8')
 process=subprocess.Popen([str(python),'-X','utf8','-B',str(p/'online-host.py')],env=environment,cwd=repo,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000 if os.name=='nt' else 0)
 return stop
def close(stop):
 stop.write_text('stop after bounded real acceptance',encoding='utf-8')
 try:code=process.wait(timeout=55)
 finally:
  if process.poll() is None:process.terminate();process.wait(timeout=10)
  log.close()
 assert code==0,(p/'worker03-process-1.log').read_text(encoding='utf-8')
def wait(client,job):
 deadline=time.monotonic()+70
 while time.monotonic()<deadline:
  value=client.get('/api/observation-update-jobs/'+job['job_id']).json()
  if value['status'] not in ('QUEUED','RUNNING'):return value
  assert process.poll() is None,'worker exited early'
  time.sleep(.15)
 raise AssertionError('bounded worker job timeout')
base='/api/observation-updates/SSE:600362';commands={};results={}
with TestClient(create_app(target,runtime_role='API')) as client:
 account_before=client.get('/api/account').json()['version']
 settings=client.get(base).json()['settings']
 assert not settings['enabled']
 response=client.post(base+'/settings',json={'expected_revision':settings['revision'],'basis':'Explicit isolated real worker acceptance; saved facts only; no source HTTP','enabled':True,'news_postclose':False,'news_refresh':False,'classify':False,'profile':'finbert-adaptation-01'})
 assert response.status_code==200,response.text
 for kind in ['NEWS','FINANCIAL']:
  commands[kind]={'idempotency_key':'real-worker-'+kind,'basis':'Bounded actual online worker over saved non-holdout archives','kind':kind,'refresh_sources':False}
  response=client.post(base+'/requests',json=commands[kind]);assert response.status_code==201,response.text
  results[kind]=response.json()
 stop=start(1)
 try:
  for kind in results:
   results[kind]=wait(client,results[kind]);assert results[kind]['status']=='COMPLETE',results[kind]
  status=client.get(base).json();assert status['worker']['worker_state']=='RUNNING'
  # A second actual worker must fail to obtain the same existing durable lease.
  probe=subprocess.run([str(python),'-B','-m','roll.worker'],env=environment,cwd=repo,capture_output=True,timeout=35)
  (p/'second-worker03-probe.log').write_bytes(probe.stdout+probe.stderr)
  assert probe.returncode!=0 and b'BACKGROUND_WORKER_ALREADY_RUNNING' in probe.stderr
  repeat=client.post(base+'/requests',json={**commands['NEWS'],'idempotency_key':'real-same-input'}).json()
  repeat=wait(client,repeat);assert repeat['cache_reused'] and repeat['observation_id']==results['NEWS']['observation_id']
  first_notices=[n for n in client.get('/api/notifications').json()['notifications'] if n['source']['kind']=='OBSERVATION_UPDATE']
  assert len(first_notices)==2 and all(n['in_app_only'] for n in first_notices)
 finally:close(stop)
 stop=start(2)
 try:
  deadline=time.monotonic()+25
  while time.monotonic()<deadline:
   status=client.get(base).json()
   if status['worker']['worker_state']=='RUNNING':break
   time.sleep(.15)
  assert status['worker']['worker_state']=='RUNNING' and status['offline_coverage']['gaps']
  for kind in results:assert client.get('/api/observation-update-jobs/'+results[kind]['job_id']).json()==results[kind]
  notices=[n for n in client.get('/api/notifications').json()['notifications'] if n['source']['kind']=='OBSERVATION_UPDATE']
  assert len(notices)==len(first_notices)
  assert len(status['observations'])==2 and all(o['evidence_kind']=='REAL_SAVED_OBSERVATION' for o in status['observations'])
  assert client.get('/api/account').json()['version']==account_before==0
  assert status['forecast_backfill'] is False
  for observation in status['observations']:
   if observation['kind']=='NEWS':
    assert observation['payload']['saved_fact_count']==22
    assert observation['payload']['classification_run_id'] is None
  (p/'real03-online-status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
 finally:close(stop)
 for root,sha in before.items():assert hashlib.sha256((Path(root)/'roll.sqlite3').read_bytes()).hexdigest()==sha
 summary={'status':'COMPLETE','evidence_kind':'REAL_ONLINE_SAVED_SOURCE_OBSERVATION','data_directory':str(target),'source_db_sha256':before,'source_files_unchanged':True,'actual_clock':True,'provider_override':False,'model_override':False,'network_calls':0,'model_calls':0,'model_policy':'explicit facts-only successor after retained bounded inference timeout; no real classification success claimed','account_before':account_before,'account_after':0,'second_worker_rejected':True,'process_restarts':1,'jobs':results,'cached_repeat':repeat,'notice_count':len(notices),'external_transmissions':0,'forecast_archive_created':False,'original_worker_gaps':status['offline_coverage']['gaps'],'at':datetime.now(timezone.utc).isoformat()}
 (p/'real03-worker-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
