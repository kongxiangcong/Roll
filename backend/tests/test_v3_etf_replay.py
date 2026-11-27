"""Replay a local ETF report through the application and command line."""

import json
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import pytest

from roll.v3.cli import run
from roll.v3.web import create_app


DAY = '2026-11-26'
PREVIOUS = '2026-11-25'
DEMO_CLOSE = '2026-11-26T20:30:00+08:00'
NEXT_MORNING = '2026-11-27T10:00:00+08:00'


def observation(symbol, series, day, value, received_at=DEMO_CLOSE, **extra):
    fallback = 'sse' if symbol.endswith('.SH') else 'szse'
    source = extra.pop('source', fallback if series == 'etf_shares' else 'fuyao')
    return {
        'symbol': symbol, 'series': series, 'trade_date': day, 'source': source,
        'source_ref': f'https://example.org/{source}/{day}', 'available_evidence': '合成演示记录',
        'received_at': received_at, 'unit': {'etf_shares': '份', 'etf_nav': '元/份'}[series],
        'payload': {'value': value, 'verified': True}, **extra,
    }


def ingest(data_dir, rows):
    source = data_dir / 'demo.json'
    source.write_text(json.dumps(rows), encoding='utf-8')
    return run(('market', 'etf', 'import', str(source)), data_dir=data_dir)


def test_frozen_demo_keeps_the_evening_coverage_after_missing_nav_arrives(tmp_path):
    with TestClient(create_app(tmp_path)) as browser:
        params = {'trade_date': DAY, 'as_of': DEMO_CLOSE}
        funds = browser.get('/api/market/etf', params=params).json()['funds']
        late = observation('159949.SZ', 'etf_nav', DAY, '1.5', NEXT_MORNING)
        rows = []
        for fund in funds:
            symbol = fund['symbol']
            rows.extend([
                observation(symbol, 'etf_shares', PREVIOUS, '100000000'),
                observation(symbol, 'etf_shares', DAY, '200000000'),
            ])
            if symbol != late['symbol']:
                rows.append(observation(symbol, 'etf_nav', DAY, '1.5'))
        ingest(tmp_path, rows)
        evening = browser.post('/api/market/etf/reports', json=params)
        assert evening.status_code == 200, evening.text
        frozen = evening.json()
        assert frozen['summary']['valid_count'] == 34
        assert frozen['summary']['flow_status'] == 'partial'
        assert frozen['summary']['flow_cny'] == '5100000000'
        assert frozen['snapshot']['snapshot_id']
        assert run(('market', 'etf', 'freeze-report', '--date', DAY, '--as-of', DEMO_CLOSE),
                   data_dir=tmp_path) == frozen

        with pytest.raises(ValueError, match='单位'):
            ingest(tmp_path, [late, {**late, 'unit': '无效'}])
        latest_params = {**params, 'as_of': NEXT_MORNING}
        assert browser.get('/api/market/etf', params=latest_params).json()['summary'] == frozen['summary']

        with ThreadPoolExecutor() as pool:
            reads = [pool.submit(browser.get, f"/api/market/etf/reports/{frozen['report_id']}") for _ in range(3)]
            assert ingest(tmp_path, [late])['appended'] == 1
            assert all(read.result().json() == frozen for read in reads)
        assert ingest(tmp_path, [late])['appended'] == 0
        latest = browser.get('/api/market/etf', params=latest_params).json()
        assert latest['summary']['valid_count'] == 35
        assert latest['summary']['flow_status'] == 'complete'
        assert latest['summary']['flow_cny'] == '5250000000'
        assert browser.get('/api/market/etf', params=params).json()['summary'] == frozen['summary']

    with TestClient(create_app(tmp_path)) as restarted:
        replay = restarted.get(f"/api/market/etf/reports/{frozen['report_id']}")
        assert replay.json() == frozen
    assert run(('market', 'etf', 'replay-report', frozen['report_id']), data_dir=tmp_path) == frozen


