"""Versioned ETF basket reports using the shared market observation store."""

from collections import defaultdict
from datetime import date, time, timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext
from itertools import groupby

from roll.market.calendar import SSE_HISTORICAL_HOLIDAYS, extended_sessions, is_session, latest_session
from roll.v3.etf import etf_snapshot_scope, previous_etf_session, read_etf_days
from roll.v3.etf_basket_versions import (
    comparison_basket_timeline, resolve_comparison_basket,
)
from roll.v3.etf_disclosures import etf_disclosure_day_cutoff, etf_disclosure_scope, read_etf_disclosures
from roll.v3.market import LIVE_RUN, RECONSTRUCTED_RESEARCH, _SCHEMA as MARKET_SCHEMA, _choose, prepare_snapshot, utc_timestamp
from roll.v3.overview import BENCHMARK_SYMBOL
from roll.v3.storage import database, ensure_schema, instant, sessions


ETF_CALCULATION_VERSION = 'adjacent-session-shares-unit-nav-v1'
ETF_HISTORY_WINDOWS = (('1', 1), ('5', 5), ('21', 21), ('120', 120), ('242', 242), ('ytd', None))
_DAILY_FIELDS = {'shares': 'etf_shares', 'nav': 'etf_nav'}


def member_applies(member, day):
    return (member['listing_date'] <= day and member['effective_from'] <= day
            and (member['effective_to'] is None or day < member['effective_to']))


def etf_history_calendar(trade_date, extension=None):
    day = date.fromisoformat(trade_date)
    first_year = max(min(SSE_HISTORICAL_HOLIDAYS), day.year - 2)
    calendar = list(sessions(f'{first_year}-01-01', trade_date, extension))
    if not calendar or calendar[-1] != trade_date:
        raise ValueError('请选择已收盘的交易日')
    return {
        key: calendar[-count:] if count else [day for day in calendar if day[:4] == trade_date[:4]]
        for key, count in ETF_HISTORY_WINDOWS
    }


def etf_history_scope(members, trade_date, *, earliest_input_date=None, extension=None):
    """Capture the ETF, index and disclosure inputs needed by all report windows."""
    calendar = etf_history_calendar(trade_date, extension)
    first = min(days[0] for days in calendar.values())
    symbols = {member['symbol'] for member in members}
    indexes = {BENCHMARK_SYMBOL, *(member['index_symbol'] for member in members if member['index_symbol'])}
    # Earlier frozen drill-downs recompute their own chart windows using the same waterline.
    index_start = f'{min(SSE_HISTORICAL_HOLIDAYS)}-01-01'
    return (
        etf_snapshot_scope(sorted(symbols), min(first, earliest_input_date or first), trade_date, extension)
        + etf_disclosure_scope(sorted(symbols), trade_date)
        + [{'series': 'daily_bar', 'symbol': index, 'start': index_start, 'end': trade_date} for index in sorted(indexes)]
    )


