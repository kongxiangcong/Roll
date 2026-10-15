"""New news source default bounded acceptance, independent of closed financial budgets."""
import argparse,hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
out=Path(__file__).resolve().parent;root=out.parents[3]
parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
if not args.execute:raise SystemExit('Prepared only; --execute uses the fixed new-source plan once.')
plan=json.loads((out/'source-plan.json').read_text());profile=Path(plan['profile']);assert not profile.exists()
receipt=out/'source-attempt.json'
with receipt.open('x') as f:json.dump({'status':'RUNNING','plan_sha256':hashlib.sha256((out/'source-plan.json').read_bytes()).hexdigest()},f)
os.environ['ROLL_ENV']='test';os.environ['ROLL_AKSHARE_PYTHON']=str(root/'.scratch/rce-runtime/akshare/Scripts/python.exe');os.environ.pop('ROLL_TRAFILATURA_PYTHON',None)
result={'status':'CLOSED_NO_RETRY','succeeded':False,'full_text_verified':False}
try:
 with TestClient(create_app(profile,runtime_role='API')) as c:
  assert c.app.state.news.worker is None
  account=c.get('/api/account').json();version=c.get('/api/market/list').json()['version']
  assert c.post('/api/market/watch',json={'operation':'ADD','instrument':plan['instrument'],'expected_list_version':version}).status_code==200
  policy=next(p for p in c.get('/api/research/collection-sources').json() if p['id']==plan['source_id'])
  assert c.post('/api/research/collection-sources/'+plan['source_id']+'/policy',json={'enabled':True,'expected_revision':policy['revision'],'basis':'Explicit isolated one-shot new news source acceptance under spec ID-04; zero retry'}).status_code==200
  base='/api/market/news/'+plan['instrument'];response=c.post(base+'/collect',json={'idempotency_key':'source-once','basis':'One new-source actual SDK/list/HTML archive acceptance, 8HTTP/18s/8MiB, no retry'})
  (out/'source-response.json').write_bytes(response.content);assert response.status_code==201,response.text
  run=response.json();result.update(run_id=run['run_id'],run_status=run['status'],network_calls=run['network_calls'],facts=len(run['facts']),errors=run['errors'])
  assert run['evidence_kind']=='REAL_ACQUISITION' and run['network_calls']<=8
  for raw in run['originals']:
   body=c.get('/api/data/archives/'+raw['sha256']).content;assert hashlib.sha256(body).hexdigest()==raw['sha256']
   # Save exact received entities separately from the machine-local profile.
   directory=out/'actual-source';directory.mkdir(exist_ok=True);(directory/(raw['sha256']+'.raw')).write_bytes(body)
  result.update(succeeded=run['status'] in ('PARTIAL','COMPLETE','EMPTY'),originals_verified=len(run['originals']),bytes=sum(r['bytes'] for r in run['originals']),account_unchanged=c.get('/api/account').json()==account)
  assert result['account_unchanged'] and result['bytes']<=8388608
except BaseException as e:result['error']=type(e).__name__+': '+str(e)[:500];raise
finally:
 result['closed_at']=datetime.now(timezone.utc).isoformat();receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
