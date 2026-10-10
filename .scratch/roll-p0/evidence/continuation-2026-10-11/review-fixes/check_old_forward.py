"""Public old-forward-method refusal, original immutable archives retained."""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app

directory = Path(sys.argv[1]).resolve()
assert directory.name == 'test_mature_settlement_only_sc0'
with TestClient(create_app(directory, review_clock=lambda: datetime.fromisoformat('2026-01-01T00:00:00+08:00'))) as client:
    protocol = client.get('/api/research/protocols').json()[0]
    frozen = client.get('/api/research/protocols/' + protocol['protocol_id'] + '/complete-freezes').json()[0]
    path = '/api/research/complete-freezes/' + frozen['freeze_id'] + '/forward'
    before = client.get(path).json()
    replay = client.post(path + '/replay')
    settle = client.post(path + '/settle', json={'basis': 'Changed adapter requires successor, never rewrite old inputs'})
    assert replay.status_code == settle.status_code == 409
    assert replay.json()['detail'] == settle.json()['detail'] == 'FORWARD_FROZEN_COMPUTATION_CHANGED_SUCCESSOR_REQUIRED'
    after = client.get(path).json()
    assert before['samples'] == after['samples'] and before['latest_assessment'] == after['latest_assessment']
    archive = before['latest_assessment']['archive']
    assert hashlib.sha256(client.get('/api/data/archives/' + archive['sha256']).content).hexdigest() == archive['sha256']
    receipt = {'freeze_id': frozen['freeze_id'], 'old_samples_unchanged': True, 'old_assessment_unchanged': True,
        'old_assessment_sha256': archive['sha256'], 'replay_status': replay.status_code, 'settle_status': settle.status_code,
        'reason': replay.json()['detail'], 'actual_account_version': client.get('/api/account').json()['version'],
        'actual_forward_started_at': after['forward_started_at']}
    assert receipt['actual_account_version'] == 0 and receipt['actual_forward_started_at'] is None
    Path(sys.argv[2]).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt))
