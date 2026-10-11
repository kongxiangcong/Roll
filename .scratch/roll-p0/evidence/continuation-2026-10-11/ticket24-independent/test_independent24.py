"""Public API engineering boundaries, isolated source copy and SQLite; no actual provider."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[5]
SCOPE = Path(__file__).resolve().parent
CHILD = ROOT / '.scratch/worktrees/ticket24'
RUNTIME = ROOT / '.roll-data/implementation-evidence/ticket24-independent'
COPIED_SOURCE = RUNTIME / 'source'
# Copy setup is deliberately a separate preflight, never performed on import.
assert (COPIED_SOURCE / 'roll/app.py').is_file(), 'Run approved stable-source preflight first'
for key in ['ROLL_ENV_FILE', 'ROLL_CODEX_AUTH_FILE', 'DEEPSEEK_API_KEY', 'ROLL_DEEPSEEK_API_KEY_FILE', 'ROLL_TEST_CRASH_POINT', 'ROLL_TEST_BOOTSTRAP_FAULT']:
    os.environ.pop(key, None)
os.environ['ROLL_ENV'] = 'test'
sys.path.insert(0, str(COPIED_SOURCE))
from roll.app import create_app
import roll.app
assert Path(roll.app.__file__).resolve() == (COPIED_SOURCE / 'roll/app.py').resolve()
sys.path.insert(0, str(CHILD / 'backend/tests/support'))
sys.path.insert(0, str(CHILD / 'backend/tests/application'))
from capability_method_app import package, save_package
from test_account import baseline, submit
from test_funding import funding
from test_technical_review import WORKER, terminal
from fastapi.testclient import TestClient
import httpx
import pytest

NETWORK = []
def deny(request):
    NETWORK.append(str(request.url).split('?')[0])
    raise AssertionError('Independent METHOD external network forbidden')
def app(directory, **kwargs):
    return create_app(directory, market_transport=httpx.MockTransport(deny), **kwargs)
def write(name, value):
    (SCOPE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
def setup_account(client, permission='OPEN', sellable='300'):
    p = package()
    b = baseline()
    b['payload']['positions'] = [{'instrument':'SSE:600000','quantity':'300','sellable_quantity':sellable,'reference_cost':'10.00'}]
    b['payload']['permission_profile'][0]['status'] = permission
    assert submit(client, b, 'baseline').status_code == 200
    assert submit(client, {'kind':'ACCOUNT_DECLARATION','expected_account_version':1,'payload':{
        'effective_at':p['required_as_of'],'source':'Independent METHOD only','record_id':'declaration',
        'scope':['TRADES','ORDERS','CASH','EQUITY'],'changes':'NONE','basis':'isolated facts'}}, 'declare').status_code == 200
    assert client.post('/api/funding/confirm',json=funding()).status_code == 200
def command(p, key='independent-grant', actions=None, instrument='SSE:600000'):
    return {'material_id':p['material_id'],'review_run_id':p['review_run_id'],'expected_material_fingerprint':p['material_fingerprint'],
        'deployment_fingerprints':p['deployment_fingerprints'],'scope':{**p['scope'],'instruments':[instrument]},
        'allowed_actions':actions or ['BUY'],'expected_account_version':2,'expected_funding_version':1,
        'required_as_of':p['required_as_of'],'effective_at':p['effective_at'],'expires_at':p['expires_at'],
        'idempotency_key':key,'basis':'Independent METHOD admission boundary'}
def shrink():
    return funding(1,capital_amount='80000.00',total_exposure='40000.00',single_exposure='15000.00',cash_reserve='40000.00')

def test_multiple_scope_restart_shrink_and_proof_integrity(tmp_path):
    p=package();p['scope']['instruments']=['SSE:600000','SSE:600001'];p['current_data']['instruments']=p['scope']['instruments'][:]
    f=save_package(tmp_path/'qualification.json',p);directory=tmp_path/'data'
    with TestClient(app(directory,capability_method_file=f)) as client:
        setup_account(client)
        proposal=client.get('/api/capabilities/proposal',params={'material_id':p['material_id'],'review_run_id':p['review_run_id']})
        assert proposal.status_code==200 and proposal.json()['expected_account_version']==2
        grants=[]
        for i,action in [('SSE:600000','BUY'),('SSE:600001','WAIT')]:
            r=client.post('/api/capabilities/grants',json=command(p,key=i,actions=[action],instrument=i))
            assert r.status_code==201,r.text
            grants.append(r.json());assert r.json()['system_usable'] is False
        before=client.get('/api/capabilities/proofs').json()
        current=client.get('/api/capabilities').json()
        assert set(current['allowed_actions'])=={'BUY','WAIT'} and len(current['grant_statuses'])==2
        for g in grants:
            r=client.get('/api/capabilities/grants/'+g['grant_id']+'/status').json()
            assert r['state']=='METHOD_GRANTED' and r['grant']==g
        assert client.get('/api/capabilities/proofs').json()==before
        account=client.get('/api/account').json()
        assert client.post('/api/funding/confirm',json=shrink()).status_code==200
        assert client.get('/api/account').json()==account
        assert all('FUNDING_VERSION_CONFLICT' in s['reasons'] for s in client.get('/api/capabilities').json()['grant_statuses'])
        assert client.post('/api/formal/evaluate',json={}).status_code==403
    with TestClient(app(directory,capability_method_file=f)) as client:
        assert client.get('/api/capabilities/grants').json()==grants
        assert client.get('/api/capabilities/proofs').json()==before
        assert client.get('/api/capabilities').json()['allowed_actions']==[]
    os.environ.pop('ROLL_ENV',None)
    try:
        with pytest.raises(ValueError,match='CAPABILITY_METHOD_HOST_TEST_ONLY'):
            app(tmp_path/'production-constructor',capability_method_file=f)
        with TestClient(app(directory)) as client:
            reopened=client.get('/api/capabilities').json()
            assert reopened['allowed_actions']==[]
            assert all('EVIDENCE_UNAVAILABLE' in s['reasons'] for s in reopened['grant_statuses'])
    finally:os.environ['ROLL_ENV']='test'
    with TestClient(app(directory,capability_method_file=f)) as client:
        proof=before[0]
        (directory/proof['archive']['path']).write_bytes(b'owned METHOD corrupted proof')
        check=client.get('/api/capabilities/proofs/'+proof['proof_id']+'/check')
        assert check.status_code==409,check.text
        assert client.get('/api/capabilities/grants/'+grants[0]['grant_id']+'/status').json()['state']=='RESTRICTED'
    write('scope-restart-results.json',{'status':'PASS','evidence_kind':'METHOD_ENGINEERING','scopes':2,
        'persisted_proofs':2,'enabled_funding_shrink_restricts_both':True,'restart_retains_history':True,
        'corrupt_proof_409':True,'production_synthetic_refused':True,'actual_system_usable':False})

@pytest.mark.parametrize('permission,sellable,allowed',[('NOT_OPEN','300',True),('UNKNOWN','300',True),('UNKNOWN',None,False)])
def test_independent_exit_scope_respects_disposal_facts(tmp_path,permission,sellable,allowed):
    gates=['DATA','RULE_QUANTITY','AUTHORIZATION','STRESS_EXECUTION','ONLINE_CONSISTENCY']
    p=package();p.update(candidate_kind='RISK_POLICY',required_gates=gates,gates={k:'PASS' for k in gates},allowed_actions=['REDUCE','EXIT'])
    f=save_package(tmp_path/'qualification.json',p)
    with TestClient(app(tmp_path/'data',capability_method_file=f)) as client:
        setup_account(client,permission,sellable)
        response=client.post('/api/capabilities/grants',json=command(p,actions=['EXIT']))
        assert response.status_code==(201 if allowed else 409),response.text
        if not allowed:assert 'ACCOUNT_FACTS_NOT_RECONCILED' in response.json()['detail']['reasons']
        for action in ['BUY','ADD']:
            r=client.post('/api/capabilities/grants',json=command(p,key=action,actions=[action]))
            assert r.status_code==409 and 'RISK_POLICY_CANNOT_AUTHORIZE_NEW_RISK' in r.json()['detail']['reasons']
        assert client.post('/api/capabilities/grants',json={**command(p),'gates':{'PASS':True}}).status_code==422
    write('exit-'+permission+'-'+str(sellable)+'.json',{'status':'PASS','permission':permission,'sellable':sellable,
        'EXIT_admitted_in_METHOD':allowed,'BUY_ADD_refused':True,'system_usable':False})

def test_slow_proof_has_short_writer_and_rechecks_enabled_shrink(tmp_path):
    p={**package(),'method_reproduction_delay_ms':1500}
    f=save_package(tmp_path/'qualification.json',p)
    with TestClient(app(tmp_path/'data',capability_method_file=f)) as client:
        setup_account(client)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(client.post,'/api/capabilities/grants',json=command(p))
            for _ in range(200):
                proofs=client.get('/api/capabilities/proofs').json()
                if proofs and proofs[0]['status']=='RUNNING':break
                time.sleep(.01)
            else:raise AssertionError('Proof never entered RUNNING')
            start=time.perf_counter();r=client.post('/api/funding/confirm',json=shrink());elapsed=time.perf_counter()-start
            assert r.status_code==200 and elapsed<1.0,(r.text,elapsed)
            denied=future.result()
        assert denied.status_code==409 and 'FUNDING_VERSION_CONFLICT' in denied.json()['detail']['reasons']
        assert client.get('/api/capabilities/grants').json()==[]
    write('short-writer-results.json',{'status':'PASS','METHOD_delay_ms':1500,'concurrent_enabled_shrink_seconds':elapsed,
        'new_funding_rechecked':True,'no_real_profile_P95_measurement':True})

def test_producer_proof_restart_reuse_and_source_input_refusal(tmp_path):
    auth=tmp_path/'method-auth.json';auth.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'METHOD_CASE_ONLY'}}))
    os.environ['ROLL_CODEX_AUTH_FILE']=str(auth)
    worker=tmp_path/'fixed-local-worker.py';worker.write_text(WORKER)
    case=tmp_path/'method-review.json';case.write_text(json.dumps({'cases':[{'case_id':'independent24','gates':{'G4':'INCONCLUSIVE'},
        'checks_complete':True,'endpoint_reached':True,'observed_value':1}]}))
    directory=tmp_path/'data';reproductions=[]
    application=app(directory,codex_worker=worker,technical_review_method_file=case)
    original=application.state.technical_reviews.reproduce
    def counted(material):reproductions.append(material['material_id']);return original(material)
    application.state.technical_reviews.reproduce=counted
    with TestClient(application) as client:
        setup_account(client)
        material=client.get('/api/research/method-review-materials').json()[0]
        started=client.post('/api/research/review-materials/'+material['material_id']+'/reviews',json={'expected_material_fingerprint':material['material_fingerprint']})
        assert started.status_code==202,started.text
        review=terminal(client,started.json()['run_id']);assert review['status']=='COMPLETE'
        c={**command(package()),'material_id':material['material_id'],'review_run_id':review['run_id'],'expected_material_fingerprint':material['material_fingerprint']}
        denied=client.post('/api/capabilities/grants',json=c)
        assert denied.status_code==409 and 'QUALIFICATION_EVIDENCE_INCOMPLETE' in denied.json()['detail']['reasons']
        assert len(reproductions)==2  # Explicit review tool, then issuer proof; no grant qualification inferred.
        proofs=client.get('/api/capabilities/proofs').json();assert len(proofs)==1 and proofs[0]['status']=='VERIFIED'
        proof_id=proofs[0]['proof_id']
    resumed=app(directory,codex_worker=worker,technical_review_method_file=case)
    def never(*args):raise AssertionError('GET must reuse saved proof, not recompute mathematics')
    resumed.state.technical_reviews.reproduce=never
    with TestClient(resumed) as client:
        for _ in range(3):
            assert client.get('/api/capabilities/proofs/'+proof_id+'/check').json()['reproduction_reused'] is True
            assert client.get('/api/capabilities').json()['state']=='UNGRANTED'
            assert client.get('/api/today').json()['formal_judgment']=='DISABLED'
        assert client.get('/api/capabilities/proofs').json()==proofs
        source=COPIED_SOURCE/'roll/research/technical_review.py';raw=source.read_bytes()
        try:
            source.write_bytes(raw+b'\n# Independent owned-source stale deployment probe\n')
            stale=client.get('/api/capabilities/proofs/'+proof_id+'/check')
            assert stale.status_code==409,stale.text
        finally:source.write_bytes(raw)
        assert client.get('/api/capabilities/proofs/'+proof_id+'/check').status_code==200
        (directory/material['method_case_archive']['path']).write_bytes(b'owned METHOD original input corruption')
        corrupted=client.get('/api/capabilities/proofs/'+proof_id+'/check');assert corrupted.status_code==409,corrupted.text
        assert client.get('/api/capabilities/grants').json()==[]
        assert client.get('/api/account').json()['version']==2
    assert not NETWORK
    os.environ.pop('ROLL_CODEX_AUTH_FILE',None)
    write('producer-proof-results.json',{'status':'PASS','evidence_kind':'METHOD_CASE','local_fixed_worker':True,
        'incomplete_qualification_refused':True,'issuer_reproductions':1,'review_tool_reproductions':1,
        'restart_GET_reproduction_count':0,'original_input_corruption_409':True,'owned_source_drift_409':True,
        'saved_proof_history_unchanged':True,'provider_calls':0,'market_network_calls':0,'actual_profiles_started':0,
        'models_fitted':0,'SEALED_read':False,'real_P95_claim':False})
