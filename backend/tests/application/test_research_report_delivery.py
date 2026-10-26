"""Real API/SQLite/isolated renderer, synthetic prices clearly remain METHOD."""
import importlib.util
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from roll.app import create_app
from test_shadow import setup, freeze

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('delivery', ROOT/'scripts/research_report_delivery.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


def test_cal_report_delivery_and_restart(tmp_path):
    if not os.environ.get('ROLL_QUANTSTATS_PYTHON'):
        pytest.skip('Requires pinned isolated QuantStats runtime')
    with TestClient(create_app(tmp_path)) as client:
        _, protocol, model, _ = setup(client, tmp_path)
        frozen = freeze(client, protocol, model).json()
        result = delivery.deliver(client, frozen['freeze_id'])
        assert result['evidence_kind'] == 'METHOD_CASE'
        assert result['forecast_count_created'] > 20
        assert result['replay']['matches_original']
        report = result['performance_report']
        assert report['capability'] == 'NOT_GRANTED'
        assert report['namespaces']['SHADOW']['benchmark_status'] == 'SAVED_MATCHED_CLOSE_INTERVALS'
        assert report['library']['version'] == '0.0.86'
        assert client.get('/api/research/models/'+model['model_run_id']).json() == model
        with pytest.raises(ValueError, match='NEW_FREEZE_REQUIRED'):
            delivery.deliver(client, frozen['freeze_id'])
        export = client.get('/api/research/performance-reports/'+report['performance_report_id']+'/export')
        assert export.status_code == 200 and b'<svg' in export.content
    with TestClient(create_app(tmp_path)) as client:
        again = delivery.deliver(client, frozen['freeze_id'], render_only=True)
        assert again['performance_report'] == report
        assert again['forecast_count_created'] == 0


def test_changed_shadow_code_keeps_original_saved_but_refuses_replay(tmp_path, monkeypatch):
    from roll.research import shadow
    with TestClient(create_app(tmp_path)) as client:
        _, protocol, model, dates = setup(client, tmp_path)
        frozen = freeze(client, protocol, model).json()
        path = '/api/research/shadow/' + frozen['freeze_id']
        state = client.post(path+'/advance', json={'through_date': dates[110],
            'forecast_ids': [], 'expected_revision': 0}).json()
        monkeypatch.setattr(shadow, 'shadow_code', lambda: 'new-version')
        assert client.get(path).json() == state
        assert client.post(path+'/replay').status_code == 409
        assert client.post(path+'/advance', json={'through_date': dates[111],
            'forecast_ids': [], 'expected_revision': 1}).status_code == 409
