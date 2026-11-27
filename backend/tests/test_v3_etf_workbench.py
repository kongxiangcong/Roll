"""Read daily ETF coverage and evidence through the workbench and CLI."""

from fastapi.testclient import TestClient

from roll.v3.cli import run
from roll.v3.web import create_app


DAY = '2026-11-26'
PREVIOUS = '2026-11-25'
CLOCK = '2026-11-27T18:30:00+08:00'


def _observation(symbol, series, day, value, source, **extra):
    return {
        'symbol': symbol, 'series': series, 'trade_date': day, 'source': source,
        'source_ref': f'https://example.org/{source}/{day}', 'available_evidence': '合成测试记录',
        'received_at': f'{DAY}T15:05:00+08:00',
        'unit': {'etf_shares': '份', 'etf_nav': '元/份'}[series],
        'payload': {'value': value, 'verified': True}, **extra,
    }


def test_daily_report_retains_primary_shares_and_groups_official_tracking_indices(tmp_path):
    import json

    rows = [
        _observation('159949.SZ', 'etf_shares', PREVIOUS, '300000000', 'szse'),
        _observation('159949.SZ', 'etf_shares', DAY, '345000003', 'szse'),
        _observation('159949.SZ', 'etf_shares', DAY, '360000000', 'investoday', quality='date_mismatch'),
        _observation('159949.SZ', 'etf_nav', DAY, '1.234567', 'fuyao'),
        _observation('159915.SZ', 'etf_shares', PREVIOUS, '200000000', 'szse'),
        _observation('159915.SZ', 'etf_shares', DAY, '200000000', 'szse'),
        _observation('159915.SZ', 'etf_nav', DAY, '1.2', 'fuyao'),
    ]
    fixture = tmp_path / 'etf.json'
    fixture.write_text(json.dumps(rows), encoding='utf-8')
    run(('market', 'etf', 'import', str(fixture)), data_dir=tmp_path)

    with TestClient(create_app(tmp_path)) as browser:
        response = browser.get('/api/market/etf', params={'trade_date': DAY, 'as_of': CLOCK})
        assert response.status_code == 200, response.text
        report = response.json()

    assert report['basket']['version'] == 'fixed-35-v1'
    assert report['summary']['valid_count'] == 2
    assert report['summary']['expected_count'] == 35
    assert report['summary']['flow_status'] == 'partial'
    assert report['summary']['flow_cny'] == '55555518.703701'
    assert report['summary']['flow_yi'] == '0.55555518703701'
    assert report['summary']['flow_display_yi'] == '+0.56'
    groups = {row['index_code']: row for row in report['groups']}
    assert groups['399673']['summary']['flow_cny'] == '55555518.703701'
    assert groups['399006']['summary']['flow_status'] == 'partial'
    assert groups['399006']['summary']['flow_cny'] == '0'
    funds = {row['symbol']: row for row in report['funds']}
    assert funds['159949.SZ']['previous_shares'] == '300000000'
    assert funds['159949.SZ']['shares'] == '345000003'
    assert funds['159949.SZ']['nav'] == '1.234567'
    shares = funds['159949.SZ']['inputs']['shares']
    assert shares['selected']['source'] == 'szse'
    secondary = next(row for row in shares['candidates'] if row['source'] == 'investoday')
    assert (secondary['selection_quality'], secondary['difference']) == ('date_mismatch', 'value_mismatch')
    assert funds['510300.SH']['missing'] == {'shares': 'missing', 'previous_shares': 'missing', 'nav': 'missing'}


