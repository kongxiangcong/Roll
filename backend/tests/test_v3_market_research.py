import argparse
import json

import pytest

from roll.v3.market_cli import register as register_market


def command(data_dir, *args):
    from roll.v3.market_research import register_market_research

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)
    register_market(subparsers)
    research = subparsers.add_parser('research').add_subparsers(required=True)
    register_market_research(research)
    options = parser.parse_args(args)
    return options.handler(options, data_dir)


def observation(symbol, day, close, **payload):
    return {
        'series': 'daily_bar',
        'symbol': symbol,
        'trade_date': day,
        'source': 'exchange-archive',
        'source_ref': 'https://example.org/daily',
        'received_at': '2025-07-23T16:00:00+08:00',
        'unit': {'price': 'CNY/share', 'volume': 'share'},
        'payload': {'close': close, **payload},
    }


def import_and_freeze(tmp_path, rows, *, start, end, extra_symbols=()):
    path = tmp_path / 'observations.json'
    path.write_text(json.dumps(rows), encoding='utf-8')
    command(tmp_path, 'market', 'import', str(path))
    symbols = sorted({row['symbol'] for row in rows} | set(extra_symbols))
    return command(tmp_path, 'market', 'freeze', *symbols, '--start', start, '--end', end,
                   '--as-of', '2025-07-24T16:00:00+08:00', '--series', 'daily_bar',
                   '--series', 'industry_membership', '--series', 'adjustment_factor')['snapshot_id']


def test_research_export_reports_coverage_and_aligned_window_metrics(tmp_path):
    days = [f'2025-07-{day:02d}' for day in (14, 15, 16, 17, 18, 21)]
    rows = [observation('600362.SH', '2025-07-11', 90, trading_status='suspended')]
    for index, day in enumerate(days):
        rows.append(observation('600362.SH', day, [100, 110, 99, 99, 99, 99][index],
                                volume=100 * (index + 1), amount=1000))
        rows.append(observation('000300.SH', day, 110 if day == '2025-07-21' else 100))
        rows.append(observation('600001.SH', day, 200))
    start, end = '2025-07-10', days[-1]
    snapshot_id = import_and_freeze(tmp_path, rows, start=start, end=end)

    report = command(tmp_path, 'research', 'export', '600362.SH',
                     '--snapshot', snapshot_id, '--start', start, '--end', end)
    assert report['snapshot_id'] == snapshot_id
    assert set(report['securities']) == {'600362.SH', '000300.SH'}
    stock = report['securities']['600362.SH']
    coverage = stock['coverage']
    assert coverage['first_date'] == '2025-07-11'
    assert coverage['last_date'] == end
    assert coverage['expected_count'] == 8
    assert coverage['effective_count'] == 6
    assert coverage['suspended_dates'] == ['2025-07-11']
    assert coverage['gap_dates'] == ['2025-07-10']
    assert coverage['evaluable']['5']['intervals'] == [{'start': end, 'end': end}]
    assert coverage['evaluable']['10']['count'] == 0

    week = stock['windows']['5']
    assert week['start'] == '2025-07-14'
    assert week['end'] == end
    assert week['return'] == pytest.approx(-0.01)
    assert week['max_drawdown'] == pytest.approx(-0.10)
    assert week['annualized_volatility'] == pytest.approx(1.122497216)
    assert week['average_volume'] == 400
    assert report['benchmark']['windows']['5']['relative_return'] == pytest.approx(-0.11)
    assert stock['windows']['10']['status'] == 'insufficient_coverage'


