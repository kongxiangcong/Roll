"""Public action evaluation timing; METHOD inputs, actual frozen policy configuration."""
import hashlib
import json
import math
import os
import platform
import sys
import time
from datetime import date, timedelta
from pathlib import Path
sys.path[:0] = [str(Path.cwd() / 'backend/src'), str(Path.cwd() / 'backend/tests/support'), str(Path.cwd() / 'backend/tests/application')]
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.accounts.ledger import encode
from test_actions import action_package, prepare
from capability_method_app import save_package
from roll.research.models import features, predict, code_fingerprint
from roll.research.shadow import calculate_policy
from roll.decisions.capabilities import source_inventory
from roll.accounts.ledger import Ledger
from roll.market.rules import RuleCalendar

os.environ['ROLL_ENV'] = 'test'
reference_path = Path('D:/dsh-proj/Roll/.scratch/roll-p0/evidence/continuation-2026-10-11/frontier24-29/benchmark-artifact-reference.json')
reference = json.loads(reference_path.read_text(encoding='utf-8'))
artifacts = []
for item in reference['artifacts']:
    raw = Path(item['path']).read_bytes()
    assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256']
    artifacts.append(json.loads(raw))
model, calibrator, body = artifacts
p = action_package()
directory = Path('D:/dsh-proj/Roll/.roll-data/r25b')
assert not directory.exists(), 'Use a fresh independent benchmark directory'
rules = RuleCalendar(Ledger(directory / 'calendar'))
policy = {'version': '20-policy-v1', 'probability_threshold': '0.60', 'quantity': '200',
    'maximum_gross_exposure': body['policy']['maximum_gross_exposure'],
    'ordering': 'descending_probability_then_instrument_then_forecast_id', 'one_active_lot_per_instrument': True,
    'exit': 'HORIZON_SESSION20_CLOSE', 'cash_flow_policy': 'NO_EXTERNAL_FLOWS', 'rejected_outcomes': 'MATURE_PREDICTION_DIAGNOSTIC_ONLY',
    'joint_budget': 'reserve_upper_price_plus_fees_before_fills; no leverage or simultaneous opportunity sums'}
assert hashlib.sha256(encode(policy).encode()).hexdigest() == body['fingerprints']['policy']
symbols = [*body['scope']['instruments'], *['SSE:' + str(600000+i) for i in range(29)]]
p['scope']['instruments'] = body['scope']['instruments']
p['current_data']['instruments'] = body['scope']['instruments']
p['action_packet']['policy'] = policy
p['action_packet']['opportunities'] = [{**p['action_packet']['opportunities'][1], 'instrument': symbol, 'forecast_id': 'METHOD-'+symbol} for symbol in symbols]
observation = '2026-09-30'
days = []
cursor = date.fromisoformat(observation)
while len(days) < 21:
    if rules.calendar('SSE', cursor)['is_trading_day'] is True: days.append(cursor.isoformat())
    cursor -= timedelta(days=1)
days.reverse()
# Explicit METHOD bars, zero cash events: raw and economic feature vectors coincide.
facts = [{'instrument': 'SSE:600362', 'trade_date': day, 'close': str(100+i), 'volume_shares': str(1000000+i*10000),
    'adjustment': 'RAW', 'volume_unit': 'SHARE', 'errors': [], 'completion_state': 'COMPLETE_REPORTED_HISTORICAL',
    'method_completion_available_at': day+'T15:05:00+08:00', 'available_at': p['required_as_of'],
    'raw_hash': hashlib.sha256(('METHOD-'+day).encode()).hexdigest(), 'cash_events_effective': [], 'evidence_kind': 'METHOD_CASE'} for i, day in enumerate(days)]
snapshot = features(facts, observation, True, p['required_as_of'])
Path(directory / 'feature-packet.json').write_bytes(encode(facts).encode())
def check_calendar(snapshot):
    for earlier, later in zip(snapshot['input_trade_dates'], snapshot['input_trade_dates'][1:]):
        assert rules.next_trading_day('SSE', date.fromisoformat(earlier)) == later
check_calendar(snapshot)
prediction = predict(model['fit'], snapshot, calibrator['intercept_shift'])
# Independent arithmetic check of four values, scaler, logit and calibration.
closes=[float(r['close']) for r in facts]
volumes=[float(r['volume_shares']) for r in facts]
returns=[closes[i]/closes[i-1]-1 for i in range(1,len(closes))]
mean=sum(returns)/20
manual=[closes[-1]/closes[-6]-1,closes[-1]/closes[0]-1,
        math.sqrt(sum((r-mean)**2 for r in returns)/20),math.log(volumes[-1]/(sum(volumes[:-1])/20))]
