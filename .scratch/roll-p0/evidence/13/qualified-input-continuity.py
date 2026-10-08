"""Explicit METHOD source checks public valuation continuity after unavailable agents."""
from pathlib import Path
from datetime import datetime,timezone
import json
import os
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'backend/src'))
os.environ['ROLL_ENV']='test'
for key in ['ROLL_ENV_FILE','ROLL_CODEX_AUTH_FILE','DEEPSEEK_API_KEY','ROLL_DEEPSEEK_API_KEY_FILE']:
    os.environ.pop(key,None)
from fastapi.testclient import TestClient
import httpx
from roll.app import create_app

directory=ROOT/'backend/.roll-data/13-qualified-continuity-method'
assert not directory.exists(),'NEW_ISOLATED_DIRECTORY_REQUIRED'
calls=[]
def source(request):
    calls.append(str(request.url))
    return httpx.Response(200,json={'instrument':'SSE:600000','last':'12.00','upstream_at':'2026-10-07T15:00:00+08:00',
        'method_case_status':'NORMAL','basis':'13 METHOD quote for arithmetic continuity only'})

with TestClient(create_app(directory,market_transport=httpx.MockTransport(source))) as c:
    draft=c.post('/api/account/drafts',json={'kind':'BASELINE','expected_account_version':0,'payload':{
        'effective_at':'2026-10-07T00:00:00+08:00','source':'13 METHOD synthetic confirmed account',
        'cash_balance':'10000.00','broker_available':None,'broker_frozen':None,'withdrawable':None,'permission_profile':[],
        'positions':[{'instrument':'SSE:600000','quantity':'300','sellable_quantity':None,'reference_cost':None}]}}).json()
    assert c.post('/api/account/confirm',json={'draft_id':draft['draft_id'],'idempotency_key':'13-method-baseline'}).status_code==200
    request=c.post('/api/data/requests',json={'instruments':['SSE:600000'],'groups':['QUOTE'],'purpose':'OBSERVATION',
        'start_date':'2026-10-07','end_date':'2026-10-07'}).json()
    run=c.post('/api/data/requests/'+request['request_id']+'/retrieve',json={}).json();assert run['status']=='COMPLETE',run
    snapshot=c.get('/api/data/snapshots/'+run['snapshot_id']).json()
    now=datetime.now(timezone.utc).isoformat()
    command={'baseline_account_version':1,'origin_at':'2026-10-07T00:00:00+08:00','as_of':now,'known_by':now}
    first=c.post('/api/account/valuations',json=command);assert first.status_code==201,first.text
    first=first.json();assert first['facts']['net_assets']=='13600.00'
    before={p:c.get(p).json() for p in ['/api/account','/api/funding','/api/research/protocols']}
    failures=[]
    for backend in ['CODEX','DEEPSEEK']:
        current=c.get('/api/agents/settings').json()
        c.post('/api/agents/settings',json={'expected_version':current['version'],'backend':backend})
        new=c.post('/api/data/requests/'+request['request_id']+'/agent',json={'question':'No model credential; retain qualified inputs'}).json()
        import time
        end=time.monotonic()+10
        while new['status']=='RUNNING' and time.monotonic()<end:
            time.sleep(.05);new=c.get('/api/data/runs/'+new['run_id']).json()
        assert new['status']=='UNAVAILABLE',new
        failures.append(new)
        value=c.post('/api/account/valuations',json=command);assert value.status_code==201,value.text
        value=value.json()
        assert value['facts']['net_assets']=='13600.00' and value['positions']==first['positions']
        assert value['input_fingerprint']==first['input_fingerprint']
        assert value['performance']['return_percent'] is None,'UNKNOWN_BASELINE_MUST_REMAIN_UNKNOWN'
        assert value['authority']['technical_capability']=='UNGRANTED'
    assert c.get('/api/data/snapshots/'+run['snapshot_id']).json()==snapshot
    replay=c.post('/api/data/runs/'+run['run_id']+'/replay',json={}).json();assert replay['network_calls']==0
    assert len(calls)==1
    assert all(c.get(p).json()==v for p,v in before.items())
    result={'evidence_kind':'METHOD_SOURCE_PUBLIC_API_REAL_SQLITE; NOT_ACTUAL_MARKET_PRICE','source_run':run,
        'before_valuation':first,'after_valuation':value,'agent_failures':failures,'source_calls':len(calls),
        'snapshot_unchanged':True,'replay_network_calls':0,'account_funding_protocols_unchanged':True,'passed':True}
    (ROOT/'.scratch/roll-p0/evidence/13/qualified-input-continuity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':True,'net_assets':'13600.00','source_calls':1,'unavailable_backends':['CODEX','DEEPSEEK']}))