def _decimal_text(amount):
    text = format(amount, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def _totals(rows, field):
    amounts = [Decimal(row[field]) for row in rows if row[field] is not None]
    if not amounts:
        return 0, None, None, None
    with localcontext() as context:
        highest = max(amount.adjusted() for amount in amounts)
        lowest = min(amount.as_tuple().exponent for amount in amounts)
        context.prec = max(context.prec, highest - lowest + len(str(len(amounts))) + 2)
        value = sum(amounts, Decimal(0))
        yi = value.scaleb(-8)
        display = yi.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if display.is_zero():
            display = abs(display)
        return len(amounts), _decimal_text(value), _decimal_text(yi), f'{display:+f}' if display else '0.00'


def summarize_etf_rows(funds):
    """Sum applicable rows at original precision before converting and rounding for display."""
    rows = [row for row in funds if row['applicable']]
    expected = len(rows)
    valid, flow, flow_yi, flow_display = _totals(rows, 'flow_cny')
    assets_valid, assets, assets_yi, _ = _totals(rows, 'assets_cny')
    status = 'not_applicable' if not expected else (
        'complete' if valid == expected else 'partial' if valid else 'missing')
    return {
        'valid_count': valid, 'expected_count': expected, 'flow_status': status,
        'flow_cny': flow, 'flow_yi': flow_yi, 'flow_display_yi': flow_display,
        'assets_valid_count': assets_valid, 'assets_cny': assets, 'assets_yi': assets_yi,
    }


def _daily_report(day, funds):
    grouped = defaultdict(list)
    for fund in funds:
        grouped[fund['index_code']].append(fund)
    groups = []
    for code, rows in grouped.items():
        identity = rows[0]
        groups.append({
            'index_code': code, 'index_symbol': identity['index_symbol'],
            'index_name': identity['index_name'], 'group_name': identity['group_name'],
            'summary': summarize_etf_rows(rows),
        })
    candidates = [item for row in funds for field in row['inputs'].values() for item in field['candidates']]
    has_observations = any(row['applicable'] and any(row[field] is not None for field in _DAILY_FIELDS)
                           for row in funds)
    return {
        'trade_date': day, 'data_date': day if has_observations else None,
        'updated_at': max((item['received_at'] for item in candidates), default=None),
        'summary': summarize_etf_rows(funds), 'groups': groups, 'funds': funds,
    }


def read_basket_days(data_dir, snapshot_id, *, members, start, end, cutoff=None, db=None, extension=None):
    """Read basket rows, summaries and evidence against one frozen input waterline."""
    days = list(sessions(start, end, extension))
    if not days:
        raise ValueError('ETF 区间须包含交易日')
    previous_days = [previous_etf_session(days[0], extension), *days[:-1]]
    funds_by_day = {day: [] for day in days}
    with database(data_dir, db=db) as connection:
        for member in members:
            applicable = set(day for day in days if member_applies(member, day))
            observations = {}
            if applicable:
                observations = {row['trade_date']: row for row in read_etf_days(
                    data_dir, snapshot_id, symbol=member['symbol'], start=min(applicable),
                    end=max(applicable), cutoff=cutoff, db=connection, extension=extension,
                )}
            for day, previous in zip(days, previous_days):
                if day in applicable:
                    row = {'applicable': True, **observations[day]}
                else:
                    reason = 'not_listed' if day < member['listing_date'] else 'outside_membership'
                    row = {
                        'applicable': False, 'trade_date': day, 'previous_trade_date': previous,
                        'shares': None, 'previous_shares': None, 'comparable_previous_shares': None,
                        'nav': None, 'split_ratio': None, 'flow_cny': None, 'assets_cny': None,
                        'missing': {'membership': reason}, 'inputs': {},
                    }
                _, _, flow_yi, flow_display = _totals([row], 'flow_cny')
                funds_by_day[day].append({
                    **member, **row, 'flow_yi': flow_yi, 'flow_display_yi': flow_display,
                })
    return [_daily_report(day, funds_by_day[day]) for day in days]


def _candidate_dates(db, members, end, cutoff, snapshot, extension):
    by_symbol = defaultdict(list)
    for member in members:
        by_symbol[member['symbol']].append(member)
    placeholders = ','.join('?' for _ in by_symbol)
    rows = db.execute(f"""
        SELECT * FROM observation
        WHERE series IN ('etf_shares', 'etf_nav') AND symbol IN ({placeholders})
          AND trade_date <= ? AND received_at <= ? AND seq <= ?
        ORDER BY trade_date DESC, series, symbol
    """, (*by_symbol, end, snapshot['as_of'], snapshot['max_seq']))
    days = defaultdict(lambda: defaultdict(int))
    for (day, series, symbol), versions in groupby(
        rows, key=lambda row: (row['trade_date'], row['series'], row['symbol']),
    ):
        if (any(member_applies(member, day) for member in by_symbol[symbol]) and is_session(date.fromisoformat(day), extension)
                and _choose(list(versions), snapshot, cutoff)[0]):
            days[day][series] += 1
    return days


def _field_dates_and_complete_report(report, candidates, members, read_day):
    current_day = report['trade_date']
    latest_fields = {}
    latest_complete_date = None
    for day in sorted({current_day, *candidates}, reverse=True):
        expected = sum(member_applies(member, day) for member in members)
        if not expected:
            continue
        entries = candidates.get(day, {})
        need_fields = {field for field, series in _DAILY_FIELDS.items()
                       if field not in latest_fields and (entries.get(series) or day == current_day)}
        could_be_complete = not latest_complete_date and (
            day == current_day or all(entries.get(series, 0) >= expected for series in _DAILY_FIELDS.values()))
        if not need_fields and not could_be_complete:
            continue
        daily = report if day == current_day else read_day(day)
        if could_be_complete and daily['summary']['flow_status'] == 'complete':
            latest_complete_date = day
        for field in need_fields:
            valid = sum(fund['applicable'] and fund[field] is not None for fund in daily['funds'])
            if valid:
                latest_fields[field] = {'trade_date': day, 'valid_count': valid, 'expected_count': expected}
        if latest_complete_date and latest_fields.keys() >= _DAILY_FIELDS.keys():
            break
    return {field: latest_fields.get(field) for field in _DAILY_FIELDS}, latest_complete_date


def report_catalog_timeline(context):
    # Reports frozen before catalog timelines retain their single pinned catalog.
    return context.get('catalog_timeline') or [context['basket']]


def disclosure_catalog_at(context, trade_date):
    timeline = report_catalog_timeline(context)
    cutoff = min(context.get('disclosure_cutoff', context['cutoff']),
                 utc_timestamp(etf_disclosure_day_cutoff(trade_date)))
    return next((basket for basket in reversed(timeline[1:]) if utc_timestamp(basket['known_at']) <= cutoff),
                timeline[0])


def attach_etf_disclosures(data_dir, report, *, snapshot, catalog, fixed_members, trade_date, cutoff, db, extension):
    """Pair the selected fixed comparison with the dated disclosure eligibility catalog."""
    by_symbol = {member['symbol']: member for member in catalog['members']}
    excluded = [{**member, 'eligible_by_wide_index_type': False}
                for member in fixed_members if member['symbol'] not in by_symbol]
    disclosures = read_etf_disclosures(data_dir, snapshot, members=[*by_symbol.values(), *excluded],
                                       trade_date=trade_date, cutoff=cutoff, db=db)
    pool = disclosures['rule_pool']
    disclosed = read_basket_days(
        data_dir, snapshot, members=pool['members'], start=trade_date, end=trade_date,
        cutoff=report['as_of'], db=db, extension=extension,
    )[0]
    disclosed['basket'] = {
        'version': pool['version'], 'name': pool['name'],
        'member_count': pool['member_count'], 'eligibility_catalog_version': catalog['version'],
    }
    return {
        **report,
        'comparison_baskets': {
            'fixed': {'basket': report['basket'], 'summary': report['summary']},
            'disclosed': disclosed,
        },
        'disclosures': {key: value for key, value in disclosures.items() if key != 'snapshot'},
    }


def prepare_etf_report(data_dir, *, db, trade_date=None, basket_version=None, as_of=None,
                       use_mode=LIVE_RUN, max_seq=None, captured_at=None, disclosure_cutoff=None):
    """Pin the input and identity versions while reading a single SQLite transaction."""
    viewed = instant(as_of)
    cutoff = utc_timestamp(viewed)
    basket = resolve_comparison_basket(db, cutoff=cutoff, version=basket_version)
    members = basket['members']
    catalog_timeline = comparison_basket_timeline(db, cutoff=cutoff)
    historical_members = [member for catalog in catalog_timeline if catalog['version'] != basket['version']
                          for member in catalog['members'] if member.get('eligible_by_wide_index_type')]
    symbols = [member['symbol'] for member in members]
    captured = viewed
    if use_mode == RECONSTRUCTED_RESEARCH:
        now = instant()
        captured = instant(captured_at) if captured_at else now
        if captured > now:
            raise ValueError('补采水位时间不能晚于当前时刻')
    last_closed, _ = latest_session(db, viewed.date() - timedelta(days=viewed.time() < time(15)))
    selected = date.fromisoformat(trade_date) if trade_date else last_closed
    extension = frozenset(day for day in extended_sessions(db) if day <= selected.isoformat())
    if selected > last_closed or not is_session(selected, extension):
        raise ValueError('请选择已收盘的交易日')
    selected = selected.isoformat()
    snapshot = prepare_snapshot(data_dir, as_of=captured, use_mode=use_mode, db=db,
                                scope=etf_disclosure_scope(symbols, selected))
    if max_seq is not None:
        if not 0 <= max_seq <= snapshot['max_seq']:
            raise ValueError('ETF 报表的输入水位超出当前数据库')
        snapshot['max_seq'] = max_seq
    candidates = _candidate_dates(db, members, selected, cutoff, snapshot, extension)
    day = selected if trade_date else next(iter(candidates), selected)
    scoped_candidates = _candidate_dates(db, historical_members, day, cutoff, snapshot, extension) if historical_members else {}
    start = min({day, *candidates, *scoped_candidates})
    scope = etf_history_scope([*members, *historical_members], day, earliest_input_date=start, extension=extension)
    if disclosure_cutoff is not None:
        disclosure_cutoff = utc_timestamp(disclosure_cutoff)
        if disclosure_cutoff > cutoff:
            raise ValueError('ETF 披露截止时刻不能晚于报表截止时刻')
    else:
        disclosure_cutoff = cutoff if as_of else min(cutoff, utc_timestamp(etf_disclosure_day_cutoff(day)))
    return {
        'trade_date': day, 'cutoff': cutoff, 'basket': basket, 'disclosure_cutoff': disclosure_cutoff,
        'calendar_extension': sorted(extension), 'catalog_timeline': catalog_timeline, 'snapshot': {**snapshot, 'scope': scope}, 'calculation_version': ETF_CALCULATION_VERSION,
    }


def read_etf_report(data_dir, context, *, db):
    """Recompute the report using only its pinned basket and DataSnapshot."""
    day, cutoff = context['trade_date'], context['cutoff']
    basket, snapshot = context['basket'], context['snapshot']
    members = basket['members']
    extension = frozenset(context.get('calendar_extension', ()))
    if context['calculation_version'] != ETF_CALCULATION_VERSION:
        raise ValueError(f"未知 ETF 计算口径 {context['calculation_version']}")

    def read_day(selected_day):
        return read_basket_days(data_dir, snapshot, members=members, start=selected_day,
                                end=selected_day, cutoff=cutoff, db=db, extension=extension)[0]

    report = read_day(day)
    candidates = _candidate_dates(db, members, day, cutoff, snapshot, extension)
    latest_fields, latest_complete = _field_dates_and_complete_report(report, candidates, members, read_day)
    report = {
        **report, 'basket': {key: value for key, value in basket.items() if key != 'members'},
        'as_of': cutoff, 'view_date': instant(cutoff).date().isoformat(), 'use_mode': snapshot['use_mode'],
        'snapshot': snapshot, 'calculation_version': context['calculation_version'],
        'availability_assumption': (
            '使用已补采且可核验的公开时点。仅知披露日期时，从上海时间次日 00:00 起计入。'
            if snapshot['use_mode'] == RECONSTRUCTED_RESEARCH else None
        ),
        'latest_fields': latest_fields, 'latest_complete_date': latest_complete,
    }
    if 'disclosure_cutoff' in context:
        return attach_etf_disclosures(data_dir, report, snapshot=snapshot, catalog=disclosure_catalog_at(context, day),
                                      fixed_members=members, trade_date=day, cutoff=context['disclosure_cutoff'],
                                      db=db, extension=extension)
    return report


def build_etf_daily_report(data_dir, **options):
    """Read an ETF report without saving a frozen copy."""
    with database(data_dir) as db:
        ensure_schema(db, MARKET_SCHEMA)
        db.execute('BEGIN')
        context = prepare_etf_report(data_dir, db=db, **options)
        return read_etf_report(data_dir, context, db=db)
