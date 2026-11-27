"""Exercise the ETF history report from CLI ingestion through the workbench API."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from roll.v3.cli import run
from roll.v3.web import create_app


HISTORY = '/api/market/etf/history'
CLOCK = '2026-10-12T18:00:00+08:00'
SESSIONS = ['2026-09-29', '2026-09-30', '2026-10-08', '2026-10-09', '2026-10-12']


def _etf(symbol, series, day, value, *, received_at=CLOCK):
    nav = series == 'etf_nav'
    return {
        'series': series, 'symbol': symbol, 'trade_date': day,
        'source': 'fuyao' if nav else 'sse', 'source_ref': f'https://example.org/{series}/{day}',
        'available_evidence': '合成测试记录',
        'received_at': received_at, 'unit': '元/份' if nav else '份',
        'payload': {'value': value, 'verified': True},
    }


def _import(data_dir, rows):
    observations = data_dir / 'observations.json'
    observations.write_text(json.dumps(rows), encoding='utf-8')
    run(('market', 'import', str(observations)), data_dir=data_dir)


def _history(data_dir, **params):
    with TestClient(create_app(data_dir)) as browser:
        response = browser.get(HISTORY, params=params)
    assert response.is_success, response.text
    return response.json()


def test_window_counts_applicable_fund_days_and_skips_exchange_holidays(tmp_path):
    rows = []
    for symbol in ('510050.SH', '510100.SH'):
        rows.append(_etf(symbol, 'etf_shares', '2026-09-28', '100000000'))
        for step, day in enumerate(SESSIONS, 1):
            rows.append(_etf(symbol, 'etf_shares', day, str(100000000 + step)))
            if (symbol, day) != ('510100.SH', '2026-10-08'):
                rows.append(_etf(symbol, 'etf_nav', day, '1.23456789'))
    _import(tmp_path, rows)

    history = _history(tmp_path, trade_date=SESSIONS[-1], index_code='000016', as_of=CLOCK)

    windows = {window['key']: window for window in history['windows']}
    week = windows['5']
    assert (week['start_date'], week['end_date']) == (SESSIONS[0], SESSIONS[-1])
    assert week['session_count'] == 5
    assert (week['valid_count'], week['expected_count'], week['flow_status']) == (9, 10, 'partial')
    assert week['flow_cny'] == '11.11111101'
    assert [day['trade_date'] for day in history['days'] if day['trade_date'] >= SESSIONS[0]] == SESSIONS
    assert set(windows) == {'1', '5', '21', '120', '242', 'ytd'}
    assert windows['21']['insufficient_history'] is True
    assert windows['21']['start_date'] == '2026-09-28'


def _bar(symbol, day, *, received_at=CLOCK, close='3910.25'):
    return {
        'series': 'daily_bar', 'symbol': symbol, 'trade_date': day, 'source': 'fuyao',
        'received_at': received_at, 'unit': '点',
        'payload': {'open': '3900.5', 'high': '3918.75', 'low': '3899.0', 'close': close},
    }


def test_index_flow_and_complete_assets_keep_independent_gaps(tmp_path):
    rows = [_etf('510100.SH', 'etf_shares', '2026-09-28', '100000000')]
    for symbol in ('510050.SH', '510100.SH'):
        for day, nav in zip(SESSIONS, ('1', '2', '3', None, '1')):
            if day == '2026-10-09':
                continue
            rows.append(_etf(symbol, 'etf_shares', day, '100000000'))
            if (symbol, day) != ('510100.SH', '2026-10-08'):
                rows.append(_etf(symbol, 'etf_nav', day, nav))
    rows += [
        _bar('000016.SH', SESSIONS[0]),
        _bar('000016.SH', SESSIONS[2]),
        _bar('000016.SH', SESSIONS[3]),
        _bar('000016.SH', SESSIONS[-1], received_at='2026-10-12T19:00:00+08:00'),
        _bar('000300.SH', SESSIONS[-1]),
    ]
    _import(tmp_path, rows)
    history = _history(tmp_path, trade_date=SESSIONS[-1], index_code='000016', as_of=CLOCK)
    days = {day['trade_date']: day for day in history['days']}

    first, second, partial, missing, final = (days[date] for date in SESSIONS)
    assert (first['flow_cny'], first['valid_count'], first['complete_assets_yi']) == ('0', 1, '2')
    assert (second['flow_cny'], second['valid_count'], second['complete_assets_yi']) == ('0', 2, '4')
    assert (partial['assets_yi'], partial['assets_valid_count'], partial['complete_assets_yi']) == ('3', 1, None)
    assert partial['index_ohlc']['open'] == '3900.5'
    assert (missing['flow_cny'], missing['assets_yi'], missing['index_ohlc']['close']) == (None, None, '3910.25')
    assert (final['index_ohlc'], final['flow_cny'], final['complete_assets_yi']) == (None, None, '2')
    whole = _history(tmp_path, trade_date=SESSIONS[-1], as_of=CLOCK)
    assert whole['index_symbol'] == '000300.SH'
    assert whole['days'][-1]['index_ohlc']['close'] == '3910.25'


def test_history_excludes_prelisting_fund_days_and_handles_first_known_session(tmp_path):
    early = '2013-01-04'
    for date, expected in (
        (early, (0, 1, '1')),
        ('2019-10-08', (0, 1, '1')),
        ('2019-10-09', (1, 2, '2')),
    ):
        # 510100 joined the index group on October 9; prelisting source rows do not count.
        rows = [_etf('510050.SH', 'etf_shares', date, '100000000'),
                _etf('510050.SH', 'etf_nav', date, '1'),
                _etf('510100.SH', 'etf_nav', date, '1')]
        if date == '2019-10-09':
            rows.append(_etf('510100.SH', 'etf_shares', date, '100000000'))
        _import(tmp_path, rows)
        day = _history(tmp_path, trade_date=date, index_code='000016', as_of=CLOCK)['days'][-1]
        assert (day['valid_count'], day['expected_count'], day['complete_assets_yi']) == expected
    fund = _history(tmp_path, trade_date='2019-10-08', symbol='510100.SH', as_of=CLOCK)
    assert fund['listing_date'] == '2019-10-09'
    assert fund['days'][-1]['flow_status'] == 'not_applicable'


def test_daily_report_waterline_pins_both_etf_and_index_inputs(tmp_path):
    day, previous = SESSIONS[-1], SESSIONS[-2]
    _import(tmp_path, [
        _etf('510050.SH', 'etf_shares', previous, '100000000'),
        _etf('510050.SH', 'etf_shares', day, '120000000'),
        _etf('510050.SH', 'etf_nav', day, '1'),
        _bar('000016.SH', day),
    ])
    with TestClient(create_app(tmp_path)) as browser:
        daily = browser.get('/api/market/etf', params={'trade_date': day, 'as_of': CLOCK}).json()
    _import(tmp_path, [
        _etf('510050.SH', 'etf_nav', day, '2'),
        _bar('000016.SH', day, close='3911.25'),
    ])

    anchored = _history(tmp_path, trade_date=day, symbol='510050.SH', as_of=daily['as_of'],
                        max_seq=daily['snapshot']['max_seq'])
    current = _history(tmp_path, trade_date=day, symbol='510050.SH', as_of=CLOCK)
    assert anchored['days'][-1]['flow_yi'] == '0.2'
    assert anchored['days'][-1]['index_ohlc']['close'] == '3910.25'
    assert current['days'][-1]['flow_yi'] == '0.4'
    assert current['days'][-1]['index_ohlc']['close'] == '3911.25'


def test_disclosed_history_uses_each_days_available_membership(tmp_path):
    published = '2026-11-27T17:00:00+08:00'
    previous, day = '2026-11-26', '2026-11-27'
    source = Path(__file__).with_name('fixtures') / 'etf_disclosures_510300.json'
    run(('market', 'etf', 'disclosures', 'import', str(source)), data_dir=tmp_path)
    _import(tmp_path, [
        _etf('510300.SH', 'etf_shares', previous, '100000000'),
        _etf('510300.SH', 'etf_nav', previous, '1'),
        _etf('510300.SH', 'etf_shares', day, '130000000', received_at=published),
        _etf('510300.SH', 'etf_nav', day, '2', received_at=published),
    ])
    history = _history(tmp_path, trade_date=day, index_code='000300', as_of=published, membership='disclosed')
    assert history['basket']['version'] == 'huijin-disclosed-wide-v1'
    before, after = history['days'][-2:]
    assert (before['trade_date'], before['expected_count'], before['flow_cny']) == (previous, 0, None)
    assert (after['trade_date'], after['expected_count'], after['flow_cny']) == (day, 1, '60000000')
    week = next(window for window in history['windows'] if window['key'] == '5')
    assert (week['valid_count'], week['expected_count']) == (1, 1)
