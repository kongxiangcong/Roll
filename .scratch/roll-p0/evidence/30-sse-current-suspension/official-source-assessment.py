"""One real anonymous bounded SSE receipt in a fresh isolated API-only directory."""
import hashlib
import json
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app

repo=Path(__file__).resolve().parents[4]
directory=repo/'.scratch/t30s-live'
assert not directory.exists(),'Actual query budget cannot be retried using this script'
app=create_app(directory,runtime_role='API')
with TestClient(app) as client:
 plan=client.post('/api/research/collections',json={'instrument':'SSE:600362',
  'basis':'Isolated anonymous current source assessment; no account setup or real forward'}).json()
 base='/api/research/collections/'+plan['plan_id']
 response=client.post(base+'/sse-suspension',json={'basis':'Authorized fifth slice single actual anonymous official assessment, max two pages'})
 assert response.status_code==201,response.text
 receipt=response.json()
 assert receipt['network_calls']<=2 and receipt['evidence_kind']=='REAL_SOURCE_ASSESSMENT'
 assert not receipt['system_usable'] and not receipt['actual_forward_start'] and receipt['forward_started_at'] is None
 assert not receipt['no_event_authority'] and not receipt['complete_status_verified']
 assert client.get(base+'/sse-suspension-receipts').json()==[receipt]
 assert client.get('/api/account').json()['version']==0
 proof=Path(__file__).with_name('runtime')/'source-assessment';proof.mkdir(parents=True,exist_ok=True)
 for page in receipt['pages']:
  raw=client.get('/api/data/archives/'+page['archive']['sha256']).content
  assert hashlib.sha256(raw).hexdigest()==page['archive']['sha256']
  (proof/(page['archive']['sha256']+'.raw')).write_bytes(raw)
 (proof/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 summary={k:receipt[k] for k in ['receipt_id','plan_id','query_date','started_at','finished_at','normalized_known_at',
  'network_calls','request_budget_pages','evidence_kind','status','errors','returned_count','declared_total','reported_page_count','gaps']}
 summary.update(isolated_directory=str(directory),runtime_role='API',account_version=0,
  system_usable=False,actual_forward_start=False,capability='NOT_GRANTED',queries_other_than_fixed_endpoint=0)
 Path(__file__).with_name('official-source-assessment.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps(summary,ensure_ascii=False))
assert not app.state.reviews.thread
