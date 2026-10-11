"""Run only after explicit parent release; one fresh namespace, two exact attempts."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.market.sse_company_actions import fingerprint, contract

folder=Path(__file__).resolve().parent
repo=folder.parents[3]
plan_body=(folder/'finite-execution-plan.json').read_bytes()
plan_sha=hashlib.sha256(plan_body).hexdigest()
assert plan_sha=='c308f42dc7828c5aa092ff4254291b2b3d8f7ba3f6eb9746bddf3f5bb57d1e3e'
plan=json.loads(plan_body)
release=json.loads((folder/'explicit-parent-release.json').read_bytes())
assert release['execution_plan_hash']==plan_sha and release['explicit_release'] is True
assert release['budget_total_attempts']==2 and release['authority']=='/root'
assert plan['request_budget_total_attempts']==2 and not plan['redirects'] and plan['retries']==plan['fallbacks']==0
assert plan['implementation_fingerprint']==fingerprint()
assert plan['document_sources']==contract()['sources']
for filename,expected in plan['source_inventory'].items():
    body=(repo/filename).read_bytes().replace(b'\r\n',b'\n')
    assert len(body)==expected['bytes_lf'] and hashlib.sha256(body).hexdigest()==expected['sha256_lf']
directory=repo/plan['runtime_namespace']
assert not directory.exists(),'One-time attempt namespace already exists; no implicit retry.'
began=datetime.now(timezone.utc).isoformat()
with TestClient(create_app(directory,runtime_role='API')) as client:
    created=client.post('/api/research/collections',json={'instrument':'SSE:600362',
        'basis':'Ninth released finite two-attempt public action source assessment; no qualification'})
    assert created.status_code==201,created.text
    base='/api/research/collections/'+created.json()['plan_id']
    assert client.get(base+'/sse-company-action-receipts').json()==[]
    response=client.post(base+'/sse-company-actions',json={'basis':
        'Frozen exact first-page FH/SG plan, no retry/fallback/redirect/extra page; raw-first only'})
    assert response.status_code==201,response.text
    receipt=response.json()
    assert receipt['evidence_kind']=='REAL_SOURCE_ASSESSMENT' and receipt['network_calls']<=2
    assert receipt['implementation_fingerprint']==plan['implementation_fingerprint']
    assert not receipt['system_usable'] and not receipt['complete_action_coverage']
    assert receipt['forward_started_at'] is None and receipt['capability']=='NOT_GRANTED'
    assert client.get(base+'/sse-company-action-receipts').json()==[receipt]
    target=folder/'runtime/source-assessment'
    target.mkdir(parents=True,exist_ok=False)
    for role,saved in receipt['responses'].items():
        archive=saved['archive']
        raw=client.get('/api/data/archives/'+archive['sha256']).content
        assert hashlib.sha256(raw).hexdigest()==archive['sha256']
        (target/(archive['sha256']+'.raw')).write_bytes(raw)
    (target/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    summary={'execution_plan_hash':plan_sha,'execution_started_at':began,
        'execution_finished_at':datetime.now(timezone.utc).isoformat(),
        'collection_plan_id':created.json()['plan_id'],'receipt_id':receipt['receipt_id'],
        'actual_attempts':receipt['network_calls'],'responses':receipt['responses'],
        'errors':receipt['errors'],'status':receipt['status'],'source_gaps':receipt['gaps'],
        'query_date_scope':'UNKNOWN','current_or_negative_coverage':False,'system_usable':False,
        'actual_forward_start':False,'capability':'NOT_GRANTED','background_worker_started':False,
        'implicit_retry_or_fallback_or_third_call':False,'provider_model_notification_calls':0}
    (folder/'actual-assessment-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:summary[k] for k in ['actual_attempts','status','errors','execution_started_at','execution_finished_at']}))