def test_daily_report_distinguishes_missing_zero_and_zero_partial_sum_and_exposes_complete_day(tmp_path):
    import json

    with TestClient(create_app(tmp_path)) as browser:
        empty = browser.get('/api/market/etf', params={'trade_date': DAY, 'as_of': CLOCK}).json()
        assert empty['data_date'] is None
        assert empty['summary']['flow_status'] == 'missing'
        assert empty['summary']['flow_cny'] is None
        assert empty['latest_complete_date'] is None

        rows = []
        for member in empty['funds']:
            symbol = member['symbol']
            source = {'SH': 'sse', 'SZ': 'szse'}[symbol.split('.')[-1]]
            rows.extend([
                _observation(symbol, 'etf_shares', PREVIOUS, '100000000', source),
                _observation(symbol, 'etf_shares', DAY, '100000000', source),
                _observation(symbol, 'etf_nav', DAY, '1.5000', 'fuyao'),
            ])
        following = '2026-11-27'
        received = f'{following}T15:30:00+08:00'
        for symbol, shares in [('159949.SZ', '200000000'), ('159915.SZ', '0')]:
            rows.extend([
                _observation(symbol, 'etf_shares', following, shares, 'szse', received_at=received),
                _observation(symbol, 'etf_nav', following, '1.5000', 'fuyao', received_at=received),
            ])
        fixture = tmp_path / 'coverage.json'
        fixture.write_text(json.dumps(rows), encoding='utf-8')
        run(('market', 'etf', 'import', str(fixture)), data_dir=tmp_path)

        complete = browser.get('/api/market/etf', params={'trade_date': DAY, 'as_of': CLOCK}).json()
        assert complete['summary']['flow_status'] == 'complete'
        assert complete['summary']['flow_cny'] == '0'
        assert complete['summary']['flow_display_yi'] == '0.00'

        partial = browser.get('/api/market/etf', params={'trade_date': following, 'as_of': CLOCK}).json()
        assert partial['data_date'] == following
        assert partial['summary']['flow_status'] == 'partial'
        assert partial['summary']['flow_cny'] == '0'
        assert partial['summary']['flow_display_yi'] == '0.00'
        assert partial['latest_complete_date'] == DAY
        assert partial['latest_fields']['nav'] == {'trade_date': following, 'valid_count': 2, 'expected_count': 35}


def test_etf_background_sync_reports_each_source_and_keeps_the_local_report_readable(tmp_path, monkeypatch):
    import threading
    from time import monotonic, sleep

    import httpx

    exchange_requested, release_exchange = threading.Event(), threading.Event()

    def provider(request):
        if request.url.host == 'query.sse.com.cn':
            exchange_requested.set()
            if not release_exchange.wait(5):
                return httpx.Response(503)
            day = request.url.params['STAT_DATE']
            return httpx.Response(200, json={'result': [
                {'STAT_DATE': day, 'SEC_CODE': '510300', 'TOT_VOL': '5000000.00'},
            ]})
        return httpx.Response(503)

    make_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda: make_client(transport=httpx.MockTransport(provider)))
    monkeypatch.setenv('ROLL_ENV', 'test')
    monkeypatch.setenv('FUYAO_API_KEY', 'test-fixture')

    with TestClient(create_app(tmp_path)) as browser:
        try:
            started = browser.post('/api/market/etf/sync', json={'trade_date': DAY})
            assert started.status_code == 200, started.text
            assert exchange_requested.wait(5)
            assert browser.get('/api/market/etf/sync/status').json()['status'] == 'running'
            assert browser.get('/api/market/etf', params={'trade_date': DAY, 'as_of': CLOCK}).is_success
            repeated = browser.post('/api/market/etf/sync', json={'trade_date': PREVIOUS}).json()
            assert repeated['status'] == 'running'
            assert repeated['trade_date'] == DAY
        finally:
            release_exchange.set()

        deadline = monotonic() + 5
        status = {'status': 'running'}
        while status['status'] == 'running' and monotonic() < deadline:
            status = browser.get('/api/market/etf/sync/status').json()
            sleep(0.02)
        assert status['status'] == 'partial'
        assert status['fields']['etf_shares']['succeeded'] == 2
        assert status['fields']['etf_nav'] == {'expected': 35, 'completed': 35, 'failed': 35, 'succeeded': 0}
        assert {row['source'] for row in status['failures']} == {'sse', 'szse', 'fuyao'}
        report = browser.get('/api/market/etf', params={'trade_date': DAY}).json()
        assert report['latest_fields']['shares']['valid_count'] == 1
        assert report['summary']['valid_count'] == 0
        assert browser.get('/api/research/tasks').json() == []