assert all(abs(a-b)<1e-12 for a,b in zip(manual,snapshot['values']))
scaled=[1,*[(v-m)/s for v,m,s in zip(manual,model['fit']['means'],model['fit']['scales'])]]
manual_logit=sum(a*b for a,b in zip(scaled,model['fit']['weights']))
assert abs(manual_logit-prediction['logit'])<1e-10
assert abs(1/(1+math.exp(-manual_logit))-prediction['uncalibrated_probability'])<1e-10
assert abs(1/(1+math.exp(-manual_logit-calibrator['intercept_shift']))-prediction['probability'])<1e-10
for row in p['action_packet']['opportunities']:
    row.update(probability=str(prediction['probability']), forecast_cutoff=snapshot['observation_cutoff'])
p['action_packet']['offline_numeric_binding'] = {'model_sha256': reference['artifacts'][0]['sha256'],
    'calibrator_sha256': reference['artifacts'][1]['sha256'], 'feature_packet_sha256': hashlib.sha256(encode(facts).encode()).hexdigest()}
p['loss_facts'] = {**p['loss_facts'], 'baseline_assets': '104050.10', 'net_assets': '104050.10'}
p['action_packet']['loss_facts'] = p['loss_facts']
file = save_package(directory / 'qualification.json', p)
with TestClient(create_app(directory / 'data', capability_method_file=file)) as client:
    holdings = [{'instrument': s, 'quantity': '1', 'sellable_quantity': '1', 'reference_cost': '135.00'} for s in symbols]
    prepare(client, p, holdings)
    durations, numeric_times, application_times = [], [], []
    identifiers = []
    for _ in range(21):
        started = time.perf_counter()
        fresh_snapshot = features(facts, observation, True, p['required_as_of'])
        check_calendar(fresh_snapshot)
        fresh = predict(model['fit'], fresh_snapshot, calibrator['intercept_shift'])
        assert fresh == prediction
        numeric_finished = time.perf_counter()
        response = client.post('/api/actions/evaluate', json={})
        finished = time.perf_counter()
        durations.append(finished - started)
        numeric_times.append(numeric_finished-started)
        application_times.append(finished-numeric_finished)
        assert response.status_code == 201, response.text
        value = response.json()
        identifiers.append(value['evaluation_id'])
        assert len(value['observations']) == 35
        assert len([r for r in value['refusals'] if 'PROFIT_CAPABILITY_NOT_CURRENT_IN_SCOPE' in r['reasons']]) == 29
        assert all(r['instrument'] == 'SSE:600362' for r in value['decisions'])
    p95 = sorted(durations)[math.ceil(len(durations)*.95)-1]
    assert p95 <= 30
    result = {'device': {'platform': platform.platform(), 'processor': platform.processor(), 'cpu_count': os.cpu_count(), 'python': sys.version},
        'stocks': symbols, 'indices': [o['instrument'] for o in value['observations'] if o['instrument'] not in symbols],
        'artifact_reference_sha256': hashlib.sha256(reference_path.read_bytes()).hexdigest(), 'artifact_bindings': reference['artifacts'],
        'actual_frozen_policy': policy, 'actual_candidate_fingerprints': body['fingerprints'], 'model_dependency_code_fingerprint': code_fingerprint(),
        'feature_packet_sha256': hashlib.sha256(encode(facts).encode()).hexdigest(), 'prediction': prediction,
        'feature_trade_dates': snapshot['input_trade_dates'], 'calendar_validation': '21 consecutive archived SSE trading sessions; 2026-09-25 excluded',
        'application_sources': source_inventory(),
        'admitted_scope': body['scope']['instruments'], 'samples_seconds': durations, 'nearest_rank_p95_seconds': p95,
        'numeric_layer_seconds': numeric_times, 'application_layer_seconds': application_times,
        'external_acquisition_seconds': 0, 'network_calls': 0, 'distinct_evaluation_ids': len(set(identifiers)),
        'namespace': 'METHOD_ENGINEERING', 'system_usable': False,
        'limitations': ['Full local path includes features, actual frozen scaler/weights, intercept-only calibrator and public application current-data/authority/budget/publication.',
            'No fitting, forecast persistence, actual profile startup, real forward or external acquisition. Numeric METHOD scores are host-frozen and identical to each freshly calculated vector.',
            'Zero METHOD cash events make raw/economic return values coincide; feature input remains synthetic and no historical or market validity is claimed.',
            'Synthetic features/quoted prices/account/grant and probabilities calculated with actual frozen parameters; same policy and admitted scope; no real G1-G7 claim.',
            'Synthetic loss assets104050.10 equal confirmed cash100000.10 plus30 single shares marked135, fixed baseline and zero external flow/pnl.',
            '30 explicitly confirmed METHOD initial holdings exercise the over-limit asset-preservation path; combined watch limit20 is retained.',
            '29 outside-scope stocks explicitly refused; admitted single existing position also blocks overlapping new entry; 5 indices background-only. No expansion of actual candidate scope.']}
    Path('D:/dsh-proj/Roll/.scratch/roll-p0/evidence/continuation-2026-10-11/ticket25-independent/benchmark-results.json').write_bytes(json.dumps(result, ensure_ascii=False, indent=2).encode())
    print(json.dumps({'p95_seconds': p95, 'stocks': 30, 'indices': 5, 'distinct_evaluations': len(set(identifiers))}))