def test_disclosure_reconstruction_starts_at_next_shanghai_midnight(tmp_path):
    day = '2026-08-28'
    received = '2026-11-27T09:05:00+08:00'
    symbol = '159949.SZ'
    shares = [
        observation(symbol, series, trade_date, value, received,
                    payload={'value': value, 'verified': True, 'disclosed_date': '2026-08-30'})
        for series, trade_date, value in [('etf_shares', '2026-08-27', '100000000'),
                                          ('etf_shares', day, '200000000')]
    ]
    ingest(tmp_path, [*shares,
                      observation(symbol, 'etf_nav', day, '1.5', received, available_at='2026-08-30'),
                      observation('159915.SZ', 'etf_nav', day, '1.2', received)])

    with TestClient(create_app(tmp_path)) as browser:
        params = {'trade_date': day, 'as_of': '2026-08-31T00:00:00+08:00'}
        live = browser.get('/api/market/etf', params=params).json()
        assert live['summary']['flow_cny'] is None
        assert live['latest_fields']['nav'] is None
        recon = {**params, 'use_mode': 'RECONSTRUCTED_RESEARCH'}
        before = browser.get('/api/market/etf', params={**recon, 'as_of': '2026-08-30T23:59:59+08:00'}).json()
        assert before['summary']['flow_cny'] is None
        response = browser.post('/api/market/etf/reports', json=recon)
        assert response.is_success, response.text
        verified = response.json()
        assert verified['use_mode'] == 'RECONSTRUCTED_RESEARCH'
        assert '上海时间次日 00:00' in verified['availability_assumption']
        assert verified['summary']['flow_cny'] == '150000000'
        assert verified['latest_fields']['nav']['valid_count'] == 1
        fund = next(row for row in verified['funds'] if row['symbol'] == symbol)
        nav = fund['inputs']['nav']['selected']
        assert nav['available_at'] is None
        assert nav['received_at'] == '2026-11-27T01:05:00.000000+00:00'
        assert nav['payload']['disclosed_date'] == '2026-08-30'
        assert nav['selected_available_at'] == '2026-08-30T16:00:00.000000+00:00'

    assert run(('market', 'etf', 'replay-report', verified['report_id']), data_dir=tmp_path) == verified


def test_basket_revisions_and_source_conflicts_can_only_change_new_report_versions(tmp_path):
    symbol = '159949.SZ'
    cutoff = '2026-11-27T14:00:00+08:00'
    rows = [observation(symbol, 'etf_shares', PREVIOUS, '100000000'),
            observation(symbol, 'etf_shares', DAY, '200000000'),
            observation(symbol, 'etf_nav', DAY, '1.2')]
    ingest(tmp_path, rows)

    with TestClient(create_app(tmp_path)) as browser:
        original = browser.post('/api/market/etf/reports', json={'trade_date': DAY, 'as_of': DEMO_CLOSE}).json()
        original_member = next(row for row in original['funds'] if row['symbol'] == symbol)
        member = {key: value for key, value in original_member.items() if key in {
            'symbol', 'name', 'fund_manager', 'listing_date', 'listing_source_ref', 'listing_source_sha256',
            'index_code', 'index_name', 'index_symbol', 'group_name', 'index_source_ref',
            'fund_tracking_source_ref', 'eligible_by_wide_index_type', 'effective_from', 'effective_to', 'known_at',
        }}
        revision = {
            **original['basket'], 'version': 'demo-fixed-35-v2', 'known_at': cutoff,
            'member_count': 1, 'members': [{**member, 'name': '演示更正基金名', 'known_at': cutoff}],
        }
        revision_file = tmp_path / 'basket.json'
        revision_file.write_text(json.dumps(revision), encoding='utf-8')
        args = ('market', 'etf', 'import-basket', str(revision_file))
        assert run(args, data_dir=tmp_path)['appended'] is True
        assert run(args, data_dir=tmp_path)['appended'] is False

        correction = observation(symbol, 'etf_nav', DAY, '1.5', cutoff, revision='1')
        ingest(tmp_path, [correction])
        old_params = {'trade_date': DAY, 'as_of': DEMO_CLOSE}
        still_original = browser.get('/api/market/etf', params=old_params).json()
        assert still_original['basket']['version'] == 'fixed-35-v1'
        assert still_original['summary']['flow_cny'] == '120000000'
        new_params = {**old_params, 'as_of': cutoff}
        current = browser.get('/api/market/etf', params=new_params).json()
        assert current['basket']['version'] == 'demo-fixed-35-v2'
        assert current['funds'][0]['name'] == '演示更正基金名'
        assert current['summary']['flow_cny'] == '150000000'

        withdrawn = '2026-11-27T14:20:00+08:00'
        ingest(tmp_path, [{**correction, 'withdrawn': True, 'received_at': withdrawn},
                          observation(symbol, 'etf_nav', DAY, '1.2', withdrawn, source='source-a'),
                          observation(symbol, 'etf_nav', DAY, '1.3', withdrawn, source='source-b')])
        conflict = browser.get('/api/market/etf', params={**new_params, 'as_of': withdrawn}).json()
        assert conflict['funds'][0]['missing'] == {'nav': 'conflict'}
        assert conflict['summary']['flow_cny'] is None
        assert browser.get(f"/api/market/etf/reports/{original['report_id']}").json() == original
