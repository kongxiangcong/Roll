"""Retained failing METHOD profile, public queries, supplemental calculation diff."""
import json
import sys
from datetime import datetime
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.research.shadow import simulate

directory = Path(sys.argv[1]).resolve()
assert directory.name == 'test_mature_settlement_only_sc0'
with TestClient(create_app(directory, review_clock=lambda: datetime.fromisoformat('2026-01-01T00:00:00+08:00'))) as client:
    protocol = client.get('/api/research/protocols').json()[0]
    frozen = client.get('/api/research/protocols/' + protocol['protocol_id'] + '/complete-freezes').json()[0]
    path = '/api/research/complete-freezes/' + frozen['freeze_id'] + '/forward'
    state = client.get(path).json()
    replay = client.post(path + '/replay').json()
    assessment = state['latest_assessment']
    samples = [sample for sample in state['samples']
               if datetime.fromisoformat(sample['recorded_at']) <= datetime.fromisoformat(assessment['cutoff'])]
    result = simulate(frozen, assessment['inputs'], [sample['forecast'] for sample in samples],
                      datetime.fromisoformat(assessment['cutoff']).date().isoformat())
    result['revision'] = assessment['shadow']['revision']
    differences = {key: {'saved': assessment['shadow'][key], 'replayed': value}
                   for key, value in result.items() if value != assessment['shadow'][key]}
    receipt = {'replay': replay, 'samples': [{'sample_id': sample['sample_id'],
        'trading_date': sample['trading_date'], 'recorded_at': sample['recorded_at']} for sample in state['samples']],
        'assessment_id': assessment['assessment_id'], 'assessment_cutoff': assessment['cutoff'],
        'saved_shadow_revision': assessment['shadow']['revision'], 'differences': differences}
    Path(sys.argv[2]).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))
    assert replay['matches_original'] is True, 'Retained public replay reproduces the observed mismatch'
