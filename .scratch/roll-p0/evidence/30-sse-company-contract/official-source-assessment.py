"""One authorized anonymous two-attempt assessment in a new API-only namespace."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.market import sse_company_contract as source
from roll.market.rules import SHANGHAI
folder = Path(__file__).resolve().parent
repo = folder.parents[3]
plan = json.loads((folder / 'finite-execution-plan.json').read_bytes())
directory = repo / '.scratch/t30u-live'
assert plan['namespace'] == str(directory) and not directory.exists()
assert plan['total_actual_http_attempt_limit'] == 2 and plan['retries'] == plan['fallbacks'] == 0
assert plan['host_date'] == datetime.now(SHANGHAI).date().isoformat()
assert plan['parser_fingerprint'] == source.fingerprint()
assert plan['document_mapping_hash'] == source.schema()['mapping_hash']
for filename, expected in plan['source_files'].items():
    content = (repo / filename).read_bytes()
    assert len(content) == expected['bytes'] and hashlib.sha256(content).hexdigest() == expected['sha256']
started = datetime.now(timezone.utc).isoformat()
app = create_app(directory, runtime_role='API')
with TestClient(app) as client:
    created = client.post('/api/research/collections', json={'instrument': 'SSE:600362',
        'basis': 'Seventh authorized exact two-source public assessment; unknown authority remains explicit'})
    assert created.status_code == 201, created.text
    base = '/api/research/collections/' + created.json()['plan_id']
    response = client.post(base + '/sse-company-contract/check', json={'basis':
        'Frozen two-attempt finite plan; no retry, redirect, fallback or production qualification'})
    assert response.status_code == 201, response.text
    job = response.json()
    receipts = client.get(base + '/sse-company-contract-receipts')
    assert receipts.status_code == 200, receipts.text
    receipt = receipts.json()[0]
    assert receipt['receipt_id'] == job['receipt_id'] and receipt['network_calls'] <= 2
    assert receipt['evidence_kind'] == 'REAL_SOURCE_ASSESSMENT' and not receipt['system_usable']
    assert receipt['forward_started_at'] is None and receipt['capability'] == 'NOT_GRANTED'
    target = folder / 'runtime/source-assessment'
    target.mkdir(parents=True, exist_ok=True)
    for saved in receipt['responses'].values():
        archive = saved['archive']
        content = client.get('/api/data/archives/' + archive['sha256']).content
        assert hashlib.sha256(content).hexdigest() == archive['sha256']
        (target / (archive['sha256'] + '.raw')).write_bytes(content)
    (target / 'receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    assert client.get('/api/account').json()['version'] == 0
    summary = {'execution_started_at': started, 'execution_finished_at': datetime.now(timezone.utc).isoformat(),
        'job': job, 'receipt_id': receipt['receipt_id'], 'actual_attempts': receipt['network_calls'],
        'raws': {role: saved['archive'] for role, saved in receipt['responses'].items()},
        'status': receipt['status'], 'errors': receipt['errors'], 'gaps': receipt['gaps'],
        'background_worker_started': False, 'account_version': 0, 'system_usable': False,
        'model_or_provider_or_notification_calls': 0, 'actual_forward_start': False,
        'no_retry_or_fallback_or_third_call': True}
    (folder / 'source-assessment-summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: summary[k] for k in ['actual_attempts', 'status', 'errors', 'execution_started_at', 'execution_finished_at']}))
