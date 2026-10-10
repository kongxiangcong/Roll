"""Independent public-API METHOD acceptance; no actual provider or personal auth."""
import io
import json
import os
import sys
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / 'backend/tests/application'))
from test_technical_review import WORKER, terminal, validated
from test_codex_evidence import request_data

profile = Path(sys.argv[1]).resolve()
if profile.exists():
    raise RuntimeError('A new isolated METHOD profile is required')
profile.mkdir(parents=True)
directory = profile / 'runtime'
credential = profile / 'synthetic-auth.json'
credential.write_text(json.dumps({'auth_mode': 'chatgpt', 'tokens': {'access_token': 'METHOD_CASE_ONLY'}}))
os.environ['ROLL_ENV'] = 'test'
os.environ['ROLL_CODEX_AUTH_FILE'] = str(credential)
os.environ['ROLL_CODEX_MODEL'] = 'METHOD_ENGINEERING_WORKER'
for key in ['DEEPSEEK_API_KEY', 'ROLL_DEEPSEEK_API_KEY_FILE', 'ROLL_TECHNICAL_REVIEW_TIMEOUT_SECONDS']:
    os.environ.pop(key, None)
worker = profile / 'fixed-worker.py'
worker.write_text(WORKER)
fixture = profile / 'finished-cases.json'
fixture.write_text(json.dumps({'cases': [
    {'case_id': 'completed-failure', 'gates': {'G1': 'PASS', 'G4': 'FAIL', 'G7': 'INCONCLUSIVE'}, 'checks_complete': True, 'endpoint_reached': True, 'observed_value': -1},
    {'case_id': 'completed-uncertainty', 'gates': {'G1': 'PASS', 'G4': 'INCONCLUSIVE', 'G7': 'INCONCLUSIVE'}, 'checks_complete': True, 'endpoint_reached': True, 'observed_value': None},
    {'case_id': 'unfinished-bounded', 'gates': {'G4': 'INCONCLUSIVE'}, 'checks_complete': False, 'endpoint_reached': False, 'observed_value': None}]}))

def start(client, material, retry=None):
    command = {'expected_material_fingerprint': material['material_fingerprint']}
    if retry:
        command['retry_of'] = retry
    r = client.post('/api/research/review-materials/' + material['material_id'] + '/reviews', json=command)
    assert r.status_code == 202, r.text
    return terminal(client, r.json()['run_id'])

with TestClient(create_app(directory, codex_worker=worker, technical_review_method_file=fixture)) as client:
    validation = validated(client, directory)
    r = client.post('/api/research/validations/' + validation['validation_id'] + '/review-materials', json={})
    assert r.status_code == 201, r.text
    material = r.json()
    path = '/api/research/review-materials/' + material['material_id']
    worker.write_text(WORKER.replace("emit(kind='completed',status='completed',output=json.dumps(output),error_info=None)",
        "output['checks'][0]['result_sha256']='forged-proof'\nemit(kind='completed',status='completed',output=json.dumps(output),error_info=None)"))
    invalid = start(client, material)
    assert invalid['status'] == 'INVALID_OUTPUT' and invalid['error']['code'] == 'REVIEW_REPRODUCTION_CLAIM_MISMATCH'
    assert 'review_record' not in invalid
    # Agreement and omitted objections cannot clear host-registered evidence gaps.
    worker.write_text(WORKER.replace("emit(kind='completed',status='completed',output=json.dumps(output),error_info=None)",
        "output['issues']=[]\nemit(kind='completed',status='completed',output=json.dumps(output),error_info=None)"))
    review = start(client, material, invalid['run_id'])
    assert review['status'] == 'COMPLETE', review
    assert review['evidence_kind'] == 'METHOD_CASE_TECHNICAL_REVIEW'
    assert review['model'] == 'METHOD_ENGINEERING_WORKER' and review['retry_of'] == invalid['run_id']
    assert review['allowed_tools'] == ['roll_read_review_material', 'roll_reproduce_validation']
    record = review['review_record']
    assert record['reproduction_verified'] and not record['blocking_issues_resolved']
    assert 'G7' in record['host_unresolved_gate_evidence'] and record['human_independent_review'] is False
    delivery = client.get(path + '/delivery').json()
    assert delivery['review_status'] == 'COMPLETE' and delivery['delivery_status'] == 'INCOMPLETE' and delivery['preliminary']
    assert delivery['capability_status'] == 'NOT_GRANTED'
    assert client.get('/api/research/validations/' + validation['validation_id']).json() == validation
    assert client.post('/api/research/technical-reviews/' + review['run_id'] + '/grant', json={}).status_code == 404
    assert client.post('/api/formal/evaluate', json={}).status_code == 403
    assert client.get('/api/account').json()['version'] == 0
    completed = []
    cases = client.get('/api/research/method-review-materials').json()
    worker.write_text(WORKER)
    for case in cases[:2]:
        assert start(client, case)['status'] == 'COMPLETE'
        current = client.get('/api/research/review-materials/' + case['material_id'] + '/delivery').json()
        assert current['delivery_status'] == 'COMPLETE' and not current['preliminary']
        assert current['validation_verdict'] in ['FAIL', 'INCONCLUSIVE'] and current['evidence_kind'] == 'METHOD_CASE'
        assert current['capability_status'] == 'NOT_GRANTED'
        completed.append(current['validation_verdict'])
    worker.write_text("import json,sys,time\njson.loads(sys.stdin.readline())\nprint(json.dumps({'kind':'turn','turn_id':'bounded'}),flush=True)\ntime.sleep(120)\n")
    bounded = cases[2]
    bound_path = '/api/research/review-materials/' + bounded['material_id']
    command = {'expected_material_fingerprint': bounded['material_fingerprint']}
    waiting = client.post(bound_path + '/reviews', json=command).json()
    assert waiting['status'] == 'RUNNING'
    assert client.post(bound_path + '/reviews', json=command).status_code == 409
    listing = client.get('/api/market/list').json()
    if not any(m['instrument'] == 'SSE:600519' for m in listing['members']):
        client.post('/api/market/watch', json={'operation': 'ADD', 'instrument': 'SSE:600519', 'expected_list_version': listing['version']}).raise_for_status()
    request_id = request_data(client)
    competing = client.post('/api/data/requests/' + request_id + '/agent', json={'question': 'Bounded METHOD concurrency check'})
    assert competing.status_code == 409 and competing.json()['detail']['code'] == 'AGENT_CONCURRENCY_LIMIT', competing.text
    client.post('/api/agents/settings', json={'expected_version': 0, 'backend': 'DEEPSEEK'}).raise_for_status()
    assert client.get('/api/research/technical-reviews/' + waiting['run_id']).json()['backend'] == 'CODEX'
    client.post('/api/research/technical-reviews/' + waiting['run_id'] + '/cancel', json={}).raise_for_status()
    cancelled = terminal(client, waiting['run_id'])
    assert cancelled['status'] == 'CANCELLED' and cancelled['process']['remaining_pids'] == []
    unavailable = start(client, bounded, cancelled['run_id'])
    assert unavailable['backend'] == 'DEEPSEEK' and unavailable['status'] == 'UNAVAILABLE'
    client.post('/api/agents/settings', json={'expected_version': 1, 'backend': 'CODEX'}).raise_for_status()
    os.environ['ROLL_TECHNICAL_REVIEW_TIMEOUT_SECONDS'] = '1'
    timed = start(client, bounded, unavailable['run_id'])
    assert timed['status'] == 'TIMED_OUT' and timed['process']['remaining_pids'] == []
    assert client.get('/api/account').json()['version'] == 0
    assert client.get('/api/research/protocols/' + validation['protocol_id']).json()['forward_started_at'] is None

