"""Independent METHOD public API snapshots/endpoints plus literal rights arithmetic."""
import copy
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.research.shadow import simulate

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'backend/tests/application'))
from test_shadow import freeze
from test_forward_assessment_binding import extended_method

profile = Path(sys.argv[1]).resolve()
assert not profile.exists(), 'Preserve prior independent runtime'
profile.mkdir(parents=True)
os.environ['ROLL_ENV'] = 'test'
os.environ.pop('ROLL_ENV_FILE', None)
os.environ['ROLL_CODEX_AUTH_FILE'] = str(profile / 'no-provider-auth.json')
for key in ('DEEPSEEK_API_KEY', 'ROLL_DEEPSEEK_API_KEY_FILE', 'ROLL_TEST_CRASH_POINT'):
    os.environ.pop(key, None)


def post(client, path, body, code=201):
    response = client.post(path, json=body)
    assert response.status_code == code, (path, response.status_code, response.text)
    return response.json()


def api_case(kind):
    directory = profile / kind
    clock = [datetime.fromisoformat('2026-01-05T14:00:00+08:00')]
    # No lifespan for ordered same-cutoff semantics; no background worker is mocked.
    # Existing44 tests separately cover actual worker/process/recovery behavior.
    client = TestClient(create_app(directory, review_clock=lambda: clock[0]))
    try:
        protocol, model, days = extended_method(client, directory)
        clock[0] = datetime.fromisoformat(days[80] + 'T16:00:00+08:00')
        frozen = freeze(client, protocol, model, baseline={'cash_yuan': '1.00', 'positions': []}).json()
        path = '/api/research/complete-freezes/' + frozen['freeze_id'] + '/forward'
        post(client, path, {'purpose': 'METHOD_VALIDATION', 'basis': 'Independent corrected endpoint METHOD'})
        first = post(client, path + '/check', {'basis': 'Only persisted initial opportunity'})
        if kind == 'membership':
            clock[0] = datetime.fromisoformat(days[100] + 'T16:00:00+08:00')
            saved = post(client, path + '/settle', {'basis': 'Archive snapshot before same-instant second commit'})
            assert saved['sample_ids'] == [first['samples'][0]['sample_id']]
            second = post(client, path + '/check', {'basis': 'Later commit at identical METHOD timestamp'})
            assert len(second['samples']) == 2 and second['samples'][-1]['recorded_at'] == saved['cutoff']
            replay = post(client, path + '/replay', {}, 200)
            assert replay['matches_original'] and replay['network_calls'] == 0
            archived = client.get('/api/data/archives/' + saved['archive']['sha256']).json()
            assert archived == {k: v for k, v in saved.items() if k != 'archive'}
            return {'status': 'PASS', 'samples_now': 2, 'original_assessment_members': len(saved['sample_ids']), 'same_cutoff': True, 'network_calls': 0}
        if kind == 'early-stop':
            stopped = post(client, path + '/stop', {'kind': 'USER_STOP', 'basis': 'Original boundary before maturity'}, 200)
            endpoint = stopped['endpoint']
            assert len(endpoint['unmatured']) == 1 and endpoint['mature'] == []
            clock[0] = datetime.fromisoformat(days[105] + 'T16:00:00+08:00')
        else:
            deadline = datetime.fromisoformat(first['method_deadline'])
            near = max(day for day in days if day < deadline.date().isoformat())
            clock[0] = datetime.fromisoformat(near + 'T16:00:00+08:00')
            last = post(client, path + '/check', {'basis': 'Already archived immature opportunity near deadline'})['samples'][-1]
            assert datetime.fromisoformat(last['action']['maturity_date'] + 'T15:05:00+08:00') > deadline
            clock[0] = deadline
            endpoint = post(client, path + '/check', {'basis': 'Original deadline closes'})['endpoint']
            assert any(item['sample_id'] == last['sample_id'] for item in endpoint['unmatured'])
            clock[0] = datetime.fromisoformat(last['action']['maturity_date'] + 'T16:00:00+08:00') + timedelta(days=2)
        late = post(client, path + '/settle', {'basis': 'Later mature facts do not extend closed experiment'})
        assert late['cutoff'] == endpoint['cutoff']
        assert all(late[k] == endpoint[k] for k in ('mature', 'unmatured', 'unscorable'))
        state = client.get(path).json()
        assert state['endpoint'] == endpoint and state['forward_started_at'] is None
        replay = post(client, path + '/replay', {}, 200)
        assert replay['matches_original'] and replay['network_calls'] == 0
        return {'status': 'PASS', 'original_cutoff': endpoint['cutoff'], 'later_settlement_cutoff': late['cutoff'], 'unmatured_labels': [r['label'] for r in late['unmatured']], 'actual_forward_started': False}
    finally:
        client.close()


days = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(24)]
symbol = 'SSE:600362'
rule = {'state': 'CONFIRMED_NORMAL', 'company_actions': 'CONFIRMED_NONE', 'price_tick_yuan': '.01', 'normal_price_limit_percent': '10'}
rows = [{'instrument': symbol, 'trade_date': day, 'open': '100', 'high': '101', 'low': '99', 'close': '100',
    'volume_shares': '10000', 'errors': [], 'completion_state': 'COMPLETE_REPORTED_HISTORICAL', 'execution_evidence': rule} for day in days]
frozen = {'baseline': {'cash_yuan': '100000.00', 'positions': []}, 'scope': {'instruments': [symbol]}, 'rules': {symbol: rule},
    'fingerprints': {'model': 'LITERAL_METHOD'}, 'policy': {'quantity': '100', 'probability_threshold': '.60', 'maximum_gross_exposure': '.50'},
    'design': {'event': 'METHOD', 'costs': {k: '0' for k in ('minimum_commission_yuan', 'commission_scenario_rate', 'transfer_each_side_rate', 'stamp_sell_rate', 'extra_regulatory_charge', 'slippage_each_side_rate')}}}
forecast = [{'instrument': symbol, 'forecast_id': 'literal', 'observation_cutoff': days[0], 'probability': .9}]
inputs = {'facts': rows, 'sessions': days, 'statutory': {}, 'cash_events': [{'instrument': symbol, 'record_date': days[20], 'ex_date': days[21], 'cash_payment_date': days[22], 'gross_cash_yuan_per_eligible_share': '1'}]}
sold = simulate(frozen, inputs, forecast, days[23])
assert sold['cash_yuan'] == sold['nav_yuan'] == '100000.00' and sold['entitlements'] == [] and sold['realized_gain_yuan'] == '0.00'
blocked_inputs = copy.deepcopy(inputs); blocked_inputs['facts'][20]['execution_evidence'] = {**rule, 'state': 'UNKNOWN'}
held = simulate(frozen, blocked_inputs, forecast, days[20])
assert held['cash_yuan'] == '90000.00' and held['nav_yuan'] == '100100.00' and held['curve'][-1]['receivable_yuan'] == '100.00'
blocked_paid = simulate(frozen, blocked_inputs, forecast, days[23])
assert blocked_paid['cash_yuan'] == '100080.00' and blocked_paid['entitlements'][0]['tax'] == '20.00'
buy_record = copy.deepcopy(inputs); buy_record['cash_events'][0].update(record_date=days[1], ex_date=days[2])
bought = simulate(frozen, buy_record, forecast, days[1])
assert len(bought['entitlements']) == 1 and bought['curve'][-1]['receivable_yuan'] == '100.00'
unpaid = simulate(frozen, buy_record, forecast, days[20])
assert unpaid['cash_yuan'] == '99980.00' and unpaid['nav_yuan'] == '100080.00' and unpaid['curve'][-1]['receivable_yuan'] == '100.00'
paid = simulate(frozen, buy_record, forecast, days[23])
assert paid['cash_yuan'] == paid['nav_yuan'] == '100080.00' and paid['curve'][-1]['receivable_yuan'] == '0.00'
assert sum(e['kind'] == 'CASH_DISTRIBUTION' for e in paid['events']) == 1
results = {kind: api_case(kind) for kind in ('membership', 'early-stop', 'deadline')}
print(json.dumps({'status': 'PASS', 'evidence_kind': 'METHOD_CASE', 'source_merge': '25d9b9ae48b94ea4603cc36ab3dbacc8200be248',
    'profile': str(profile), 'public_api_cases': results, 'literal_rights_cases': {'record_close_sold_no_rights': '100000.00',
        'blocked_exit_record_close_receivable': '100.00', 'record_date_buy_then_sold_unpaid_nav': '100080.00', 'payment_once_final_cash': '100080.00'},
    'provider_calls': 0, 'actual_forward_start': False}, indent=2))
