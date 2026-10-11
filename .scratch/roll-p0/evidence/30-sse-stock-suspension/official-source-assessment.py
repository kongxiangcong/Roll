"""Exactly one fresh finite anonymous actual stock interval assessment, no retries."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.accounts.ledger import now
from roll.market.rules import SHANGHAI
from roll.market.sse_stock_suspension import fingerprint

repo=Path(__file__).resolve().parents[4]
prepared=json.loads(Path(__file__).with_name('finite-execution-plan.json').read_bytes())
assert prepared['parser_fingerprint']==fingerprint()
assert prepared['host_date']==datetime.fromisoformat(now()).astimezone(SHANGHAI).date().isoformat()
directory=repo/'.scratch/t30i-live'
assert not directory.exists(),'No implicit actual budget retry'
app=create_app(directory,runtime_role='API')
with TestClient(app) as client:
 plan=client.post('/api/research/collections',json={'instrument':'SSE:600362','basis':'Isolated sixth public source assessment only, no account setup'}).json()
 base='/api/research/collections/'+plan['plan_id']
 response=client.post(base+'/sse-stock-suspension',json={'basis':'Authorized new independent trade-day1 plus interval2 budget, no fallback'})
 assert response.status_code==201,response.text
 receipt=response.json()
 assert receipt['network_calls']<=3 and receipt['evidence_kind']=='REAL_SOURCE_ASSESSMENT'
 assert not receipt['system_usable'] and not receipt['no_event_authority'] and not receipt['complete_status_verified']
 assert not receipt['actual_forward_start'] and receipt['forward_started_at'] is None
 assert client.get(base+'/sse-stock-suspension-receipts').json()==[receipt]
 assert client.get('/api/account').json()['version']==0
 proof=Path(__file__).with_name('runtime')/'source-assessment';proof.mkdir(parents=True,exist_ok=True)
 pages=([receipt['trade_day_page']] if receipt['trade_day_page'] else [])+receipt['pages']
 for page in pages:
  raw=client.get('/api/data/archives/'+page['archive']['sha256']).content
  assert hashlib.sha256(raw).hexdigest()==page['archive']['sha256']
  (proof/(page['archive']['sha256']+'.raw')).write_bytes(raw)
 (proof/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 summary={k:receipt[k] for k in ['receipt_id','plan_id','host_date','started_at','finished_at','normalized_known_at',
  'network_calls','request_budget_calls','evidence_kind','status','errors','reported_before_trade_day',
  'latest_trade_day_verified','returned_count','declared_total','reported_page_count','gaps']}
 summary.update(isolated_directory=str(directory),runtime_role='API',account_version=0,system_usable=False,
  actual_forward_start=False,capability='NOT_GRANTED',prepared_plan_sha256=hashlib.sha256(Path(__file__).with_name('finite-execution-plan.json').read_bytes()).hexdigest(),
  queries_other_than_fixed_endpoint=0)
 Path(__file__).with_name('official-source-assessment.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps(summary,ensure_ascii=False))
assert not app.state.reviews.thread