with TestClient(create_app(directory, technical_review_method_file=fixture)) as client:
    assert client.get('/api/research/technical-reviews/' + review['run_id']).json() == review
    assert client.get('/api/research/review-materials/' + material['material_id'] + '/delivery').json() == delivery
    exported = client.post(path + '/export', json={})
    assert exported.status_code == 201, exported.text
    data = client.get('/api/data/archives/' + exported.json()['archive']['sha256'])
    assert data.status_code == 200
    with zipfile.ZipFile(io.BytesIO(data.content)) as package:
        local = json.loads(package.read('manifest.json'))
        assert len(local['review_attempts']) == 2 and local['delivery'] == delivery
        assert 'code/research/registry.py' in package.namelist()
        assert json.loads(package.read('archives/' + validation['input_archive']['sha256']))['replay']['forecasts']
    original = directory / material['inventory'][0]['archive']['path']
    before = original.read_bytes()
    try:
        original.write_bytes(before + b' ')
        assert client.get(path).status_code == 409
        assert client.post(path + '/export', json={}).status_code == 409
    finally:
        original.write_bytes(before)
    assert client.get(path).json() == material

os.environ['ROLL_ENV'] = 'production'
try:
    create_app(profile / 'production-refused', technical_review_method_file=fixture)
except ValueError as error:
    assert 'METHOD' in str(error)
else:
    raise AssertionError('Production accepted a host METHOD fixture')
with TestClient(create_app(directory)) as client:
    assert client.get('/api/research/review-materials/' + cases[0]['material_id']).status_code == 409
    assert client.get('/api/research/technical-reviews/' + review['run_id']).json()['evidence_kind'] == 'METHOD_CASE_TECHNICAL_REVIEW'

print(json.dumps({'status': 'PASS', 'evidence_kind': 'METHOD_CASE', 'profile': str(profile),
    'validation_id': validation['validation_id'], 'review_id': review['run_id'], 'record_status': 'COMPLETE',
    'frozen_experiment_delivery': delivery['delivery_status'], 'host_G7_gap_preserved': True,
    'forged_reproduction_refused': True, 'completed_method_verdicts': completed,
    'bounded_statuses': [cancelled['status'], unavailable['status'], timed['status']],
    'acquisition_and_review_shared_concurrency': True, 'restart_export_matches': True,
    'corrupt_material_refused': True, 'production_method_fixture_and_load_refused': True,
    'account_version': 0, 'forward_started': False, 'capability': 'NOT_GRANTED',
    'actual_provider_invoked': False, 'external_transmissions': 0}, indent=2))
