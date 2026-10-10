"""Public API version-boundary receipt; isolated METHOD runtime only."""
import json
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from roll.app import create_app

sys.path.insert(0, str(Path.cwd() / 'backend/tests/application'))
from test_shadow import setup, freeze, high_forecasts

directory = Path(sys.argv[2]).resolve()
receipt_path = directory / 'public-receipt.json'
with TestClient(create_app(directory)) as client:
    if sys.argv[1] == 'prepare':
        _, protocol, model, dates = setup(client, directory)
        frozen = freeze(client, protocol, model).json()
        forecast = high_forecasts(client, model)[0]
        path = '/api/research/shadow/' + frozen['freeze_id']
        response = client.post(path + '/advance', json={
            'through_date': forecast['observation_cutoff'][:10],
            'forecast_ids': [forecast['forecast_id']], 'expected_revision': 0})
        assert response.status_code == 201, response.text
        state = response.json()
        assert client.post(path + '/replay').json()['matches_original'] is True
        receipt = {'frozen': frozen, 'state': state, 'next_day': dates[120]}
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding='utf-8')
        print(json.dumps({'mode': 'prepare', 'freeze_id': frozen['freeze_id'],
                          'shadow_code': frozen['fingerprints']['shadow_code'], 'replay': True}))
    else:
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        frozen, state = receipt['frozen'], receipt['state']
        path = '/api/research/shadow/' + frozen['freeze_id']
        assert client.get('/api/research/complete-freezes/' + frozen['freeze_id']).json() == frozen
        assert client.get(path).json() == state
        replay = client.post(path + '/replay')
        advance = client.post(path + '/advance', json={
            'through_date': receipt['next_day'], 'forecast_ids': [], 'expected_revision': 1})
        assert replay.status_code == advance.status_code == 409
        assert client.get(path).json() == state
        assert client.get('/api/account').json()['version'] == 0
        assert client.get('/api/research/protocols/' + frozen['protocol_id']).json()['forward_started_at'] is None
        print(json.dumps({'mode': 'check', 'freeze_id': frozen['freeze_id'],
                          'old_manifest_unchanged': True, 'old_state_unchanged': True,
                          'replay_status': replay.status_code, 'replay_reason': replay.json()['detail'],
                          'advance_status': advance.status_code, 'advance_reason': advance.json()['detail'],
                          'actual_account_version': 0, 'actual_forward_started_at': None}))
