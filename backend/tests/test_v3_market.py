import argparse
import json

from roll.v3.market_cli import register


def command(data_dir, *args):
    parser = argparse.ArgumentParser()
    register(parser.add_subparsers(required=True))
    options = parser.parse_args(["market", *args])
    return options.handler(options, data_dir)


def test_frozen_snapshot_keeps_original_after_correction_and_withdrawal(tmp_path):
    def ingest(**changes):
        first = {
            'series': 'daily_bar',
            'symbol': '600362.SH',
            'trade_date': '2025-07-21',
            'source': 'price-archive',
            'unit': {'price': 'CNY/share'},
            'available_at': '2025-07-21T15:05:00+08:00',
            'available_evidence': 'official-price-file-v1',
            'received_at': '2025-07-21T15:08:00+08:00',
            'revision': 'v1',
            'payload': {'open': '23.81', 'high': '24.58', 'low': '23.79', 'close': '24.40'},
        }
        incoming = tmp_path / 'observations.json'
        incoming.write_text(json.dumps([{**first, **changes}]), encoding='utf-8')
        return command(tmp_path, 'import', str(incoming))

    def freeze(mode):
        return command(tmp_path, 'freeze', '600362.SH', '--start', '2025-07-21',
                       '--end', '2025-07-22', '--as-of', '2025-07-25T16:00:00+08:00',
                       '--use-mode', mode)['snapshot_id']

    def read(snapshot_id, cutoff):
        return command(tmp_path, 'read', snapshot_id, '--cutoff', cutoff)

    original = ingest()
    old = freeze('LIVE_RUN')
    assert ingest()['appended'] == 0
    correction = ingest(
        revision='v2', available_at='2025-07-22T09:00:00+08:00',
        received_at='2025-07-23T10:00:00+08:00', available_evidence='official-price-file-v2',
        payload={'open': '23.81', 'high': '24.58', 'low': '23.79', 'close': '24.41'},
    )
    live = freeze('LIVE_RUN')
    strict = freeze('STRICT_HISTORICAL_AS_OF')
    before_receipt = '2025-07-22T15:00:00+08:00'
    assert read(live, before_receipt)['observations'][0]['payload']['close'] == '24.40'
    assert read(strict, before_receipt)['observations'][0]['payload']['close'] == '24.41'

    ingest(revision='v3', withdrawn=True, payload={}, available_evidence='official-withdrawal',
           available_at='2025-07-24T09:00:00+08:00', received_at='2025-07-24T09:10:00+08:00')
    missing = read(freeze('LIVE_RUN'), '2025-07-24T16:00:00+08:00')
    assert missing['observations'] == []
    assert missing['coverage'][0]['withdrawn_dates'] == ['2025-07-21']
    assert correction['max_seq'] == 2
    after_withdrawal = '2025-07-24T16:00:00+08:00'
    replay = read(old, after_withdrawal)
    assert replay['snapshot']['max_seq'] == original['max_seq'] == 1
    assert replay['observations'][0]['payload']['close'] == '24.40'
    assert read(live, after_withdrawal)['observations'][0]['revision'] == 'v2'


