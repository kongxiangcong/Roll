"""Fuyao raw daily observations and sync into the versioned market store."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import os

import httpx

from roll.config import load_runtime_environment
from roll.market.calendar import LAST_NOTICE_DAY, is_session
from roll.v3.market import (
    RECONSTRUCTED_RESEARCH, SHANGHAI, append_observations, available_dates,
    freeze_snapshot, read_snapshot,
)


FUYAO = 'https://fuyao.aicubes.cn'
TENCENT_INDEX = 'https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get'
ACTION_PATH = '/api/a-share/corporate-actions/adjustment-factors'
OHLC = ('open', 'high', 'low', 'close')
DEFAULT_SYMBOLS = ('600362.SH', '000300.SH')
PRICE_SERIES = ('daily_bar', 'daily_open')


def _get(client, token, path, symbol, params):
    response = client.get(FUYAO + path, params={'thscode': symbol, **params},
                          headers={'X-api-key': token}, follow_redirects=False, timeout=20)
    if response.status_code != 200:
        raise ValueError(f'扶摇 HTTP {response.status_code}')
    body = json.loads(response.content, parse_float=Decimal)
    if body['code'] != 0:
        raise ValueError(f"扶摇业务码 {body['code']}")
    data = body['data']
    if data.get('thscode', symbol) != symbol:
        raise ValueError('扶摇返回的证券代码不符')
    return data


def _local_time(day, at):
    return datetime.combine(day, at, SHANGHAI)


def _millis(day, at):
    return int(_local_time(day, at).timestamp() * 1000)


def _day(millis):
    return datetime.fromtimestamp(int(millis) / 1000, SHANGHAI).date()


def _number(value):
    return format(Decimal(str(value)), 'f') if value is not None else None


def _previous_session(day):
    day -= timedelta(days=1)
    while not is_session(day):
        day -= timedelta(days=1)
    return day


def _ranges(start, end, available):
    cursor = start
    while cursor <= end:
        right = min(end, date(cursor.year, 12, 31))
        days = [cursor + timedelta(days=offset) for offset in range((right - cursor).days + 1)]
        missing = [day for day in days if is_session(day) and str(day) not in available]
        if missing:
            yield missing[0], missing[-1]
        cursor = right + timedelta(days=1)


def _observed_row(symbol, day, path, received_at, *, series, at, unit, payload,
                  reconstruction_only=False, quality='usable', source='fuyao'):
    return {
        'series': series, 'symbol': symbol, 'trade_date': str(day), 'source': source,
        'source_ref': FUYAO + path if source == 'fuyao' else path, 'received_at': received_at,
        'assumed_available_at': _local_time(day, at), 'availability_assumption':
            f'Shanghai {at:%H:%M} reconstruction from {source} historical observations',
        'unit': unit, 'payload': payload, 'reconstruction_only': reconstruction_only, 'quality': quality,
    }


def _factors(client, token, symbol, start, end):
    data = _get(client, token, ACTION_PATH, symbol, {'from': str(start), 'to': str(end)})
    received = datetime.now(timezone.utc)
    result = {}
    for item in data['item']:
        day = _day(item['ex_date_ms'])
        if not start <= day <= end:
            continue
        if item['ticker'] != symbol.split('.')[0] or day in result:
            raise ValueError('扶摇除权事件日期或证券代码冲突')
        cash = Decimal(item['dividend_per_share'])
        bonus = Decimal(item['per_share_bonus'])
        rights = Decimal(item.get('allotment_ratio') or 0)
        price = Decimal(item['allotment_price']) if rights else Decimal(0)
        multiplier = Decimal(1) / (1 + bonus + rights)
        offset = (rights * price - cash) * multiplier
        result[day] = _observed_row(
            symbol, day, ACTION_PATH, received, series='adjustment_factor', at=time(9, 30),
            unit={'offset': 'CNY/share', 'dividend_per_share': 'CNY/share'},
            payload={
                'multiplier': str(multiplier), 'offset': str(offset),
                'dividend_per_share': str(cash), 'bonus_per_share': str(bonus),
                'rights_per_share': str(rights), 'rights_price': str(price),
            },
        )
    return result


def _basis(prior_close, factor, factors_known):
    if prior_close is None or not factors_known:
        return None, None
    if factor is None:
        return prior_close, 'prior_close_no_adjustment_factor'
    payload = factor['payload']
    adjusted = Decimal(prior_close) * Decimal(payload['multiplier']) + Decimal(payload['offset'])
    price = adjusted.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return str(price), 'fuyao_adjustment_factor'


def _bars(client, token, symbol, start, end, *, index, factors):
    lookback = _previous_session(start)
    path = '/api/a-share-index/prices/historical' if index else '/api/a-share/prices/historical'
    params = {'start': _millis(lookback, time.min), 'end': _millis(end, time.max), 'interval': '1d'}
    if not index:
        params['adjust'] = 'none'
    data = _get(client, token, path, symbol, params)
    received = datetime.now(timezone.utc)
    if data.get('adjust', params.get('adjust')) != params.get('adjust') or data.get('interval', '1d') != '1d':
        raise ValueError('扶摇日线口径不符')
    rows = {}
    for item in data['item']:
        day = _day(item['date_ms'])
        if not lookback <= day <= end:
            continue
        if day in rows:
            raise ValueError(f'扶摇返回重复行情日期 {day}')
        rows[day] = item

    unit = {'price': 'index_point' if index else 'CNY/share', 'volume': 'share', 'amount': 'CNY'}
    for day, item in sorted(rows.items()):
        if day < start:
            continue
        prices = {key: _number(item.get(key + '_price')) for key in OHLC}
        previous = rows.get(_previous_session(day), {})
        prior = _number(previous.get('close_price'))
        pre_close, pre_close_basis = _basis(prior, (factors or {}).get(day), index or factors is not None)
        status = 'trading' if prices['open'] is not None and Decimal(prices['open']) > 0 else 'unknown'
        open_payload = {'open': prices['open'], 'prior_close': prior, 'pre_close': pre_close,
                        'pre_close_basis': pre_close_basis, 'trading_status': status}
        quality = 'usable' if all(value is not None and Decimal(value) > 0 for value in prices.values()) else 'anomalous'
        yield _observed_row(
            symbol, day, path, received, series='daily_bar', at=time(15, 5), unit=unit, quality=quality,
            payload={**open_payload, **prices, 'volume': _number(item.get('volume')),
                     'amount': _number(item.get('turnover'))},
        )
        # Daily history provides a reconstructed opening print, with only information
        # independent of the rest of that day's bar.
        yield _observed_row(
            symbol, day, path, received, series='daily_open', at=time(9, 30),
            unit={'price': unit['price']}, payload=open_payload, reconstruction_only=True,
            quality='usable' if status == 'trading' else 'anomalous',
        )


def _benchmark_fallback(client, start, end):
    lookback = _previous_session(start)
    response = client.get(
        TENCENT_INDEX,
        params={'param': f'sh000300,day,{lookback},{end},640,qfq'},
        timeout=20,
    )
    response.raise_for_status()
    received = datetime.now(timezone.utc)
    data = response.json()['data']['sh000300']['day']
    previous = None
    for item in data:
        day, opening, close, high, low, hands = item[:6]
        day = date.fromisoformat(day)
        if start <= day <= end:
            open_payload = {'open': opening, 'prior_close': previous, 'pre_close': previous,
                            'pre_close_basis': 'prior_raw_close', 'trading_status': 'trading'}
            # The index endpoint reports board lots and ten-thousands of yuan.
            bar = {**open_payload, 'close': close, 'high': high, 'low': low,
                   'volume': _number(int(Decimal(hands) * 100)),
                   'amount': _number(int(Decimal(item[8]) * 10_000))}
            yield _observed_row(
                '000300.SH', day, TENCENT_INDEX, received, source='tencent', series='daily_bar',
                at=time(15, 5), unit={'price': 'index_point', 'volume': 'share', 'amount': 'CNY'},
                payload=bar,
            )
            yield _observed_row(
                '000300.SH', day, TENCENT_INDEX, received, source='tencent', series='daily_open',
                at=time(9, 30), unit={'price': 'index_point'}, payload=open_payload,
                reconstruction_only=True,
            )
        previous = close


def sync_daily_market(data_dir, *, symbols=DEFAULT_SYMBOLS, start='2020-01-02', end=None,
                      indices=(), refresh=False, warmup=0):
    now = datetime.now(SHANGHAI)
    last = now.date() if now.time() >= time(15, 5) else now.date() - timedelta(days=1)
    last = min(last, LAST_NOTICE_DAY)
    while not is_session(last):
        last -= timedelta(days=1)
    start, end = date.fromisoformat(start), date.fromisoformat(end) if end else last
    if start > end or end > last:
        raise ValueError('请选择已收盘的行情区间')

    symbols = tuple(dict.fromkeys(symbol.upper() for symbol in symbols))
    index_symbols = {'000300.SH', *(symbol.upper() for symbol in indices)}
    scope = [dict(series=series, symbol=symbol, start=str(start), end=str(end))
             for symbol in symbols for series in (*PRICE_SERIES, 'adjustment_factor')
             if series != 'adjustment_factor' or symbol not in index_symbols and not symbol.endswith('.TI')]
    failures = []
    fallbacks = []
    operations = []
    for symbol in symbols:
        available = set() if refresh else available_dates(
            data_dir, series='daily_bar', symbol=symbol, start=str(start), end=str(end), as_of=now,
        )
        operations.extend((symbol, left, right) for left, right in _ranges(start, end, available))

    appended = 0
    if operations:
        load_runtime_environment()
        token = os.environ.get('FUYAO_API_KEY')
        if not token:
            raise ValueError('FUYAO_API_KEY 未配置')
        with httpx.Client() as client:
            for symbol, left, right in operations:
                index = symbol in index_symbols or symbol.endswith('.TI')
                window = {'symbol': symbol, 'start': str(left), 'end': str(right)}
                factors = None
                if not index:
                    try:
                        factors = _factors(client, token, symbol, left, right)
                        appended += append_observations(data_dir, factors.values())['appended']
                    except (ValueError, KeyError, TypeError, InvalidOperation, httpx.HTTPError) as error:
                        failures.append({**window, 'series': 'adjustment_factor', 'error': str(error)})
                try:
                    rows = list(_bars(client, token, symbol, left, right, index=index, factors=factors))
                    appended += append_observations(data_dir, rows)['appended']
                except (ValueError, KeyError, TypeError, InvalidOperation, httpx.HTTPError) as error:
                    if symbol != '000300.SH':
                        failures.append({**window, 'series': 'daily_bar', 'error': str(error)})
                        continue
                    rows = []
                    fallbacks.append({**window, 'source': 'tencent', 'fuyao_error': str(error)})
                if symbol == '000300.SH':
                    seen = {row['trade_date'] for row in rows if row['series'] == 'daily_bar'}
                    for gap_start, gap_end in _ranges(left, right, seen):
                        try:
                            rows = list(_benchmark_fallback(client, gap_start, gap_end))
                            appended += append_observations(data_dir, rows)['appended']
                        except (ValueError, KeyError, IndexError, httpx.HTTPError) as error:
                            failures.append({**window, 'series': 'daily_bar', 'source': 'tencent',
                                             'error': str(error)})

    snapshot = freeze_snapshot(data_dir, as_of=datetime.now(timezone.utc),
                               use_mode=RECONSTRUCTED_RESEARCH, scope=scope)
    report = read_snapshot(data_dir, snapshot['snapshot_id'], warmup=warmup)
    return {'snapshot': snapshot, 'appended': appended, 'failures': failures,
            'fallbacks': fallbacks, 'coverage': report['coverage']}
