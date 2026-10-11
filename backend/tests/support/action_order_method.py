"""One explicit paired host METHOD fixture, never a production supplier."""
from copy import deepcopy
from test_actions import action_package
from test_lifecycle_composition import risk_package


def paired_package():
    profit = action_package()
    profit['scope']['instruments'] = ['SSE:600000', 'SSE:600001', 'SSE:600002']
    profit['current_data']['instruments'] = profit['scope']['instruments'][:]
    profit['material_id'] = profit['review']['material_id'] = 'ordering-profit-material'
    profit['review_run_id'] = 'ordering-profit-review'
    # Literal confirmed cash100000.10 +300 shares at100, no flows/PnL.
    profit['loss_facts'].update(baseline_assets='130000.10', net_assets='130000.10')
    packet = profit['action_packet']
    packet['loss_facts'] = deepcopy(profit['loss_facts'])
    template = packet['opportunities'][0]
    packet['opportunities'] = [
        {**template, 'instrument': 'SSE:600001', 'forecast_id': 'new-1', 'probability': '.80', 'price_lower_yuan': '40.00', 'price_upper_yuan': '50.00'},
        {**template, 'instrument': 'SSE:600002', 'forecast_id': 'new-2', 'probability': '.70', 'price_lower_yuan': '40.00', 'price_upper_yuan': '50.00'},
        {**template, 'instrument': 'SSE:600000', 'forecast_id': 'held', 'probability': '.50', 'price_lower_yuan': '100.00', 'price_upper_yuan': '110.00'},
    ]
    risk = risk_package()
    risk['material_id'] = risk['review']['material_id'] = 'ordering-risk-material'
    risk['review_run_id'] = 'ordering-risk-review'
    risk['material_fingerprint'] = risk['review']['material_fingerprint'] = '9' * 64
    for field in ['account_version', 'scope_kind', 'scope_id', 'required_as_of', 'effective_at', 'expires_at', 'review_due_at', 'current_data', 'loss_facts']:
        risk[field] = deepcopy(profit[field])
    for field in ['as_of', 'expires_at', 'loss_facts']:
        risk['action_packet'][field] = deepcopy(packet[field])
    packet['risk_inputs'] = deepcopy(risk['action_packet']['risk_inputs'])
    profit['risk_qualification'] = risk
    return profit


def grant_command(value, key):
    return {'material_id': value['material_id'], 'review_run_id': value['review_run_id'],
        'expected_material_fingerprint': value['material_fingerprint'], 'deployment_fingerprints': value['deployment_fingerprints'],
        'scope': value['scope'], 'allowed_actions': ['BUY'] if value['candidate_kind'] == 'PROFIT_MODEL' else ['REDUCE', 'EXIT'],
        'expected_account_version': 2, 'expected_funding_version': 1,
        'effective_at': value['effective_at'], 'expires_at': value['expires_at'], 'required_as_of': value['required_as_of'],
        'idempotency_key': key, 'basis': 'Explicit independent METHOD qualification; no actual authority'}
