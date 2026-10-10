"""Persisted correction/as-of boundaries and a full isolated virtual build."""
import hashlib
import json
from datetime import datetime
from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from roll.accounts.ledger import encode
from roll.app import create_app
from roll.research.prospective import CollectionCommand


def batch(app, plan, instant, close='100', kind='REAL_ACQUISITION', failed=False):
    evidence = app.state.evidence
    raw = encode({'close': close, 'clock': instant}).encode()
    archive = evidence.archive(raw, 'RAW_RESPONSE', received_at=instant)
    fact = {'instrument': 'SSE:600362', 'group': 'DAILY', 'source_id': 'fixture', 'trade_date': '2026-10-12',
            'adjustment': 'RAW', 'close': close, 'raw_hash': archive['sha256'], 'available_at': instant,
            'errors': [], 'volume_unit': 'SHARE', 'completion_state': 'COMPLETE_REPORTED_HISTORICAL'}
    facts = [] if failed else [fact]
    buffer = BytesIO(); pq.write_table(pa.Table.from_pylist([{'payload': encode(f)} for f in facts]), buffer)
    parquet = evidence.archive(buffer.getvalue(), 'NORMALIZED_PARQUET', 'parquet')
    run_id = 'run-'+hashlib.sha256(raw).hexdigest()
    request_id = 'request-'+run_id; snapshot_id = 'snapshot-'+run_id
    request = {'request_id': request_id, 'purpose': 'RESEARCH', 'instruments': ['SSE:600362']}
    snapshot = {'snapshot_id': snapshot_id, 'run_id': run_id, 'request_id': request_id, 'created_at': instant,
                'facts': facts, 'archives': [archive], 'parquet': parquet, 'evidence_kind': kind,
                'adapter_version': 'framework-test-v1', 'observations': []}
    run = {'run_id': run_id, 'request_id': request_id, 'started_at': instant, 'finished_at': instant,
           'snapshot_id': snapshot_id, 'status': 'FAILED' if failed else 'COMPLETE', 'gaps': []}
    with app.state.ledger.connection() as db:
        db.execute('INSERT INTO data_requests VALUES(?,?)', (request_id, encode(request)))
        db.execute('INSERT INTO retrieval_runs VALUES(?,?,?)', (run_id, request_id, encode(run)))
        db.execute('INSERT INTO market_evidence_snapshots VALUES(?,?,?)', (snapshot_id, run_id, encode(snapshot)))
    return app.state.prospective.record(plan['plan_id'], run_id), archive


def test_asof_corrections_restarts_duplicates_and_integrity(tmp_path, monkeypatch):
    monkeypatch.setattr('roll.research.prospective.now', lambda: '2026-10-13T18:00:00+08:00')
    app = create_app(tmp_path)
    monkeypatch.setattr('roll.research.prospective.now', lambda: '2026-10-10T18:00:00+08:00')
    plan = app.state.prospective.start(CollectionCommand(instrument='SSE:600362', basis='明确自建前向证据库'))
    assert app.state.prospective.start(CollectionCommand(instrument='SSE:600362', basis='重复不重置')) == plan
    first, original = batch(app, plan, '2026-10-12T16:00:00+08:00')
    second, _ = batch(app, plan, '2026-10-13T16:00:00+08:00', close='101')
    batch(app, plan, '2026-10-12T17:00:00+08:00', close='100.50')
    monkeypatch.setattr('roll.research.prospective.now', lambda: '2026-10-13T18:00:00+08:00')
    pit = app.state.prospective
    assert pit.as_of(plan['plan_id'], datetime.fromisoformat('2026-10-12T15:59:59+08:00'))['versions'] == []
    saved = pit.as_of(plan['plan_id'], datetime.fromisoformat('2026-10-12T16:01:00+08:00'))
    assert saved['versions'][0]['fact']['close'] == '100'
    assert pit.as_of(plan['plan_id'], datetime.fromisoformat('2026-10-13T16:01:00+08:00'))['versions'][0]['fact']['close'] == '101'
    assert pit.record(plan['plan_id'], first['run_id']) == first
    assert len(pit.batches(plan['plan_id'])) == 3
    with pytest.raises(HTTPException) as error:
        batch(app, plan, '2026-10-09T16:00:00+08:00', close='90')
    assert error.value.status_code == 409
    with TestClient(create_app(tmp_path)) as client:
        replay = client.get('/api/research/collections/'+plan['plan_id']+'/as-of', params={'cutoff': '2026-10-12T16:01:00+08:00'}).json()
        assert replay == saved
        state = client.get('/api/research/collections/'+plan['plan_id']+'/readiness').json()
        assert state['real_recorded_sessions'] == 1 and not state['system_usable']
        assert client.post('/api/research/collections', json={'instrument': 'SSE:600362', 'basis': '不能回填', 'started_at': '2020-01-01'}).status_code == 422
        assert client.get('/api/research/collections/'+plan['plan_id']+'/as-of', params={'cutoff': '2026-10-12T16:00:00'}).status_code == 422
        original_path = tmp_path/original['path']; original_path.write_bytes(b'corrupt')
        assert client.get('/api/research/collections/'+plan['plan_id']+'/as-of', params={'cutoff': '2026-10-12T16:01:00+08:00'}).status_code == 409


