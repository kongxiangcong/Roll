"""Public API acceptance; writes only a new isolated METHOD runtime."""
import hashlib
import json
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / 'backend/tests/application'))
from test_shadow import setup, freeze, high_forecasts

directory = Path(sys.argv[1]).resolve()
if directory.exists():
    raise RuntimeError('Independent runtime must be new; preserve every prior profile')
directory.mkdir(parents=True)

def saved(client, frozen):
    r = client.post('/api/research/complete-freezes/' + frozen['freeze_id'] + '/validations', json={
        'purpose': 'DIAGNOSTIC', 'expected_complete_protocol_fingerprint': frozen['complete_protocol_fingerprint'],
        'basis': 'Independent METHOD acceptance: no statistical qualification or real forward'})
    assert r.status_code == 201, r.text
    result = r.json()
    assert result['validation_attempt']['status'] == 'SUCCEEDED'
    assert result['experiment_status'] == 'RUNNING_DIAGNOSTIC'
    assert result['review_status'] == 'PENDING_TECHNICAL_REVIEW'
    assert result['capability_status'] == 'NOT_GRANTED' and result['system_usable'] is False
    assert result['confirmation_pass_look'] is False and result['sealed_read'] is False
    assert result['gates']['G7']['status'] == 'INCONCLUSIVE'
    assert result['gates']['G2']['status'] == 'INCONCLUSIVE'
    assert result['gates']['G2']['details']['replay_subcheck'] == 'PASS'
    return result

with TestClient(create_app(directory)) as client:
    dataset, protocol, model, dates = setup(client, directory)
    main = freeze(client, protocol, model).json()
    forecasts = high_forecasts(client, model)
    day = forecasts[0]['observation_cutoff'][:10]
    mature = dates[dates.index(day) + 20]
    path = '/api/research/shadow/' + main['freeze_id']
    r = client.post(path + '/advance', json={'through_date': mature,
        'forecast_ids': [f['forecast_id'] for f in forecasts], 'expected_revision': 0})
    assert r.status_code == 201, r.text
    state = r.json()
    assert [o['action'] for o in state['opportunities']] == ['BUY', 'REFUSE']
    assert [e['kind'] for e in state['events']] == ['BUY_FILL', 'SELL_FILL']
    canonical = saved(client, main)
    g4 = canonical['gates']['G4']['details']
    assert (g4['unique_opportunities'], g4['selected'], g4['decision_coverage']) == (1, 1, 1)
    assert 'MINIMUM_DECISION_COVERAGE_NOT_MET' not in g4['hard_failures']
    assert sum(c['details']['closed_positions'] for c in canonical['gates']['G5']['details']['time_segments']) == 1
    assert all(c['method_fingerprint'] and c['input_fingerprint'] and c['result_fingerprint']
        for c in canonical['gates']['G5']['details']['delays'])
    assert canonical['monitoring_method_validation']['checks_passed'] is True

    def successor(cash, use_forecasts):
        p = client.post('/api/research/protocols', json={'dataset_id': dataset['dataset_id'],
            'predecessor_id': protocol['protocol_id'], 'basis': 'Separate METHOD baseline; no inherited performance'}).json()
        r = freeze(client, p, model, baseline={'cash_yuan': cash, 'positions': []})
        assert r.status_code == 201, r.text
        f = r.json()
        r = client.post('/api/research/shadow/' + f['freeze_id'] + '/advance', json={
            'through_date': day, 'forecast_ids': [x['forecast_id'] for x in forecasts] if use_forecasts else [], 'expected_revision': 0})
        assert r.status_code == 201, r.text
        return f, saved(client, f)

    empty_freeze, empty = successor('100000.00', False)
    low_freeze, failed = successor('5000.00', True)
    assert empty['validation_verdict'] == 'INCONCLUSIVE'
    assert empty['gates']['G4']['details']['unique_opportunities'] == 0
    assert empty['gates']['G4']['details']['candidate']['net_return'] == 0
    assert failed['validation_verdict'] == 'FAIL' and failed['gates']['G4']['status'] == 'FAIL'
    assert 'MINIMUM_DECISION_COVERAGE_NOT_MET' in failed['gates']['G4']['reasons']
    assert client.get(path).json() == state
    validation_path = '/api/research/complete-freezes/' + main['freeze_id'] + '/validations'
    refusal = client.post(validation_path, json={'purpose': 'CONFIRMATORY',
        'expected_complete_protocol_fingerprint': main['complete_protocol_fingerprint'], 'basis': 'Independent admission refusal check'})
    assert refusal.status_code == 409, refusal.text
    assert refusal.json()['detail']['sealed_read'] is False and refusal.json()['detail']['input_content_consumed'] is False
    assert len(client.get(validation_path).json()) == 1
    assert not any(e['action'] == 'SEALED_INPUT_ACCESSED' for e in client.get('/api/research/protocols/' + protocol['protocol_id'] + '/audit').json())
    assert client.get('/api/account').json()['version'] == 0
    assert client.get('/api/research/protocols/' + protocol['protocol_id']).json()['forward_started_at'] is None

with TestClient(create_app(directory)) as client:
    for result in [canonical, empty, failed]:
        p = '/api/research/validations/' + result['validation_id']
        assert client.get(p).json() == result
        replay = client.post(p + '/replay')
        assert replay.status_code == 200, replay.text
        assert replay.json()['matches_original'] and replay.json()['network_calls'] == 0
    p = '/api/research/validations/' + canonical['validation_id']
    for field, operation in [('manifest_archive', 'get'), ('input_archive', 'replay')]:
        artifact = directory / canonical[field]['path']
        original = artifact.read_bytes()
        assert hashlib.sha256(original).hexdigest() == canonical[field]['sha256']
        try:
            artifact.write_bytes(original + b' ')
            response = client.get(p) if operation == 'get' else client.post(p + '/replay')
            assert response.status_code == 409, response.text
            assert response.json()['detail'] == {'code': 'ARCHIVE_MISSING_OR_CORRUPT'}
        finally:
            artifact.write_bytes(original)
    assert client.get(p).json() == canonical
    assert client.post(p + '/replay').json()['matches_original'] is True

print(json.dumps({'status': 'PASS', 'evidence_kind': 'METHOD_CASE', 'profile': str(directory),
    'canonical_validation_id': canonical['validation_id'], 'unique_opportunities': 1, 'raw_opportunities': 2,
    'selected': 1, 'segment_total_closed_positions': 1,
    'empty_validation_id': empty['validation_id'], 'empty_verdict': empty['validation_verdict'],
    'budget_validation_id': failed['validation_id'], 'budget_verdict': failed['validation_verdict'],
    'budget_G4_reasons': failed['gates']['G4']['reasons'], 'G2': 'INCONCLUSIVE', 'G2_replay_subcheck': 'PASS',
    'G7': 'INCONCLUSIVE', 'persisted_restart_replays': 3, 'network_calls': 0,
    'manifest_and_input_corruption_refused': True, 'confirmation_refusal_http': 409,
    'sealed_read': False, 'account_version': 0, 'forward_started': False, 'capability': 'NOT_GRANTED'}, indent=2))
