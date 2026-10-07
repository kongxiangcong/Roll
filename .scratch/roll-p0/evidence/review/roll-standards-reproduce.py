import json
from pathlib import Path
import httpx
from fastapi.testclient import TestClient
from roll.app import create_app
from test_independent_verification import acquire, original_quote, command
from test_source_resolution import setup_request
from test_reviews import wait_result

root = Path(__file__).parent / 'roll-standards-length-reproduction'
with TestClient(create_app(root, market_transport=httpx.MockTransport(lambda r: httpx.Response(200, content=original_quote('A:first')))), raise_server_exceptions=False) as client:
    setup_request(client)
    reference = acquire(client)
    task = wait_result(client, client.post('/api/reviews/tasks', json={'mode':'ON_DEMAND'}).json()['task_id'])
    payload = command([reference])
    payload['reason'] = 'x' * 2001
    saved = client.post('/api/reviews/tasks/' + task['task_id'] + '/verification-request', json=payload)
    saved.raise_for_status()
    consumed = client.post('/api/reviews/verification-requests/' + saved.json()['request_id'] + '/verify')
    report = {'evidence_kind':'METHOD_CASE', 'public_original_request_status':saved.status_code, 'consumption_status':consumed.status_code, 'consumption_body':consumed.text, 'reason_length':len(payload['reason']), 'actual_external_network_calls':0}
    (Path(__file__).parent / 'roll-standards-reproduction.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
