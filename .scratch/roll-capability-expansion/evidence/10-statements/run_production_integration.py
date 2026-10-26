"""One separately approved supplement acceptance. Closed09 budget is never reused."""
import argparse,hashlib,json,os,shutil
from datetime import datetime,timezone
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app

out=Path(__file__).parent;root=out.parents[3]
parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
if not args.execute:raise SystemExit('Prepared only; approval required')
plan=json.loads((out/'production-plan.json').read_text(encoding='utf-8'));assert plan['status']=='APPROVED_ONCE'
profile=Path(plan['data_directory']);donor=Path(plan['income_profile']);assert not profile.exists()
receipt=out/'production-attempt.json'
with receipt.open('x',encoding='utf-8') as file:json.dump({'status':'RUNNING','started_at':datetime.now(timezone.utc).isoformat(),'plan_sha256':hashlib.sha256((out/'production-plan.json').read_bytes()).hexdigest()},file)
result={'status':'CLOSED_NO_RETRY','succeeded':False,'profile':str(profile)}
try:
    # Closed, idle isolated profile; retain original facts and reception times, never backdate imports.
    files={str(p.relative_to(donor)):hashlib.sha256(p.read_bytes()).hexdigest() for p in donor.rglob('*') if p.is_file()}
    shutil.copytree(donor,profile)
    assert all(hashlib.sha256((profile/p).read_bytes()).hexdigest()==sha for p,sha in files.items())
    (out/'income-profile-copy.json').write_text(json.dumps(files,indent=2),encoding='utf-8')
    os.environ['ROLL_ENV']='test';os.environ['ROLL_AKSHARE_PYTHON']=str(root/'.scratch/rce-runtime/akshare/Scripts/python.exe')
    with TestClient(create_app(profile,runtime_role='API')) as client:
        assert client.app.state.financial_statements.worker is None
        account=client.get('/api/account').json();base='/api/market/financial/'+plan['instrument']
        income=client.get(base+'/income').json()['facts'];assert len(income)==5
        response=client.post(base+'/statements/collect',json={'idempotency_key':'production-supplement-once','basis':'Separately approved one shot asset/liability and cash flow, joint8HTTP18s8MiB zero retry'})
        (out/'production-response.json').write_bytes(response.content)
        assert response.status_code==201,response.text
        run=response.json();result.update(run_id=run['run_id'],run_status=run['status'],network_calls=run['network_calls'])
        assert run['status']=='COMPLETE' and run['evidence_kind']=='REAL_ACQUISITION' and 0<run['network_calls']<=8
        for original in run['originals']:
            body=client.get('/api/data/archives/'+original['sha256']).content;assert hashlib.sha256(body).hexdigest()==original['sha256'].lower()
        view=client.get(base+'/statements').json();(out/'production-query.json').write_text(json.dumps(view,ensure_ascii=False,indent=2),encoding='utf-8')
        matched=next(g for g in view['groups'] if g['report_period']=='2026-06-30' and g['status']=='MATCHED')
        assert matched['balance_check']['status']=='WITHIN_ROUNDING'
        assert client.get('/api/account').json()==account
        assert client.get(base+'/income').json()['facts']==income
        result.update(succeeded=True,account_unchanged=True,income_unchanged=True,originals_verified=len(run['originals']),facts=len(run['facts']))
except BaseException as error:
    result['error']=type(error).__name__+': '+str(error)[:1000];raise
finally:
    result['closed_at']=datetime.now(timezone.utc).isoformat();receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