def test_industry_export_respects_membership_and_separates_etf_proxy(tmp_path):
    days = [f'2025-07-{day:02d}' for day in (7, 8, 9, 10, 11, 14, 15, 16, 17, 18, 21, 22)]
    start, end = days[0], days[-1]
    received = '2025-07-23T16:00:00+08:00'
    trend = {
        'received_at': received,
        'data': {'code': '200', 'data': [
            {'swindexcode': '801055', 'bargaindate': day, 'openindex': 100, 'maxindex': 100,
             'minindex': 100, 'closeindex': 100, 'bargainamount': 3, 'bargainsum': 25}
            for day in days
        ]},
    }
    members = {
        'received_at': received,
        'data': {'code': '200', 'data': {'results': [
            {'stockcode': '600362', 'stockname': '江西铜业', 'beginningdate': '2025-07-15T08:00:00+08:00'},
            {'stockcode': '600001', 'stockname': '其他股票', 'beginningdate': '2025-07-15T08:00:00+08:00'},
        ]}},
    }
    paths = [tmp_path / name for name in ('trend.json', 'members.json')]
    for path, payload in zip(paths, (trend, members)):
        path.write_text(json.dumps(payload), encoding='utf-8')
    assert command(tmp_path, 'research', 'import-industry', *map(str, paths),
                   '--start', start, '--end', end)['appended'] == 13
    rows = [observation(code, day, 110 if code == '600362.SH' and day in {days[5], end} else 100)
            for day in days for code in ('600362.SH', '000300.SH', '512400.SH')]
    snapshot_id = import_and_freeze(
        tmp_path, rows, start=start, end=end, extra_symbols=('801055.SI',),
    )
    args = ('research', 'export', '600362.SH', '--snapshot', snapshot_id, '--start', start)
    report = command(tmp_path, *args)
    comparison = report['industry_comparisons']
    assert [(item['kind'], item['symbol'], item['start'], item['end']) for item in comparison] == [
        ('etf_proxy', '512400.SH', '2025-07-07', '2025-07-14'),
        ('industry_index', '801055.SI', '2025-07-15', '2025-07-22'),
    ]
    assert comparison[0]['stock_relative_windows']['5']['relative_return'] == pytest.approx(0.10)
    assert comparison[1]['stock_relative_windows']['10']['status'] == 'insufficient_coverage'
    assert report['industry_memberships'][0]['payload']['classification'] == '申万行业分类（2021版）'
    assert 'component_stocks' in report['industry_memberships'][0]['source_ref']
    assert report['securities']['801055.SI']['coverage']['effective_count'] == 12
    assert command(tmp_path, *args)['reference'] == report['reference']


def test_window_return_uses_the_frozen_effective_adjustment(tmp_path):
    days = [f'2025-07-{day:02d}' for day in (14, 15, 16, 17, 18, 21)]
    stock = '600362.SH'
    rows = [observation(stock, day, 100 if day == days[0] else 90) for day in days]
    rows.append({
        **observation(stock, days[1], None), 'series': 'adjustment_factor',
        'payload': {'multiplier': '1', 'offset': '-10', 'dividend_per_share': '10'},
    })
    snapshot_id = import_and_freeze(tmp_path, rows, start=days[0], end=days[-1])
    report = command(tmp_path, 'research', 'export', stock, '--snapshot', snapshot_id, '--start', days[0])
    security = report['securities'][stock]
    assert security['windows']['5']['return'] == pytest.approx(0)
    assert security['windows']['5']['raw_close_return'] == pytest.approx(-0.1)
    assert security['windows']['5']['annualized_volatility'] == pytest.approx(0)
    assert security['windows']['5']['max_drawdown'] == pytest.approx(0)
    assert security['adjustment_factors'][0]['trade_date'] == days[1]


def test_research_sync_industry_reads_publisher_quotes_and_membership(tmp_path, monkeypatch):
    import httpx

    def publisher(request):
        assert request.url.params['swindexcode'] == '801055'
        if request.url.path.endswith('/trend/'):
            data = [{'swindexcode': '801055', 'bargaindate': '2025-07-22', 'openindex': 100,
                     'maxindex': 105, 'minindex': 98, 'closeindex': 102,
                     'bargainamount': 3, 'bargainsum': 25}]
        else:
            assert request.url.path.endswith('/component_stocks/')
            data = {'results': [{'stockcode': '600362', 'stockname': '江西铜业',
                                 'beginningdate': '2021-12-13T08:00:00+08:00'}]}
        return httpx.Response(200, json={'code': '200', 'data': data})

    client = httpx.Client(transport=httpx.MockTransport(publisher))
    monkeypatch.setattr(httpx, 'Client', lambda **_options: client)
    result = command(tmp_path, 'research', 'sync-industry', '--end', '2025-07-22')
    assert result['appended'] == 2
    assert result['symbol'] == '801055.SI'
