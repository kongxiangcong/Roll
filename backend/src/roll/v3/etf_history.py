"""Historical comparison of local ETF flows, assets and tracking-index prices."""

from datetime import date, time, timedelta
from decimal import Decimal, InvalidOperation

from roll.market.calendar import SSE_HISTORICAL_HOLIDAYS, is_session, latest_session
from roll.v3.etf import etf_snapshot_scope
from roll.v3.etf_basket import FIXED_BASKET_VERSION, get_fixed_basket, read_basket_days, summarize_etf_rows
from roll.v3.market import LIVE_RUN, _SCHEMA as MARKET_SCHEMA, prepare_snapshot, read_snapshot, utc_timestamp
from roll.v3.overview import BENCHMARK_SYMBOL
from roll.v3.storage import database, ensure_schema, instant, sessions


_WINDOWS = (('1', 1), ('5', 5), ('21', 21), ('120', 120), ('242', 242), ('ytd', None))
_FLOW_FIELDS = ('flow_cny', 'flow_yi', 'flow_display_yi', 'flow_status', 'valid_count', 'expected_count')
_PRICE_FIELDS = ('open', 'high', 'low', 'close')


def _calendar_windows(trade_date):
    day = date.fromisoformat(trade_date)
    first_calendar_year = min(SSE_HISTORICAL_HOLIDAYS)
    first_year = max(first_calendar_year, day.year - 2)
    calendar = list(sessions(f'{first_year}-01-01', trade_date))
    return {
        key: calendar[-count:] if count else [day for day in calendar if day[:4] == trade_date[:4]]
        for key, count in _WINDOWS
    }


def _input_scope(members, first, end):
    indexes = sorted({BENCHMARK_SYMBOL, *(member['index_symbol'] for member in members if member['index_symbol'])})
    return etf_snapshot_scope([member['symbol'] for member in members], first, end) + [
        {'series': 'daily_bar', 'symbol': index, 'start': first, 'end': end} for index in indexes
    ]


def etf_history_scope(members, trade_date):
    """Return the input scope required to replay all history windows and index candles."""
    calendar = _calendar_windows(trade_date)
    return _input_scope(members, min(days[0] for days in calendar.values()), trade_date)


def _window_totals(calendar, reports, start):
    result = []
    for key, requested in _WINDOWS:
        days = calendar[key]
        available = [day for day in days if start is not None and day >= start]
        totals = summarize_etf_rows(fund for day in available for fund in reports[day]['funds'])
        result.append({
            'key': key, 'start_date': available[0] if available else None,
            'end_date': available[-1] if available else None, 'session_count': len(available),
            'requested_session_count': requested or len(days),
            'window_start_date': days[0], 'window_end_date': days[-1],
            'insufficient_history': len(available) < (requested or len(days)),
            **{field: totals[field] for field in _FLOW_FIELDS},
        })
    return result


def _index_candles(data_dir, snapshot, symbol, start, end, cutoff, db):
    if not symbol:
        return {}
    observations = read_snapshot(
        data_dir, snapshot, symbol=symbol, start=start, end=end, cutoff=cutoff, db=db,
    )['observations']
    candles = {}
    for row in observations:
        payload = row['payload']
        if row['item_id'] or payload.get('trading_status') == 'suspended':
            continue
        try:
            prices = {field: Decimal(str(payload[field])) for field in _PRICE_FIELDS}
        except (InvalidOperation, KeyError):
            continue
        if not all(value.is_finite() and value > 0 for value in prices.values()):
            continue
        if not all(prices['low'] <= prices[field] <= prices['high'] for field in ('open', 'close')):
            continue
        candles[row['trade_date']] = {
            **{field: format(value, 'f') for field, value in prices.items()},
            'source': row['source'], 'source_ref': row['source_ref'],
        }
    return candles


def _day_summary(report, candle):
    summary = report['summary']
    return {
        'trade_date': report['trade_date'], 'data_date': report['data_date'],
        'index_ohlc': candle,
        **{field: summary[field] for field in _FLOW_FIELDS},
        'assets_yi': summary['assets_yi'], 'assets_cny': summary['assets_cny'],
        'assets_valid_count': summary['assets_valid_count'],
        'complete_assets_yi': summary['assets_yi']
        if summary['expected_count'] and summary['assets_valid_count'] == summary['expected_count'] else None,
    }


def _selected_members(members, index_code, symbol):
    selected = [member for member in members
                if (index_code is None or member['index_code'] == index_code)
                and (symbol is None or member['symbol'] == symbol.upper())]
    if not selected:
        raise ValueError('所选指数或基金不在篮子内')
    return selected


def build_etf_history_report(data_dir, *, trade_date, index_code=None, symbol=None,
                             basket_version=FIXED_BASKET_VERSION, as_of=None, max_seq=None,
                             snapshot=None, cutoff=None, basket=None):
    """Read cumulative coverage and aligned daily series against one local waterline."""
    basket = get_fixed_basket(basket_version) if basket is None else basket
    members = _selected_members(basket['members'], index_code, symbol)
    identity = members[0]
    grouped = index_code is not None or symbol is not None
    index_symbol = identity['index_symbol'] if grouped else BENCHMARK_SYMBOL
    selected = date.fromisoformat(trade_date)
    viewed = instant(cutoff or as_of or (snapshot and snapshot['as_of']))

    with database(data_dir) as db:
        ensure_schema(db, MARKET_SCHEMA)
        db.execute('BEGIN')
        last_closed, _ = latest_session(db, viewed.date() - timedelta(days=viewed.time() < time(15)))
        if selected > last_closed or selected.year < min(SSE_HISTORICAL_HOLIDAYS) or not is_session(selected):
            raise ValueError('请选择已收盘的交易日')
        calendar = _calendar_windows(trade_date)
        first = min(days[0] for days in calendar.values())
        if snapshot is None:
            snapshot = prepare_snapshot(
                data_dir, as_of=viewed, use_mode=LIVE_RUN,
                scope=_input_scope(members, first, trade_date), db=db,
            )
            if max_seq is not None:
                snapshot['max_seq'] = min(max_seq, snapshot['max_seq'])
        cutoff = min(utc_timestamp(viewed), snapshot['as_of'])
        daily = read_basket_days(
            data_dir, snapshot, members=members, start=first, end=trade_date, cutoff=cutoff, db=db,
        )
        candles = _index_candles(data_dir, snapshot, index_symbol, first, trade_date, cutoff, db)

    first_data = next((report['trade_date'] for report in daily if report['data_date']), None)
    if any(fund['previous_shares'] is not None for fund in daily[0]['funds']):
        first_data = first
    return {
        'trade_date': trade_date, 'as_of': cutoff, 'first_data_date': first_data,
        'basket': {key: value for key, value in basket.items() if key != 'members'},
        'index_code': identity['index_code'] if grouped else None,
        'index_symbol': index_symbol, 'index_name': identity['index_name'] if grouped else '沪深 300',
        'group_name': identity['group_name'] if grouped else None,
        'symbol': identity['symbol'] if symbol else None, 'fund_name': identity['name'] if symbol else None,
        'listing_date': identity['listing_date'] if symbol else None,
        'snapshot': snapshot,
        'windows': _window_totals(calendar, {report['trade_date']: report for report in daily}, first_data),
        'days': [_day_summary(report, candles.get(report['trade_date'])) for report in daily],
    }
