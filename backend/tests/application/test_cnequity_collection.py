"""Source boundaries, quarantine, persisted revisions and offline replay; no live data claim."""
import base64
from datetime import datetime
import json
import time

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from roll.accounts.ledger import encode
from roll.app import create_app
from roll.market.collection_cleaning import clean_rows
from roll.market.collection_sources import CNE_COMMIT, CollectionSources, SourcePolicyCommand
from roll.market.cnequity import CNEquityCollection
from roll.market.directory import WatchCommand
from roll.research.prospective import CollectionCommand


def source(app, identifier='cnequity-eastmoney-daily'):
    return app.state.collection_sources.policy(identifier)


def row(close=11):
    return {'symbol': '600362.SH', 'trade_date': '2026-10-09', 'open': 11,
            'high': 12, 'low': 10, 'close': close, 'volume': 1000, 'amount': 11000}


def app_at(tmp_path, monkeypatch, instant='2026-10-12T16:10:00+08:00'):
    for module in ['roll.market.evidence', 'roll.market.cnequity', 'roll.market.collection_sources', 'roll.research.prospective']:
        monkeypatch.setattr(module+'.now', lambda: instant)
    # Controlled transport is marked METHOD, including subprocess exports.
    app = create_app(tmp_path, market_transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    app.state.market.watch(WatchCommand(operation='ADD', instrument='SSE:600362', expected_list_version=app.state.market.listing()['version']))
    return app


def payload(command, rows, code=None):
    body = encode(rows).encode()
    return {'commit': CNE_COMMIT, 'source_id': command['source_id'], 'rows': rows,
            'calls': 1, 'error_code': code,
            'captures': [{'kind': 'RAW_RESPONSE', 'url': 'https://push2his.eastmoney.com/api/qt/stock/kline/get',
                          'body_b64': base64.b64encode(body).decode()}]}


def test_cleaning_units_bad_numbers_scope_conflicting_duplicates(tmp_path, monkeypatch):
    app = app_at(tmp_path, monkeypatch)
    spec = source(app)
    archives = [{'sha256': 'a'*64}]
    args = [spec, 'SSE:600362', archives, '2026-10-12T16:10:00+08:00', '2026-08-28', '2026-10-12', {'is_trading_day': True}]
    facts, rejected = clean_rows([row(), row()], *args)
    assert len(facts) == 1 and not rejected
    assert facts[0]['volume_shares'] == '1000' and facts[0]['amount_yuan'] == '11000'
    assert facts[0]['model_daily_input_allowed'] and not facts[0]['historical_pit_claim']
    for bad in [{**row(), 'volume': 100000}, {**row(), 'close': float('nan')},
                {**row(), 'symbol': '600000.SH'}, {**row(), 'amount': None},
                {**row(), 'volume': 0, 'amount': 0}, {**row(), 'trade_date': '2020-01-01'}]:
        good, quarantine = clean_rows([bad], *args)
        assert not good and quarantine[0]['errors']
    facts, rejected = clean_rows([row(), row(11.5)], *args)
    assert facts == [] and len(rejected) == 2


def test_status_and_rights_unknowns_never_filled(tmp_path, monkeypatch):
    app = app_at(tmp_path, monkeypatch)
    archives = [{'sha256': 'a'*64}]
    sample = {'symbol': '600362.SH', 'trade_date': '2026-10-12', 'status': 'normal', 'is_trading': True, 'risk_warning': None}
    args = ['SSE:600362', archives, '2026-10-12T16:10:00+08:00', '2026-08-28', '2026-10-12']
    facts, rejected = clean_rows([sample], source(app, 'cnequity-eastmoney-status'), *args, {'is_trading_day': True})
    assert not rejected and facts[0]['risk_warning'] is None and facts[0]['ex_rights'] is None
    assert facts[0]['listing_stage'] is None and facts[0]['st_subtype'] is None
    assert clean_rows([sample], source(app, 'cnequity-eastmoney-status'), *args, {'is_trading_day': False})[1]
    action = {'symbol': '600362.SH', 'ex_date': '2026-10-09', 'action_type': 'allotment', 'allotment_ratio': .2, 'allotment_price': None}
    facts, rejected = clean_rows([action], source(app, 'cnequity-eastmoney-actions'), *args, {'is_trading_day': True})
    assert not rejected and facts[0]['allotment_price'] is None and facts[0]['account_receipt'] is None
    assert 'NO_ACCOUNT_LEDGER_AUTHORITY' in facts[0]['limitations']


def test_policies_persist_optimistic_changes_cooldown_and_scope(tmp_path, monkeypatch):
    app = app_at(tmp_path, monkeypatch)
    service = app.state.collection_sources
    identifier = 'cnequity-eastmoney-daily'
    changed = service.change(identifier, SourcePolicyCommand(enabled=False, expected_revision=1, basis='暂停故障来源'))
    assert changed['revision'] == 2 and service.access(identifier, 'SSE:600362') == 'SOURCE_DISABLED'
    with pytest.raises(HTTPException):
        service.change(identifier, SourcePolicyCommand(enabled=True, expected_revision=1, basis='过期写入'))
    service.change(identifier, SourcePolicyCommand(enabled=True, expected_revision=2, basis='继续'))
    for _ in range(3):
        service.outcome(identifier, False, 'NETWORK_ERROR', 'failed-run')
    assert service.access(identifier, 'SSE:600362') == 'SOURCE_COOLDOWN'
    assert service.access(identifier, 'SSE:600000') == 'SOURCE_SCOPE_NOT_ALLOWED'
    restarted = CollectionSources(app.state.evidence)
    assert restarted.policy(identifier)['health']['consecutive_failures'] == 3
    assert restarted.policy(identifier)['revision'] == 3
    service.outcome(identifier, True, 'ACQUIRED', 'new-run')
    assert service.access(identifier, 'SSE:600362') is None
    assert {p['upstream'] for p in service.listing() if 'eastmoney' in p['id']} == {'EASTMONEY'}


def test_comparison_retains_conflicts_without_winner(tmp_path, monkeypatch):
    app = app_at(tmp_path, monkeypatch)
    service = app.state.collection_sources
    versions = [{'fact': {'instrument': 'SSE:600362', 'group': 'DAILY', 'trade_date': '2026-10-09',
                'adjustment': 'RAW', 'source_id': sid, 'close': close, 'volume_shares': volume, 'raw_hash': sid}}
                for sid, close, volume in [('eastmoney-daily', '11', '1000'), ('cnequity-eastmoney-daily', '11', '1100')]]
    report = service.compare_daily('sample-plan', versions)
    assert report['source_winner'] is None
    assert report['differences'][0]['fields']['volume_shares'] == {'left': '1000', 'right': '1100'}
    assert report['differences'][0]['independence'] == 'NOT_ASSERTED'
    assert service.comparisons('sample-plan') == [report]


def test_archived_corrections_quarantine_asof_and_restart(tmp_path, monkeypatch):
    app = app_at(tmp_path, monkeypatch)
    pit = app.state.prospective
    plan = pit.start(CollectionCommand(instrument='SSE:600362', basis='test'))
    worker = CNEquityCollection(app.state.evidence, pit.sources)
    spec = source(app)
    monkeypatch.setattr('roll.market.cnequity.acquire', lambda cmd: payload(cmd, [row(), {**row(), 'trade_date': '2026-10-08', 'volume': 100000}]))
    run = worker.one(plan, spec, time.monotonic()+30)
    batch = pit.record(plan['plan_id'], run['run_id'])
    assert batch['fact_count'] == 1 and run['status'] == 'PARTIAL'
    report = pit.sources.reports()[0]
    assert report['accepted_rows'] == 1 and len(report['quarantined_rows']) == 1
    assert report['evidence_kind'] == 'METHOD_CASE'
    for module in ['roll.market.evidence', 'roll.market.cnequity', 'roll.market.collection_sources', 'roll.research.prospective']:
        monkeypatch.setattr(module+'.now', lambda: '2026-10-13T16:10:00+08:00')
    monkeypatch.setattr('roll.market.cnequity.acquire', lambda cmd: payload(cmd, [row(11.5)]))
    second = worker.one(plan, spec, time.monotonic()+30)
    pit.record(plan['plan_id'], second['run_id'])
    first_asof = pit.as_of(plan['plan_id'], datetime.fromisoformat('2026-10-12T17:00:00+08:00'))
    latest = pit.as_of(plan['plan_id'], datetime.fromisoformat('2026-10-13T16:10:00+08:00'))
    assert first_asof['versions'][0]['fact']['close'] == '11'
    assert latest['versions'][0]['fact']['close'] == '11.5'
    assert pit.record(plan['plan_id'], run['run_id']) == batch
    monkeypatch.setattr('roll.market.cnequity.acquire', lambda cmd: (_ for _ in ()).throw(AssertionError('offline')))
    assert app.state.evidence.replay(second['run_id'])['network_calls'] == 0
    assert pit.sources.integrity()['consistent']
    assert not pit.readiness(plan['plan_id'])['system_usable'] and pit.readiness(plan['plan_id'])['real_recorded_sessions'] == 0
    restarted = create_app(tmp_path)
    assert restarted.state.prospective.as_of(plan['plan_id'], datetime.fromisoformat('2026-10-12T17:00:00+08:00')) == first_asof
    raw = app.state.evidence.raw(latest['versions'][0]['raw_hash'])
    raw.write_bytes(b'corrupt')
    assert not pit.sources.integrity()['consistent']
    with pytest.raises(HTTPException):
        pit.as_of(plan['plan_id'], datetime.fromisoformat('2026-10-13T16:10:00+08:00'))


def test_corporate_correction_retains_old_version_and_disabled_never_calls(tmp_path, monkeypatch):
    app = app_at(tmp_path, monkeypatch)
    pit = app.state.prospective
    plan = pit.start(CollectionCommand(instrument='SSE:600362', basis='test'))
    worker = CNEquityCollection(app.state.evidence, pit.sources)
    identifier = 'cnequity-eastmoney-actions'
    action = {'symbol': '600362.SH', 'ex_date': '2026-10-09', 'action_type': 'cash_dividend', 'cash_dividend': .2}
    monkeypatch.setattr('roll.market.cnequity.acquire', lambda cmd: payload(cmd, [action]))
    run = worker.one(plan, source(app, identifier), time.monotonic()+30)
    pit.record(plan['plan_id'], run['run_id'])
    for module in ['roll.market.evidence', 'roll.market.cnequity', 'roll.market.collection_sources', 'roll.research.prospective']:
        monkeypatch.setattr(module+'.now', lambda: '2026-10-13T16:10:00+08:00')
    action = {**action, 'cash_dividend': .3}
    second = worker.one(plan, source(app, identifier), time.monotonic()+30)
    pit.record(plan['plan_id'], second['run_id'])
    assert pit.as_of(plan['plan_id'], datetime.fromisoformat('2026-10-12T17:00:00+08:00'))['versions'][0]['fact']['cash_dividend'] == '0.2'
    latest = pit.as_of(plan['plan_id'], datetime.fromisoformat('2026-10-13T16:10:00+08:00'))
    assert len(latest['versions']) == 1 and latest['versions'][0]['fact']['cash_dividend'] == '0.3'
    pit.sources.change(identifier, SourcePolicyCommand(enabled=False, expected_revision=1, basis='停止'))
    monkeypatch.setattr('roll.market.cnequity.acquire', lambda cmd: (_ for _ in ()).throw(AssertionError('disabled source called')))
    skipped = worker.one(plan, source(app, identifier), time.monotonic()+30)
    assert skipped['network_calls'] == 0 and skipped['gaps'][0]['code'] == 'SOURCE_DISABLED'


def test_recovery_registers_completed_host_snapshot_without_network(tmp_path, monkeypatch):
    app = app_at(tmp_path, monkeypatch)
    pit = app.state.prospective
    plan = pit.start(CollectionCommand(instrument='SSE:600362', basis='test'))
    monkeypatch.setattr('roll.market.cnequity.acquire', lambda cmd: payload(cmd, [row()]))
    run = CNEquityCollection(app.state.evidence, pit.sources).one(plan, source(app), time.monotonic()+30)
    assert pit.batches(plan['plan_id']) == []
    monkeypatch.setattr('roll.market.cnequity.acquire', lambda cmd: (_ for _ in ()).throw(AssertionError('recovery network')))
    restarted = create_app(tmp_path)
    batches = restarted.state.prospective.batches(plan['plan_id'])
    assert len(batches) == 1 and batches[0]['run_id'] == run['run_id']
    assert batches[0]['fact_count'] == 1
    assert restarted.state.collection_sources.integrity()['consistent']


def test_sqlite_fact_tampering_rejected_even_with_valid_raw_hash(tmp_path, monkeypatch):
    app = app_at(tmp_path, monkeypatch)
    pit = app.state.prospective
    plan = pit.start(CollectionCommand(instrument='SSE:600362', basis='test'))
    monkeypatch.setattr('roll.market.cnequity.acquire', lambda cmd: payload(cmd, [row()]))
    run = CNEquityCollection(app.state.evidence, pit.sources).one(plan, source(app), time.monotonic()+30)
    pit.record(plan['plan_id'], run['run_id'])
    with app.state.ledger.connection() as db:
        value = json.loads(db.execute('SELECT value FROM pit_fact_versions').fetchone()[0])
        value['fact']['close'] = '999'
        db.execute('UPDATE pit_fact_versions SET value=?', (encode(value),))
    assert app.state.collection_sources.integrity()['sqlite'] == 'ok'
    assert not app.state.collection_sources.integrity()['consistent']
    with pytest.raises(HTTPException):
        pit.as_of(plan['plan_id'], datetime.fromisoformat('2026-10-12T16:10:00+08:00'))


def test_empty_event_query_is_successful_without_inventing_events(tmp_path, monkeypatch):
    app = app_at(tmp_path, monkeypatch)
    pit = app.state.prospective
    plan = pit.start(CollectionCommand(instrument='SSE:600362', basis='test'))
    monkeypatch.setattr('roll.market.cnequity.acquire', lambda cmd: payload(cmd, []))
    identifier = 'cnequity-eastmoney-actions'
    run = CNEquityCollection(app.state.evidence, pit.sources).one(plan, source(app, identifier), time.monotonic()+30)
    batch = pit.record(plan['plan_id'], run['run_id'])
    assert run['status'] == 'COMPLETE' and run['gaps'] == [] and batch['fact_count'] == 0
    assert set(run['roll_code_sha256']) == {'cnequity.py', 'cnequity_process.py', 'collection_cleaning.py'}
    saved = app.state.evidence.get('market_evidence_snapshots', run['snapshot_id'])
    assert saved['roll_code_sha256'] == run['roll_code_sha256']
    assert source(app, identifier)['health']['state'] == 'ACQUIRED'
    assert pit.sources.integrity()['consistent']
    assert not pit.readiness(plan['plan_id'])['system_usable']
    with TestClient(app) as client:
        assert client.get('/api/research/collection-cleaning').json()[0]['accepted_rows'] == 0
        assert client.post('/api/research/collection-integrity').json()['consistent']
        policy = '/api/research/collection-sources/'+identifier+'/policy'
        assert client.post(policy, json={'enabled': False, 'expected_revision': 1, 'basis': '暂停',
                                         'endpoint': 'https://other.invalid'}).status_code == 422
        assert client.post(policy, json={'enabled': False, 'expected_revision': 1, 'basis': '暂停'}).status_code == 200
        assert client.post(policy, json={'enabled': True, 'expected_revision': 1, 'basis': '旧配置'}).status_code == 409
