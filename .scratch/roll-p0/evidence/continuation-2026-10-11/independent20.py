"""Independent public-API acceptance using only an isolated METHOD runtime."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / 'backend/tests/application'))
from fastapi.testclient import TestClient
from roll.app import create_app
from test_shadow import setup, freeze, high_forecasts
from test_account import baseline, submit

directory = Path(sys.argv[1]).resolve()
if directory.exists():
    raise RuntimeError('Independent runtime must be new; never delete or reuse existing state')
directory.mkdir(parents=True)

with TestClient(create_app(directory)) as client:
    _, protocol, model, dates = setup(client, directory)
    holding = {'instrument': protocol['scope']['instruments'][0], 'quantity': '200',
               'acquisition_cost_yuan': '20000.00', 'acquired_on': '2025-12-31'}
    response = freeze(client, protocol, model, baseline={'cash_yuan': '100000.00', 'positions': [holding]})
    assert response.status_code == 201, response.text
    frozen = response.json()
    forecasts = high_forecasts(client, model)
    day = forecasts[0]['observation_cutoff'][:10]
    path = '/api/research/shadow/' + frozen['freeze_id']
    complete_archive = directory / frozen['archive']['path']
    original_complete = complete_archive.read_bytes()
    assert hashlib.sha256(original_complete).hexdigest() == frozen['archive']['sha256']
    complete_archive.write_bytes(original_complete + b' ')
    corrupt_freeze = client.post(path + '/advance', json={'through_date': day,
        'forecast_ids': [f['forecast_id'] for f in forecasts], 'expected_revision': 0})
    assert corrupt_freeze.status_code == 409, corrupt_freeze.text
    assert corrupt_freeze.json()['detail'] == {'code': 'ARCHIVE_MISSING_OR_CORRUPT'}
    complete_archive.write_bytes(original_complete)
    assert client.get(path).json()['revision'] == 0
    first = client.post(path + '/advance', json={'through_date': day,
        'forecast_ids': [f['forecast_id'] for f in forecasts], 'expected_revision': 0})
    assert first.status_code == 201, first.text
    first = first.json()
    assert first['cash_yuan'] == '100000.00' and first['positions'][0]['quantity'] == '200'
    assert all(o['action'] == 'REFUSE' and 'OVERLAPPING_POSITION_OR_ORDER' in o['reasons'] for o in first['opportunities'])
    mature_day = dates[dates.index(day) + 20]
    final = client.post(path + '/advance', json={'through_date': mature_day,
        'forecast_ids': [], 'expected_revision': 1})
    assert final.status_code == 201, final.text
    saved = final.json()
    assert saved['cash_yuan'] == '100000.00' and saved['positions'][0]['quantity'] == '200'
    assert saved['events'] == [] and saved['realized_gain_yuan'] == '0.00'
    assert all(o['counterfactual']['diagnostic_only'] for o in saved['opportunities'])
    assert client.post(path + '/replay').json()['matches_original'] is True
    actual = baseline()
    assert submit(client, actual, 'independent-actual-baseline').status_code == 200
    assert client.get(path).json() == saved
    diagnostic = client.post(path + '/account-conditional', json={'forecast_ids': [f['forecast_id'] for f in forecasts]})
    assert diagnostic.status_code == 201, diagnostic.text
    diagnostic = diagnostic.json()
    assert diagnostic['namespace'] == 'ACCOUNT_CONDITIONAL' and diagnostic['continuous_performance'] is False
    assert diagnostic['account_version'] == 1 and client.get(path).json() == saved
    results = client.get('/api/research/results', params={'freeze_id': frozen['freeze_id']}).json()
    assert set(results) == {'ACTUAL', 'HISTORICAL', 'SHADOW', 'ACCOUNT_CONDITIONAL'}
    assert client.get('/api/research/protocols/' + protocol['protocol_id']).json()['forward_started_at'] is None

with TestClient(create_app(directory)) as client:
    assert client.get(path).json() == saved
    assert client.post(path + '/replay').json()['matches_original'] is True
    artifact = directory / saved['input_archive']['path']
    before = artifact.read_bytes()
    assert hashlib.sha256(before).hexdigest() == saved['input_archive']['sha256']
    artifact.write_bytes(before + b' ')
    refused = client.post(path + '/replay')
    assert refused.status_code == 409, refused.text
    assert refused.json()['detail'] == {'code': 'ARCHIVE_MISSING_OR_CORRUPT'}
    artifact.write_bytes(before)
    assert client.post(path + '/replay').json()['matches_original'] is True

print(json.dumps({'status': 'PASS', 'evidence_kind': 'METHOD_CASE', 'freeze_id': frozen['freeze_id'],
    'shadow_revision': saved['revision'], 'nonempty_baseline_preserved': True,
    'overlap_refusals': len(saved['opportunities']), 'actual_version': 1,
    'restart_replay': True, 'isolated_archive_corruption_refused': True,
    'complete_protocol_archive_corruption_refused': True,
    'sealed_read': False, 'forward_started': False, 'capability': frozen['capability']}, indent=2))
