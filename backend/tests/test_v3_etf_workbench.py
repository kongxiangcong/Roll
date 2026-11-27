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
        assert status['status'] == 'partial', status
        assert status['fields']['etf_shares']['succeeded'] == 2
        assert status['fields']['etf_nav'] == {'expected': 35, 'completed': 35, 'failed': 35, 'succeeded': 0}
        assert {row['source'] for row in status['failures'] if row['series'] != 'daily_bar'} == {'sse', 'szse', 'fuyao'}
        report = browser.get('/api/market/etf', params={'trade_date': DAY}).json()
        assert report['latest_fields']['shares']['valid_count'] == 1
        assert report['summary']['valid_count'] == 0
        assert browser.get('/api/research/tasks').json() == []


def test_withdrawn_or_unusable_successors_remove_stale_latest_dates(tmp_path):
    import json

    following = DAY
    receipt = f'{following}T15:30:00+08:00'
    shares = _observation('159949.SZ', 'etf_shares', following, '200', 'szse', received_at=receipt)
    nav = _observation('159949.SZ', 'etf_nav', following, '2', 'fuyao', received_at=receipt)
    observations = tmp_path / 'dates.json'
    observations.write_text(json.dumps([
        _observation('159949.SZ', 'etf_shares', PREVIOUS, '100', 'szse'),
        _observation('159949.SZ', 'etf_nav', PREVIOUS, '1', 'fuyao'), shares, nav,
        {**shares, 'withdrawn': True, 'received_at': f'{following}T16:00:00+08:00'},
        {**nav, 'quality': 'date_mismatch', 'received_at': f'{following}T16:00:00+08:00'},
    ]), encoding='utf-8')
    run(('market', 'etf', 'import', str(observations)), data_dir=tmp_path)

    with TestClient(create_app(tmp_path)) as browser:
        assert browser.get('/api/market/dates').json()['latest_trade_date'] == PREVIOUS
        before = browser.get('/api/market/etf', params={'as_of': receipt}).json()
        assert before['trade_date'] == following
        current = browser.get('/api/market/etf', params={'as_of': CLOCK}).json()
        assert current['trade_date'] == PREVIOUS
        explicit = browser.get('/api/market/etf', params={'trade_date': following, 'as_of': CLOCK}).json()
        assert explicit['data_date'] is None
        assert explicit['latest_fields']['nav']['trade_date'] == PREVIOUS


def test_workbench_lists_known_fixed_basket_options_and_can_freeze_the_selected_version(tmp_path):
    import json

    from roll.v3.etf_basket_versions import get_fixed_basket

    baseline = get_fixed_basket()
    known_at = '2026-11-27T15:45:00+08:00'
    path = tmp_path / 'alternate-basket.json'
    path.write_text(json.dumps({
        **baseline, 'version': 'fixed-demo-small', 'name': '演示小篮子', 'known_at': known_at,
        'member_count': 1, 'members': baseline['members'][:1],
    }), encoding='utf-8')
    run(('market', 'etf', 'import-basket', str(path)), data_dir=tmp_path)

    with TestClient(create_app(tmp_path)) as browser:
        versions = '/api/market/etf/baskets'
        prior = browser.get(versions, params={'as_of': '2026-11-27T15:44:00+08:00'})
        assert prior.is_success, prior.text
        assert {row['version'] for row in prior.json()} == {'fixed-35-v1'}
        known = browser.get(versions, params={'as_of': CLOCK}).json()
        assert {row['version']: row['member_count'] for row in known} == {'fixed-35-v1': 35, 'fixed-demo-small': 1}
        params = {'trade_date': DAY, 'as_of': CLOCK, 'basket_version': 'fixed-35-v1'}
        report = browser.get('/api/market/etf', params=params).json()
        assert report['summary']['expected_count'] == 35
        frozen = browser.post('/api/market/etf/reports', json=params).json()
        assert browser.get(f"/api/market/etf/reports/{frozen['report_id']}").json()['basket']['version'] == 'fixed-35-v1'
        assert browser.get('/api/market/etf', params={**params, 'basket_version': 'fixed-demo-small'}).json()['summary']['expected_count'] == 1


def test_workbench_etf_sync_acquires_tracking_index_and_labels_missing_index_groups(tmp_path, monkeypatch):
    from datetime import datetime
    import json
    from time import monotonic, sleep

    import httpx

    from roll.v3.etf_basket_versions import get_fixed_basket

    baseline = get_fixed_basket()
    known_at = f'{DAY}T15:30:00+08:00'
    members = [{**member, 'known_at': known_at}
               for member in baseline['members'] if member['symbol'] in {'510050.SH', '560050.SH'}]
    path = tmp_path / 'index-basket.json'
    path.write_text(json.dumps({
        **baseline, 'version': 'index-demo-basket', 'known_at': known_at,
        'member_count': len(members), 'members': members,
    }), encoding='utf-8')
    run(('market', 'etf', 'import-basket', str(path)), data_dir=tmp_path)
    observations = tmp_path / 'observations.json'
    observations.write_text(json.dumps([
        _observation(member['symbol'], series, day, '100' if series == 'etf_shares' else '2', source)
        for member in members
        for series, day, source in [('etf_shares', PREVIOUS, 'sse'), ('etf_shares', DAY, 'sse'), ('etf_nav', DAY, 'fuyao')]
    ]), encoding='utf-8')
    run(('market', 'etf', 'import', str(observations)), data_dir=tmp_path)

    requests = []

    def provider(request):
        if request.url.path != '/api/a-share-index/prices/historical':
            return httpx.Response(503)
        symbol = request.url.params['thscode']
        requests.append(symbol)
        price = dict(open_price=100, low_price=99, high_price=103, close_price=102,
                     date_ms=int(datetime.fromisoformat(f'{DAY}T15:00:00+08:00').timestamp() * 1000))
        return httpx.Response(200, json={'code': 0, 'data': {
            'thscode': symbol, 'item': [price] if symbol == '000016.SH' else [],
        }})

    make_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda: make_client(transport=httpx.MockTransport(provider)))
    monkeypatch.setenv('ROLL_ENV', 'test')
    monkeypatch.setenv('FUYAO_API_KEY', 'test-fixture')

    with TestClient(create_app(tmp_path)) as browser:
        started = browser.post('/api/market/etf/sync', json={'trade_date': DAY, 'basket_version': 'index-demo-basket'})
        assert started.is_success, started.text
        deadline = monotonic() + 5
        status = started.json()
        while status['status'] == 'running' and monotonic() < deadline:
            status = browser.get('/api/market/etf/sync/status').json()
            sleep(0.02)
        assert status['status'] == 'partial', status
        assert status['fields']['daily_bar'] == {'expected': 3, 'completed': 3, 'failed': 2, 'succeeded': 1}
        assert {row['symbol'] for row in status['failures']} == {'000300.SH', '746059'}
        assert set(requests) == {'000016.SH', '000300.SH'}
        history = browser.get('/api/market/etf/history', params={
            'trade_date': DAY, 'index_code': '000016', 'basket_version': 'index-demo-basket',
        }).json()
        assert history['days'][-1]['index_ohlc']['close'] == '102'
