"""Explicit METHOD browser factory; never production configuration."""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
sys.path.insert(0, str(Path(__file__).parents[2] / 'src'))
sys.path.insert(0, str(Path(__file__).parents[1] / 'application'))
from roll.app import create_app
from test_actions import action_package
from capability_method_app import save_package, package
from test_funding import funding


def risk_package():
    import capability_method_app
    capability_method_app.ANCHOR = (datetime.now(timezone(timedelta(hours=8))) - timedelta(days=1)).replace(hour=15, minute=5, second=0, microsecond=0)
    # Same explicit controlled METHOD qualification clock as the API reduction
    # test; do not relabel yesterday's packet as current market evidence.
    import roll.decisions.capabilities
    import roll.decisions.actions
    clock = (capability_method_app.ANCHOR + timedelta(minutes=1)).isoformat()
    roll.decisions.capabilities.now = lambda: clock
    roll.decisions.actions.now = lambda: clock
    p = package()
    p['loss_facts'] = {**p['loss_facts'], 'baseline_assets': '130000.10', 'net_assets': '130000.10'}
    gates = ['DATA', 'RULE_QUANTITY', 'AUTHORIZATION', 'STRESS_EXECUTION', 'ONLINE_CONSISTENCY']
    p.update(candidate_kind='RISK_POLICY', gates={g: 'PASS' for g in gates}, required_gates=gates, allowed_actions=['REDUCE', 'EXIT'])
    p['deployment_fingerprints'] = {'policy': 'e' * 64}
    rule_id = 'SSE-MAIN-A-2026-07-06'
    p['action_packet'] = {'namespace': 'METHOD_ENGINEERING', 'as_of': p['required_as_of'], 'expires_at': p['expires_at'],
        'opportunities': [], 'loss_facts': p['loss_facts'], 'risk_inputs': {
            'policy': {'policy_id': 'risk-method', 'policy_fingerprint': 'e' * 64, 'authorization': {**funding()['authorization'], 'version': 1, 'loss_origin_at': '2026-10-07T02:00:00+00:00'},
                       'scope': p['scope'], 'rule_ids': {'SSE:600000': rule_id}},
            'required_as_of': p['required_as_of'], 'consumer_knowledge_cutoff': datetime.now(timezone.utc).isoformat(),
            'quotes': {'SSE:600000': {'last': '100', 'adjustment': 'RAW', 'currency': 'CNY', 'errors': [], 'upstream_at': p['required_as_of'],
                    'available_at': p['required_as_of'], 'method_status': 'NORMAL', 'evidence_kind': 'METHOD_CASE'}},
            'identities': {'SSE:600000': {'exchange': 'SSE', 'board': 'MAIN', 'instrument_type': 'STOCK'}},
            'rules': {'SSE:600000': {'implementation_status': 'ADAPTED', 'rule_id': rule_id, 'normal_price_limit_percent': '10', 'price_tick_yuan': '.01'}},
            'calendars': {'SSE:600000': {'is_trading_day': True}}, 'evidence_kind': 'METHOD_CASE'}}
    return p


def factory():
    if os.environ.get('ROLL_ENV') != 'test':
        raise RuntimeError('Explicit METHOD browser factory requires ROLL_ENV=test')
    directory = Path(os.environ['ROLL_DATA_DIR'])
    case = os.environ.get('ROLL_ACTION_CASE', 'qualified')
    if case not in {'qualified', 'stale', 'permission', 'sellable'}:
        raise RuntimeError('Unsupported explicit METHOD browser case')
    p = risk_package() if case == 'sellable' else action_package()
    if case == 'stale':
        p['action_packet']['loss_facts'] = {**p['loss_facts'], 'valuation_status': 'STALE', 'net_assets': None}
    file = save_package(directory / 'qualification.json', p)
    return create_app(directory, capability_method_file=file)