def test_fuyao_sync_replays_raw_market_fields_and_open_projection(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    import httpx

    calls = []
    local = timezone(timedelta(hours=8))
    first, last = (int(datetime(2025, 7, day, tzinfo=local).timestamp() * 1000) for day in (21, 22))

    def fuyao(request):
        calls.append(request.url.path)
        if request.url.path.endswith('/adjustment-factors'):
            return httpx.Response(200, json={'code': 0, 'data': {'item': [
                {'ticker': '600362', 'ex_date_ms': last, 'dividend_per_share': 0.70,
                 'per_share_bonus': 0.0},
            ]}})
        assert request.url.params['thscode'] == '600362.SH'
        assert request.url.params['adjust'] == 'none'
        return httpx.Response(200, json={'code': 0, 'data': {'adjust': 'none', 'item': [
            {'date_ms': first, 'open_price': 23.81, 'high_price': 24.58, 'low_price': 23.79,
             'close_price': 24.40, 'volume': 49705147, 'turnover': 1210260704.48},
            {'date_ms': last, 'open_price': 23.73, 'high_price': 24.1, 'low_price': 23.55,
             'close_price': 23.91, 'volume': 52219668, 'turnover': 1241541268.97},
        ]}})

    monkeypatch.setenv('ROLL_ENV', 'test')
    monkeypatch.setenv('FUYAO_API_KEY', 'fixture')
    client = httpx.Client(transport=httpx.MockTransport(fuyao))
    monkeypatch.setattr(httpx, 'Client', lambda: client)

    scope = ('600362.SH', '--start', '2025-07-21', '--end', '2025-07-22')
    synced = command(tmp_path, 'sync', *scope)
    assert synced['coverage'][0]['effective_count'] == 2
    assert synced['coverage'][0]['gap_dates'] == []
    assert synced['failures'] == []
    assert command(tmp_path, 'sync', *scope)['appended'] == 0
    assert len(calls) == 2

    cutoff = '2025-07-22T09:30:00+08:00'
    snapshot = synced['snapshot']['snapshot_id']
    opened = command(tmp_path, 'read', snapshot, '--series', 'daily_open', '--cutoff', cutoff)
    ex_open = opened['observations'][-1]
    assert ex_open['source'] == 'fuyao'
    assert ex_open['unit']['price'] == 'CNY/share'
    assert ex_open['payload'] == {
        'open': '23.73', 'prior_close': '24.4', 'pre_close': '23.70',
        'pre_close_basis': 'fuyao_adjustment_factor', 'trading_status': 'trading',
    }
    assert ex_open['available_at'] is None
    assert ex_open['assumed_available_at'] == '2025-07-22T01:30:00.000000+00:00'
    assert ex_open['received_at'] > ex_open['assumed_available_at']
    seen_by_open = command(tmp_path, 'read', snapshot, '--series', 'daily_bar', '--cutoff', cutoff)
    assert [row['trade_date'] for row in seen_by_open['observations']] == ['2025-07-21']
    bars = command(tmp_path, 'read', snapshot, '--series', 'daily_bar')['observations']
    assert bars[-1]['payload']['amount'] == '1241541268.97'
    assert bars[-1]['payload']['volume'] == '52219668'
    strict = command(tmp_path, 'freeze', *scope, '--use-mode', 'STRICT_HISTORICAL_AS_OF')
    assert command(tmp_path, 'read', strict['snapshot_id'])['observations'] == []
    live = command(tmp_path, 'freeze', *scope, '--use-mode', 'LIVE_RUN')
    assert command(tmp_path, 'read', live['snapshot_id'], '--series', 'daily_open')['observations'] == []
    assert command(tmp_path, 'read', live['snapshot_id'], '--series', 'daily_bar',
                   '--cutoff', cutoff)['observations'] == []


def test_benchmark_sync_fills_uncovered_fuyao_window_with_tencent(tmp_path, monkeypatch):
    import httpx

    requests = []

    def prices(request):
        requests.append(request)
        if request.url.host == 'fuyao.aicubes.cn':
            return httpx.Response(200, json={'code': 1003})
        assert request.url.host == 'proxy.finance.qq.com'
        assert 'X-api-key' not in request.headers
        return httpx.Response(200, json={'data': {'sh000300': {'day': [
            ['2020-01-02', '4093.93', '4152.24', '4161.18', '4093.93',
             '149405254.00', {}, '1.36', '22537430.79'],
        ]}}})

    monkeypatch.setenv('ROLL_ENV', 'test')
    monkeypatch.setenv('FUYAO_API_KEY', 'fixture')
    client = httpx.Client(transport=httpx.MockTransport(prices))
    monkeypatch.setattr(httpx, 'Client', lambda: client)

    scope = ('000300.SH', '--start', '2020-01-02', '--end', '2020-01-02')
    synced = command(tmp_path, 'sync', *scope)
    assert synced['coverage'][0]['effective_count'] == 1
    assert synced['failures'] == []
    assert len(requests) == 2
    assert command(tmp_path, 'sync', *scope)['appended'] == 0
    rows = command(tmp_path, 'read', synced['snapshot']['snapshot_id'])['observations']
    assert rows[0]['source'] == 'tencent'
    assert rows[0]['payload']['close'] == '4152.24'
    assert rows[0]['payload']['volume'] == '14940525400'
    assert rows[0]['payload']['amount'] == '225374307900'
