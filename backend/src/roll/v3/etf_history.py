"""Historical comparison of local ETF flows, assets and tracking-index prices."""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from roll.v3.etf_basket import (
    ETF_HISTORY_WINDOWS, _daily_report, etf_history_calendar, prepare_etf_report,
    read_basket_days, summarize_etf_rows,
)
from roll.v3.etf_disclosures import (
    DISCLOSED_BASKET_NAME, DISCLOSED_BASKET_VERSION, etf_disclosure_day_cutoff,
    read_etf_disclosures,
)
from roll.v3.etf_replay import load_frozen_etf_report
from roll.v3.market import LIVE_RUN, _SCHEMA as MARKET_SCHEMA, read_snapshot, utc_timestamp
from roll.v3.overview import BENCHMARK_SYMBOL
from roll.v3.storage import database, ensure_schema


_FLOW_FIELDS = ('flow_cny', 'flow_yi', 'flow_display_yi', 'flow_status', 'valid_count', 'expected_count')
_PRICE_FIELDS = ('open', 'high', 'low', 'close')


def _window_totals(calendar, reports, start):
    result = []
    for key, requested in ETF_HISTORY_WINDOWS:
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


def _history_start(data_dir, snapshot, members, daily, cutoff, db):
    first = daily[0]['trade_date']
    recent = next((report['trade_date'] for report in daily if report['data_date']), None)
    if recent == first or any(fund['previous_shares'] is not None for fund in daily[0]['funds']):
        return first
    if not any(item['series'] == 'etf_nav' and item['start'] < first for item in snapshot['scope']):
        return recent
    prior = str(date.fromisoformat(first) - timedelta(days=1))
    for member in members:
        start = max(member['listing_date'], member['effective_from'])
        end = prior
        if member['effective_to']:
            end = min(end, str(date.fromisoformat(member['effective_to']) - timedelta(days=1)))
        if start > end:
            continue
        for series in ('etf_shares', 'etf_nav'):
            if read_snapshot(data_dir, snapshot, series=series, symbol=member['symbol'],
                             start=start, end=end, cutoff=cutoff, db=db)['observations']:
                return first
    return recent


def _apply_disclosed_membership(data_dir, snapshot, members, daily, cutoff, db):
    reports = []
    selected = daily[-1]['trade_date']
    for report in daily:
        day = report['trade_date']
        disclosed = read_etf_disclosures(
            data_dir, snapshot, members=members, trade_date=day, db=db,
            cutoff=cutoff if day == selected else min(cutoff, utc_timestamp(etf_disclosure_day_cutoff(day))),
        )
        symbols = {member['symbol'] for member in disclosed['rule_pool']['members']}
        reports.append(_daily_report(day, [fund for fund in report['funds'] if fund['symbol'] in symbols]))
    return reports


def build_etf_history_report(data_dir, *, trade_date=None, index_code=None, symbol=None,
                             basket_version=None, membership='fixed', as_of=None, max_seq=None,
                             use_mode=LIVE_RUN, captured_at=None, disclosure_cutoff=None, report_id=None):
    """Read cumulative coverage and aligned daily series from the daily report context."""
    if membership not in {'fixed', 'disclosed'}:
        raise ValueError('未知 ETF 历史篮子口径')

    with database(data_dir) as db:
        ensure_schema(db, MARKET_SCHEMA)
        db.execute('BEGIN')
        if report_id:
            context = load_frozen_etf_report(data_dir, report_id, trade_date=trade_date, db=db)
        else:
            context = prepare_etf_report(
                data_dir, db=db, trade_date=trade_date, basket_version=basket_version, as_of=as_of,
                use_mode=use_mode, max_seq=max_seq, captured_at=captured_at, disclosure_cutoff=disclosure_cutoff,
            )
        basket, snapshot, cutoff = context['basket'], context['snapshot'], context['cutoff']
        trade_date = context['trade_date']
        members = _selected_members(basket['members'], index_code, symbol)
        identity = members[0]
        grouped = index_code is not None or symbol is not None
        index_symbol = identity['index_symbol'] if grouped else BENCHMARK_SYMBOL
        calendar = etf_history_calendar(trade_date)
        first = min(days[0] for days in calendar.values())
        daily = read_basket_days(
            data_dir, snapshot, members=members, start=first, end=trade_date, cutoff=cutoff, db=db,
        )
        first_data = _history_start(data_dir, snapshot, members, daily, cutoff, db)
        candles = _index_candles(data_dir, snapshot, index_symbol, first, trade_date, cutoff, db)
        if membership == 'disclosed':
            daily = _apply_disclosed_membership(
                data_dir, snapshot, members, daily, context.get('disclosure_cutoff', cutoff), db,
            )

    basket_meta = {key: value for key, value in basket.items() if key != 'members'}
    if membership == 'disclosed':
        basket_meta = {
            'version': DISCLOSED_BASKET_VERSION, 'name': DISCLOSED_BASKET_NAME,
            'eligibility_catalog_version': basket['version'], 'history_label': '按历史日披露归属',
        }
    return {
        'trade_date': trade_date, 'as_of': cutoff, 'first_data_date': first_data,
        'basket': basket_meta,
        'index_code': identity['index_code'] if grouped else None,
        'index_symbol': index_symbol, 'index_name': identity['index_name'] if grouped else '沪深 300',
        'group_name': identity['group_name'] if grouped else None,
        'symbol': identity['symbol'] if symbol else None, 'fund_name': identity['name'] if symbol else None,
        'listing_date': identity['listing_date'] if symbol else None,
        'snapshot': snapshot, 'report_id': report_id, 'use_mode': snapshot['use_mode'],
        'windows': _window_totals(calendar, {report['trade_date']: report for report in daily},
                                  first_data or trade_date),
        'days': [_day_summary(report, candles.get(report['trade_date'])) for report in daily],
    }