def test_failed_and_method_batches_are_retained_without_real_support(tmp_path, monkeypatch):
    monkeypatch.setattr('roll.research.prospective.now', lambda: '2026-10-10T18:00:00+08:00')
    app = create_app(tmp_path)
    plan = app.state.prospective.start(CollectionCommand(instrument='SSE:600362', basis='test collection'))
    batch(app, plan, '2026-10-12T16:00:00+08:00', kind='METHOD_CASE')
    failed, _ = batch(app, plan, '2026-10-13T16:00:00+08:00', failed=True)
    monkeypatch.setattr('roll.research.prospective.now', lambda: '2026-10-13T18:00:00+08:00')
    assert failed['status'] == 'FAILED' and failed['fact_count'] == 0
    state = app.state.prospective.readiness(plan['plan_id'])
    assert state['batches'] == 2 and state['real_recorded_sessions'] == 0 and not state['system_usable']


def test_virtual_training_freeze_forecast_replay_and_admission(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        account = client.get('/api/account').json()
        response = client.post('/api/research/development-runs')
        assert response.status_code == 201, response.text
        run = response.json()
        assert run['status'] == 'ENGINEERING_COMPLETE', run
        assert all(count >= 20 for count in run['statistical_support']['calibration_per_class'].values())
        assert run['replay']['matches_original'] and run['sealed_consumed'] is False
        assert not run['system_usable'] and run['real_model_frozen'] is False
        assert client.post('/api/research/development-runs').json() == run
        pid = run['protocol_id']
        manifest = client.get('/api/research/protocols/'+pid+'/attempt-manifest').json()
        assert [a['category'] for a in manifest['attempts']] == ['PRIMARY_FIT', 'CALIBRATION']
        assert client.post('/api/research/protocols/'+pid+'/models', json={'purpose': 'RESEARCH', 'basis': '不能虚拟转真实'}).status_code == 409
        assert client.get('/api/research/protocols/'+pid+'/attempt-manifest').json() == manifest
        assert client.get('/api/account').json() == account
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/research/development-runs').json() == [run]
        assert client.post('/api/research/forecasts/'+run['forecast_id']+'/replay').json()['matches_original']


def test_virtual_build_refuses_existing_research_without_reset(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        protocol = client.post('/api/research/protocols', json={'basis': 'preserved real work'}).json()
        assert client.post('/api/research/development-runs').status_code == 409
        assert client.get('/api/research/development-runs').json() == []
        assert client.get('/api/research/protocols/'+protocol['protocol_id']).json() == protocol


def test_interrupted_virtual_run_is_retained_and_never_retried(tmp_path):
    app = create_app(tmp_path)
    prior = {'development_run_id': 'ticket19-synthetic-v1', 'status': 'RUNNING', 'evidence_kind': 'METHOD_CASE',
             'system_usable': False, 'capability': 'NOT_GRANTED', 'host_owner': {'pid': -1}}
    with app.state.ledger.connection() as db:
        db.execute('INSERT INTO research_development_runs VALUES(?,?)', (prior['development_run_id'], encode(prior)))
    with TestClient(create_app(tmp_path)) as client:
        value = client.post('/api/research/development-runs').json()
        assert value['status'] == 'INTERRUPTED' and not value['system_usable']
        assert client.get('/api/research/protocols').json() == []
