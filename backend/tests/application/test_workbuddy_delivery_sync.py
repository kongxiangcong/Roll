"""Actual delivery integration: append/replay/idempotence and recovery references."""
import importlib.util
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from roll.app import create_app
from roll.runtime.backups import references
from test_research_acquisition_import import acquire, provider


def load_sync():
    path = Path(__file__).resolve().parents[3] / 'scripts/sync_ticket19_delivery.py'
    spec = importlib.util.spec_from_file_location('workbuddy_sync', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_delivery_sync_appends_exact_coverage_without_training_and_reuses_originals(tmp_path, monkeypatch):
    module = load_sync()
    _, parsed, index, contents, audit = module.verify(module.DEFAULT_PACKAGE)
    assert audit['corrected_requested_exchange_sessions'] == 1945
    assert audit['unexplained_missing_dates'] == []
    assert len(audit['suspension_placeholder_dates']) == 8
    assert audit['requested_observed_dates'] == 1937
    assert audit['cross_source_validation']['host_precision_mismatch_count'] == 40
    assert audit['cross_source_validation']['ohlc_mismatch_dates'] == []
    assert len(audit['dividend_announcement_date_disagreements']) == 5
    assert len(audit['host_supplemented_missing_calendar_originals']) == 9
    app = create_app(tmp_path, market_transport=httpx.MockTransport(provider))
    with TestClient(app) as client:
        run = acquire(client)
        response = client.post('/api/research/datasets', json={'source_run_id':run['run_id'],'basis':'Isolated METHOD identity for delivery integration only'})
        assert response.status_code == 201, response.text
    monkeypatch.setattr(module.httpx, 'Client', lambda **kwargs:TestClient(app))
    first = module.sync(tmp_path,'http://testserver',parsed,index,contents,audit)
    second = module.sync(tmp_path,'http://testserver',parsed,index,contents,audit)
    wind = module.sync(tmp_path,'http://testserver',parsed,index,contents,audit,source_id='SRC-WIND')
    assert first['dataset_id'] == second['dataset_id']
    assert not first['idempotent_reuse'] and second['idempotent_reuse']
    assert first['dataset_coverage']['session_count'] == 1916
    assert first['dataset_coverage']['status_reported_dates'] == 1
    assert first['dataset_coverage']['company_action_rows'] == 8
    assert wind['dataset_coverage']['session_count'] == 1937
    assert wind['dataset_coverage']['company_action_rows'] == 7
    assert wind['dataset_id'] != first['dataset_id']
    assert first['attempt_manifests_unchanged']
    assert first['account_and_old_research_state_unchanged']
    with module.ExistingLedger(tmp_path).connection() as db:
        refs = references(db,tmp_path)
        assert {r['sha256'] for r in refs} >= {module.sha(b) for b in contents.values()}
        import json
        snapshot=json.loads(db.execute('SELECT value FROM market_evidence_snapshots WHERE id=?',(wind['snapshot_id'],)).fetchone()[0])
        daily=[r for r in snapshot['facts'] if r['group']=='DAILY']
        assert len({r['trade_date'] for r in daily})==len(daily)
        assert {r['source_id'] for r in daily}=={'SRC-WIND'}
        placeholders=[r for r in snapshot['facts'] if r['group']=='SUSPENSION_PLACEHOLDER']
        assert len(placeholders)==8 and all(r['volume_shares'] is None and not r['model_daily_input_allowed'] for r in placeholders)
        assert len(snapshot['facts'])==7031
        assert next(r for r in snapshot['facts'] if r['record_id']=='CA-WIND-DIV-Q4 FY2023')['group']=='OUT_OF_SCOPE_ACTION_VERSION'
    with TestClient(create_app(tmp_path)) as client:
        dataset = client.get('/api/research/datasets/'+first['dataset_id']).json()
        assert all(v['state'] == 'NOT_PREREGISTERED' for v in dataset['partitions'].values())
        assert client.get('/api/research/datasets/'+first['dataset_id']+'/partitions/DEVELOPMENT').status_code == 409
        assert client.get('/api/research/datasets/'+first['dataset_id']+'/partitions/SEALED').status_code == 403


def test_altered_zip_is_refused_before_any_database_import(tmp_path):
    module = load_sync()
    package = tmp_path/'ticket19-data-delivery'
    package.with_suffix('.zip').write_bytes(b'altered delivery')
    import pytest
    with pytest.raises(ValueError,match='Unexpected delivery ZIP'):
        module.verify(package)
    assert not (tmp_path/'roll.sqlite3').exists()
