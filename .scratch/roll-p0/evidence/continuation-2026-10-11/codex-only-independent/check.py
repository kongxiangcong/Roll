"""Independent current-scope guards; METHOD SQLite only, no provider runtime."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import faulthandler

ROOT = Path(__file__).resolve().parents[5]
SCOPE = Path(__file__).resolve().parent
CHILD = ROOT / '.scratch/worktrees/codex-scope'
OWN = CHILD / '.scratch/roll-p0/evidence/continuation-2026-10-11/codex-only-scope'
RUNTIME = ROOT / '.roll-data/implementation-evidence/codex-only-independent-elevated'
faulthandler.dump_traceback_later(90,repeat=True)
OID = 'c3198e0f960024df2ddd9dfaf66a0b730f996203'

def write(name, value):
    (SCOPE/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args): return subprocess.check_output(['git','-C',str(CHILD),*args],text=True).strip()
def extended(p): return Path('\\\\?\\'+str(p.resolve()))

assert git('rev-parse','HEAD') == OID
assert not git('status','--porcelain','--untracked-files=no')
sources=json.loads((OWN/'source-final.json').read_text(encoding='utf-8'))
assert len(sources)==21
for i,item in enumerate(sources):
    for base in ([CHILD,ROOT] if i<15 else [CHILD]):
        p=base/item['path']
        assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],str(p)
manifest=json.loads((OWN/'runtime-preservation.json').read_text(encoding='utf-8'))
assert manifest['files']==1097 and manifest['bytes']==88979482 and manifest['mismatches']==0
for item in manifest['inventory']:
    for base in [CHILD/'.scratch',Path(manifest['destination'])]:
        p=extended(base/item['path'])
        assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],str(p)
write('preflight.json',{'status':'PASS','stable_oid':OID,'source_files':21,'protected_raw_sources':15,
    'preserved_files':1097,'preserved_bytes':88979482,'source_root_SHA_length_mismatches':0})
print('Preflight PASS',flush=True)

for key in ['ROLL_ENV_FILE','ROLL_CODEX_AUTH_FILE','DEEPSEEK_API_KEY','ROLL_DEEPSEEK_API_KEY_FILE',
            'ROLL_TEST_CRASH_POINT','ROLL_TEST_BOOTSTRAP_FAULT']:
    os.environ.pop(key,None)
os.environ['ROLL_ENV']='test'
sys.path.insert(0,str(CHILD/'backend/src'))
sys.path.insert(0,str(CHILD/'backend/tests/application'))
from roll.app import create_app
from roll.agents.codex_process import process_creation
from fastapi.testclient import TestClient
from test_market_directory import establish
from test_codex_evidence import request_data
import httpx

network=[]
def deny(request):
    network.append(str(request.url).split('?')[0])
    raise AssertionError('External transport forbidden')
def app(directory,**kwargs): return create_app(directory,market_transport=httpx.MockTransport(deny),**kwargs)
def refusal(client,url,body):
    r=client.post(url,json=body)
    assert r.status_code==403,r.text
    assert r.json()['detail']['code']=='BACKEND_OUTSIDE_CURRENT_SCOPE',r.text
    return {'url':url,'status':403,'code':r.json()['detail']['code']}

RUNTIME.mkdir(parents=True,exist_ok=True)
fresh=RUNTIME/'fresh/data';assert not fresh.exists()
with TestClient(app(fresh)) as c:
    print('Fresh Host entered',flush=True)
    settings=c.get('/api/agents/settings').json()
    history=c.get('/api/agents/settings/history').json()
    assert settings['backend']=='CODEX' and settings['supported_backends']==['CODEX'] and not settings['resave_required']
    refusal(c,'/api/agents/settings',{'backend':'DEEPSEEK','expected_version':999})
    assert c.get('/api/agents/settings/history').json()==history
    assert c.get('/api/data/runs').json()==[]
print('Fresh Host exited',flush=True)

legacy_dir=RUNTIME/'legacy/data';assert not legacy_dir.exists()
with TestClient(app(legacy_dir)) as c:
    establish(c,['SSE:600519']);request_id=request_data(c)
legacy={'version':4,'backend':'DEEPSEEK','saved_at':'2026-10-08T00:00:00+00:00'}
run={'run_id':'independent-legacy-running-method','request_id':request_id,'backend':'DEEPSEEK',
    'model':'historical-method','status':'RUNNING','evidence_kind':'METHOD_CASE_LEGACY_ARCHIVE',
    'started_at':'2026-10-08T00:00:00+00:00','backend_settings':legacy,
    'config_fingerprint':'historical-method-fingerprint','question':'历史配置读取','tools':[],'gaps':[],
    'host_owner':{'pid':os.getpid(),'creation_ticks':process_creation(os.getpid())}}
assert run['host_owner']['creation_ticks']
with sqlite3.connect(legacy_dir/'roll.sqlite3') as db:
    db.execute('INSERT INTO agent_settings VALUES(?,?)',(4,json.dumps(legacy)))
    db.execute('INSERT INTO retrieval_runs VALUES(?,?,?)',(run['run_id'],request_id,json.dumps(run)))
with TestClient(app(legacy_dir)) as c:
    before_history=c.get('/api/agents/settings/history').json()
    before_account=c.get('/api/account').json()
    current=c.get('/api/agents/settings').json()
    assert {k:current[k] for k in legacy}==legacy and current['resave_required'] is True
    refusals=[]
    for key in ['missing',request_id]:
        for route in ['deepseek','agent']:
            refusals.append(refusal(c,f'/api/data/requests/{key}/{route}',{'question':'current scope','retry_of':'missing'}))
    refusals.append(refusal(c,'/api/research/review-materials/missing/reviews',{'expected_material_fingerprint':'missing','retry_of':'missing'}))
    assert c.get('/api/data/runs').json()==[run]
    assert c.get('/api/agents/settings/history').json()==before_history
    assert c.get('/api/account').json()==before_account
    assert c.get('/api/data/runs/'+run['run_id']).json()==run
    cancel=c.post('/api/data/runs/'+run['run_id']+'/cancel').json()
    assert cancel=={'run_id':run['run_id'],'cancel_requested':False,'status':'RUNNING'},cancel
    assert c.get('/api/data/runs/'+run['run_id']).json()==run
    save=c.post('/api/agents/settings',json={'backend':'CODEX','expected_version':4})
    assert save.status_code==200,save.text
    saved=save.json();assert saved['backend']=='CODEX' and saved['version']==5 and saved['saved_at']
    duplicate=c.post('/api/agents/settings',json={'backend':'CODEX','expected_version':5})
    assert duplicate.status_code==200 and duplicate.json()==saved
    assert c.post('/api/agents/settings',json={'backend':'CODEX','expected_version':4}).status_code==409
    refusal(c,'/api/agents/settings',{'backend':'DEEPSEEK','expected_version':999})
    refusal(c,'/api/data/requests/missing/deepseek',{'question':'current scope'})
    after_history=c.get('/api/agents/settings/history').json()
    assert after_history==[saved,*before_history]
    assert c.get('/api/data/runs').json()==[run] and c.get('/api/account').json()==before_account
with TestClient(app(legacy_dir)) as c:
    current=c.get('/api/agents/settings').json()
    assert current['version']==5 and current['backend']=='CODEX' and not current['resave_required']
    assert c.get('/api/agents/settings/history').json()==after_history
    assert c.get('/api/data/runs/'+run['run_id']).json()==run
write('scope-results.json',{'status':'PASS','refusals':refusals,'legacy_setting_version':4,'explicit_saved_version':5,
    'idempotent_same_version':True,'stale_version_status':409,'historical_RUNNING_record_unchanged':True,
    'historical_cancel_route_status':200,'cancel_requested':False,'active_owner_fixture_only':True,
    'actual_DeepSeek_runtime_tested':False,'new_run_dispatches':0,'account_unchanged':True,'restart_history_unchanged':True})
print('Settings/history/restart PASS',flush=True)

# Reuse only our own stopped, synthetic ticket24 profile; do not open actual profiles.
source=ROOT/'.roll-data/implementation-evidence/ticket24-independent/pytest-02/test_independent_exit_scope_re0'
target=RUNTIME/'stale-capability';assert not target.exists()
copy=[]
for p in sorted(source.rglob('*')):
    if not p.is_file():continue
    assert p.name not in {'auth.json','.env'},'Never copy credentials'
    relative=p.relative_to(source);to=target/relative
    to.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,to)
    assert sha(p)==sha(to)
    copy.append({'path':relative.as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
with sqlite3.connect('file:'+str(target/'data/roll.sqlite3')+'?mode=ro',uri=True) as db:
    before={table:db.execute('SELECT id,value FROM '+table+' ORDER BY id').fetchall()
        for table in ['capability_grants','capability_proofs']}
with TestClient(app(target/'data',capability_method_file=target/'qualification.json')) as c:
    grants=c.get('/api/capabilities/grants').json();proofs=c.get('/api/capabilities/proofs').json()
    assert len(grants)==1 and grants[0]['evidence_kind']=='METHOD_ENGINEERING' and grants[0]['system_usable'] is False
    current=c.get('/api/capabilities/grants/'+grants[0]['grant_id']+'/status').json()
    assert current['state']=='RESTRICTED' and current['allowed_actions']==[],current
    assert any('DEPLOYMENT_SOURCE_CHANGED' in r or 'HOST_PROOF_SOURCE_CHANGED' in r for r in current['reasons']),current
    proof=c.get('/api/capabilities/proofs/'+grants[0]['proof_id']+'/check')
    assert proof.status_code==409,proof.text
    assert c.get('/api/capabilities/grants').json()==grants and c.get('/api/capabilities/proofs').json()==proofs
with sqlite3.connect('file:'+str(target/'data/roll.sqlite3')+'?mode=ro',uri=True) as db:
    after={table:db.execute('SELECT id,value FROM '+table+' ORDER BY id').fetchall() for table in before}
assert before==after
for item in copy:
    p=source/item['path'];assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256']
write('stale-proof-results.json',{'status':'PASS','prior_profile':'self-owned ticket24 METHOD only','copied_files':len(copy),
    'source_profile_SHA_length_mismatches':0,'state':current['state'],'reasons':current['reasons'],
    'old_grant_and_proof_rows_byte_identical':True,'proof_check_status':409,'old_fields_cleared':False,
    'grant_system_usable':False,'copy_inventory':copy})
assert network==[]
for item in sources:
    p=CHILD/item['path'];assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256']
assert git('rev-parse','HEAD')==OID and not git('status','--porcelain','--untracked-files=no')
write('results.json',{'status':'PASS','exit_code':0,'independent_scenarios':3,'stable_oid':OID,
    'preserved_files':1097,'preserved_bytes':88979482,'protected_raw_sources':15,'source_mismatches':0,
    'provider_model_calls':0,'new_review_runs':0,'new_retrieval_runs':0,'network_transport_calls':len(network),
    'fit_forecast_started':False,'actual_profiles_started':0,'SEALED_read':False,
    'historical_record_mutations':0,'qualification_claim':'METHOD scope guards only; actual NOT_GRANTED unchanged'})
print('PASS: three independent METHOD scope/history/stale-proof scenarios; no dispatch, provider, fit or actual profile')
faulthandler.cancel_dump_traceback_later()
