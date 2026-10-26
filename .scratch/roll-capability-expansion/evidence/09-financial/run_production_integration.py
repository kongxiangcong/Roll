"""One separately user-approved production integration attempt; no retry."""
import argparse
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app

out=Path(__file__).parent;root=out.parents[3]
parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
if not args.execute:raise SystemExit('Prepared only. Requires separate user-approved execution.')
plan=json.loads((out/'integration-plan.json').read_text(encoding='utf-8'));assert plan['status']=='APPROVED_ONCE';profile=Path(plan['data_directory'])
assert not profile.exists(),'No repeat or existing profile reuse'
receipt=out/'integration-attempt.json'
with receipt.open('x',encoding='utf-8') as file:json.dump({'status':'RUNNING','started_at':datetime.now(timezone.utc).isoformat(),'plan_sha256':hashlib.sha256((out/'integration-plan.json').read_bytes()).hexdigest()},file)
os.environ['ROLL_ENV']='test';os.environ['ROLL_AKSHARE_PYTHON']=str(root/'.scratch/rce-runtime/akshare/Scripts/python.exe')
result={'status':'CLOSED_NO_RETRY','succeeded':False,'profile':str(profile)}
try:
    with TestClient(create_app(profile,runtime_role='API')) as client:
        assert client.app.state.financial.worker is None
        account=client.get('/api/account').json()
        market=client.get('/api/market/list').json()
        assert client.post('/api/market/watch',json={'operation':'ADD','instrument':plan['instrument'],'expected_list_version':market['version']}).status_code==200
        policy=next(p for p in client.get('/api/research/collection-sources').json() if p['id']=='akshare-financial-em')
        assert client.post('/api/research/collection-sources/akshare-financial-em/policy',json={'enabled':True,'expected_revision':policy['revision'],'basis':'Separately approved single isolated production-chain acceptance; no automatic retry'}).status_code==200
        base='/api/market/financial/'+plan['instrument']+'/income'
        response=client.post(base+'/collect',json={'idempotency_key':'production-integration-once','basis':'Separately approved one-shot production SDK chain, bounded 8HTTP/18s/8MiB, no retry'})
        (out/'integration-response.json').write_bytes(response.content)
        assert response.status_code==201,response.text
        run=response.json();result['run_id']=run['run_id'];result['run_status']=run['status'];result['network_calls']=run['network_calls']
        assert run['evidence_kind']=='REAL_ACQUISITION'
        assert run['status']=='COMPLETE' and 0<run['network_calls']<=8
        assert len(run['facts'])==5
        for original in run['originals']:
            body=client.get('/api/data/archives/'+original['sha256']).content
            assert hashlib.sha256(body).hexdigest()==original['sha256'].lower()
        assert len(client.get(base).json()['facts'])==5
        assert client.get('/api/account').json()==account
        result.update(succeeded=True,account_unchanged=True,originals_verified=len(run['originals']),facts=5)
except BaseException as error:
    result['error']=type(error).__name__+': '+str(error)[:1000]
    raise
finally:
    result['closed_at']=datetime.now(timezone.utc).isoformat()
    receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
