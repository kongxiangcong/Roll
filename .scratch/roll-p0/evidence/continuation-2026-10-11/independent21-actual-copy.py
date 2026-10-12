"""Read/replay saved diagnostics only on the authorized consistent actual19 copy."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app

root = Path(__file__).resolve().parents[4]
directory = root / '.roll-data/implementation-evidence/21/actual-current-copy'
receipt = json.loads((root / '.scratch/roll-p0/evidence/21/actual-current-results.json').read_text(encoding='utf-8-sig'))
expected = receipt['validation']
old_id = receipt['prior_method_replay']['validation_id']
pid = expected['protocol_id']
with TestClient(create_app(directory)) as client:
    account = client.get('/api/account').json()
    fit_attempts = client.get('/api/research/protocols/' + pid + '/attempt-manifest').json()
    path = '/api/research/validations/' + expected['validation_id']
    r = client.get(path)
    assert r.status_code == 200 and r.json() == expected, r.text
    old = client.get('/api/research/validations/' + old_id)
    assert old.status_code == 200, old.text
    changed = client.post('/api/research/validations/' + old_id + '/replay')
    assert changed.status_code == 409 and changed.json()['detail'] == 'VALIDATION_CODE_CHANGED_SUCCESSOR_REQUIRED', changed.text
    replay = client.post(path + '/replay')
    assert replay.status_code == 200, replay.text
    assert replay.json()['matches_original'] and replay.json()['network_calls'] == 0
    assert client.get('/api/account').json() == account
    assert client.get('/api/research/protocols/' + pid + '/attempt-manifest').json() == fit_attempts
    assert client.get('/api/research/protocols/' + pid).json()['forward_started_at'] is None
    assert expected['validation_verdict'] == 'FAIL' and expected['gates']['G7']['status'] == 'INCONCLUSIVE'
    assert expected['capability_status'] == 'NOT_GRANTED' and expected['sealed_read'] is False
    result = {'status': 'PASS', 'runtime_copy': str(directory), 'data_use': 'RECONSTRUCTED_RESEARCH',
        'evidence_kind': expected['evidence_kind'], 'validation_id': expected['validation_id'],
        'diagnostic_verdict': expected['validation_verdict'], 'gate_statuses': {k:v['status'] for k,v in expected['gates'].items()},
        'historical_validation_id': old_id, 'historical_record_readable': True,
        'changed_method_replay_http': changed.status_code, 'changed_method_reason': changed.json()['detail'],
        'latest_replay_matches': True, 'network_calls': 0, 'account_unchanged': True,
        'original_fit_attempts_unchanged': True, 'no_new_validation': True, 'no_new_fit': True,
        'sealed_read': False, 'forward_started': False, 'capability_status': expected['capability_status']}
print(json.dumps(result, indent=2))
