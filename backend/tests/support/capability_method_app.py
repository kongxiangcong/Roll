"""Explicit isolated host factory; unavailable through production HTTP."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).parents[2] / 'src'))

from roll.accounts.ledger import encode
from roll.app import create_app

ANCHOR = datetime.now(timezone.utc).replace(microsecond=0)


def package():
    return {'namespace': 'METHOD_ENGINEERING', 'material_id': 'method-material', 'review_run_id': 'method-codex-review',
            'material_fingerprint': 'a' * 64, 'candidate_kind': 'PROFIT_MODEL', 'protocol_id': 'method-protocol',
            'complete_protocol_fingerprint': 'd' * 64,
            'validation_id': 'method-validation', 'validation_verdict': 'PASS', 'preliminary': False,
            'experiment_status': 'CLOSED', 'incomplete_checks': [], 'required_gates': [f'G{i}' for i in range(1, 8)],
            'gates': {f'G{i}': 'PASS' for i in range(1, 8)},
            'review': {'backend': 'CODEX', 'status': 'COMPLETE', 'material_id': 'method-material',
                       'material_fingerprint': 'a' * 64, 'blocking_issues_resolved': True, 'host_unresolved_gate_evidence': [],
                       'issues': [], 'reproduction': {'matches_original': True, 'network_calls': 0}},
            'deployment_fingerprints': {'model': 'b' * 64, 'calibrator': 'c' * 64},
            'scope': {'instruments': ['SSE:600000'], 'market': 'SSE', 'board': 'MAIN', 'frequency': 'DAILY', 'horizon': 20},
            'allowed_actions': ['BUY', 'ADD', 'HOLD', 'REDUCE', 'EXIT', 'WAIT'], 'execution': {'version': 'method-daily-v1'},
            'effective_at': (ANCHOR - timedelta(seconds=20)).isoformat(), 'required_as_of': ANCHOR.isoformat(),
            'expires_at': (ANCHOR + timedelta(days=1)).isoformat(), 'review_due_at': (ANCHOR + timedelta(days=1)).isoformat(),
            'account_version': 2, 'scope_kind': 'ACCOUNT', 'scope_id': 'account-1',
            'current_data': {'as_of': ANCHOR.isoformat(), 'instruments': ['SSE:600000'], 'status': 'COMPLETE'},
            'loss_facts': {'scope_kind': 'ACCOUNT', 'scope_id': 'account-1', 'baseline_account_version': 2,
                'origin_at': '2026-10-07T02:00:00+00:00', 'as_of': ANCHOR.isoformat(), 'facts_version': 'isolated-loss',
                'valuation_status': 'COMPLETE', 'baseline_assets': '100000.10', 'net_assets': '100000.10',
                'external_in': '0.00', 'external_out': '0.00', 'realized_pnl': '0.00', 'unrealized_pnl': '0.00',
                'income': '0.00', 'fees': '0.00', 'pending_income_delta': '0.00', 'pending_expense_delta': '0.00'}}


def save_package(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = encode(value).encode()
    path.write_text(encode({'sha256': hashlib.sha256(raw).hexdigest(), 'package': value}), encoding='utf-8')
    return path


def factory():
    directory = Path(os.environ['ROLL_DATA_DIR'])
    file = save_package(directory / 'isolated-qualification.json', package())
    return create_app(directory, capability_method_file=file)
