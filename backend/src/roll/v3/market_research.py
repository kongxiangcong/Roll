"""Export reproducible public market evidence from a frozen DataSnapshot."""

from datetime import date, datetime, time, timedelta
from hashlib import sha256
from itertools import accumulate, groupby
import json
from math import isfinite, sqrt
from pathlib import Path
from statistics import fmean, stdev

from roll.market.calendar import LAST_NOTICE_DAY, is_session
from roll.v3.industry_sources import MEMBERSHIP_FIELDS, METALS_ETF, STOCK, shenwan_observations
from roll.v3.market import SHANGHAI, append_observations, get_snapshot, read_snapshot, utc_timestamp


WINDOWS = (5, 10, 20, 60, 120)
DEFAULT_START = '2020-01-02'
DEFAULT_BENCHMARK = '000300.SH'
_BAR_FIELDS = (
    'open', 'high', 'low', 'close', 'volume', 'amount', 'turnover_rate', 'prior_close',
    'pre_close', 'pre_close_basis', 'trading_status',
)
_ADJUSTMENT_FIELDS = (
    'multiplier', 'offset', 'dividend_per_share', 'bonus_per_share', 'rights_per_share', 'rights_price',
)
_PROVENANCE_FIELDS = (
    'seq', 'series', 'symbol', 'trade_date', 'source', 'source_ref', 'revision',
    'available_at', 'available_evidence', 'received_at', 'selected_available_at',
    'assumed_available_at', 'availability_assumption', 'quality', 'reconstruction_only',
)


def _session_dates(start, end):
    cursor = date.fromisoformat(start)
    end = date.fromisoformat(end)
    sessions, unknown = [], []
    while cursor <= end:
        try:
            if is_session(cursor):
                sessions.append(cursor.isoformat())
        except ValueError:
            unknown.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return sessions, unknown


def _number(value):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def _close(row):
    return _number(row['payload'].get('close')) if row else None


def _effective(row):
    return row is not None and (_close(row) or 0) > 0 and row['payload'].get('trading_status') != 'suspended'


def _public_observation(row, payload_fields, unit_fields=()):
    return {**{key: row[key] for key in _PROVENANCE_FIELDS},
            'unit': {key: row['unit'][key] for key in unit_fields if key in row['unit']},
            'payload': {key: row['payload'][key] for key in payload_fields if key in row['payload']}}


def _continuous_dates(sessions, rows):
    current = []
    intervals = []
    for day in sessions:
        if _effective(rows.get(day)):
            current.append(day)
        elif current:
            intervals.append(current)
            current = []
    if current:
        intervals.append(current)
    return intervals


def _coverage(start, end, sessions, unknown, rows, snapshot_coverage):
    intervals = _continuous_dates(sessions, rows)
    states = {day: status for scope in snapshot_coverage for day, status in scope['quality_by_date'].items()}
    actual = sorted(rows)
    evaluable = {}
    for window in WINDOWS:
        ready = [interval[window:] for interval in intervals if len(interval) > window]
        evaluable[str(window)] = {
            'first_date': ready[0][0] if ready else None,
            'last_date': ready[-1][-1] if ready else None,
            'count': sum(map(len, ready)),
            'intervals': [{'start': interval[0], 'end': interval[-1]} for interval in ready],
        }
    return {
        'requested_start': start, 'requested_end': end,
        'first_date': actual[0] if actual else None, 'last_date': actual[-1] if actual else None,
        'expected_count': len(sessions), 'effective_count': sum(map(len, intervals)),
        'suspended_dates': [day for day in sessions if day in rows
                            and rows[day]['payload'].get('trading_status') == 'suspended'],
        'gap_dates': [day for day in sessions if day not in rows],
        'unusable_dates': [day for day in sessions if day in rows
                           and not _effective(rows[day])
                           and rows[day]['payload'].get('trading_status') != 'suspended'],
        'calendar_unknown_dates': unknown,
        'quality_by_date': states, 'evaluable': evaluable,
    }


def _averages(bars):
    averages = {}
    units = {}
    for field in ('volume', 'amount', 'turnover_rate'):
        values = [_number(row['payload'].get(field)) for row in bars]
        observed_units = {row['unit'].get(field) for row in bars}
        field_unit = next(iter(observed_units)) if len(observed_units) == 1 else None
        averages[f'average_{field}'] = fmean(values) if field_unit and None not in values else None
        if field_unit:
            units[field] = field_unit
    return {**averages, 'volume_change': (
        _values_change(bars, 'volume') if averages['average_volume'] is not None else None
    ), 'units': units}


def _values_change(rows, field):
    initial = _number(rows[0]['payload'][field])
    final = _number(rows[-1]['payload'][field])
    return final / initial - 1 if initial else None


def _return_metrics(factors):
    levels = list(accumulate(factors, lambda level, factor: level * factor, initial=1.0))
    peaks = accumulate(levels, max)
    return {
        'return': levels[-1] - 1,
        'annualized_volatility': stdev(factor - 1 for factor in factors) * sqrt(252),
        'max_drawdown': min(level / peak - 1 for level, peak in zip(levels, peaks)),
    }


def _daily_return(previous, row, adjustment):
    if adjustment:
        factor = adjustment['payload']
        multiplier, offset = _number(factor.get('multiplier')), _number(factor.get('offset'))
        if multiplier is not None and offset is not None:
            reference = previous * multiplier + offset
            if reference > 0:
                return _close(row) / reference, 'adjustment_factor'
    reference = _number(row['payload'].get('pre_close'))
    if reference and reference > 0 and reference != previous:
        return _close(row) / reference, 'reference_pre_close'
    return _close(row) / previous, 'raw_close'


def _windows(sessions, rows, adjustments):
    result = {}
    for window in WINDOWS:
        days = sessions[-(window + 1):]
        bars = [rows.get(day) for day in days]
        if len(days) <= window or not all(map(_effective, bars)):
            result[str(window)] = {'status': 'insufficient_coverage'}
            continue
        closes = list(map(_close, bars))
        factors, bases = zip(*[
            _daily_return(previous, row, adjustments.get(day))
            for day, previous, row in zip(days[1:], closes, bars[1:])
        ])
        result[str(window)] = {
            'status': 'usable', 'start': days[0], 'end': days[-1],
            'raw_close_start': closes[0], 'raw_close_end': closes[-1],
            'raw_close_return': closes[-1] / closes[0] - 1,
            'return_basis_counts': {basis: bases.count(basis) for basis in sorted(set(bases))},
            **_return_metrics(factors), **_averages(bars[1:]),
        }
    return result


def _relative_windows(left, right):
    return {
        window: {
            'status': 'usable', 'start': first['start'], 'end': first['end'],
            'relative_return': first['return'] - right[window]['return'],
        } if (first['status'] == right[window]['status'] == 'usable'
              and first['start'] == right[window]['start'] and first['end'] == right[window]['end'])
        else {'status': 'insufficient_coverage'}
        for window, first in left.items()
    }


def _membership_for_date(day, memberships):
    return next((row for row in memberships if
                 row['payload']['effective_start'] <= day <= row['payload']['effective_end']), None)


def _industry_comparisons(sessions, securities, adjustments, memberships, stock, benchmark, proxy):
    def comparison_basis(day):
        membership = _membership_for_date(day, memberships)
        index_symbol = membership['payload']['index_symbol'] if membership else None
        if membership and _effective(securities[index_symbol].get(day)):
            return 'industry_index', index_symbol, membership['seq'], None
        reason = 'industry_quotes_missing' if membership else 'membership_unverified'
        if proxy and _effective(securities[proxy].get(day)):
            return 'etf_proxy', proxy, None, reason
        return 'unavailable', None, None, reason

    result = []
    for (kind, symbol, evidence_seq, reason), group in groupby(sessions, key=comparison_basis):
        days = list(group)
        comparison = {'kind': kind, 'symbol': symbol, 'start': days[0], 'end': days[-1]}
        if reason:
            comparison['reason'] = reason
        if evidence_seq is not None:
            comparison['membership_seq'] = evidence_seq
        if kind == 'etf_proxy':
            comparison['proxy_evidence'] = METALS_ETF
        if symbol is not None:
            reference = _windows(days, securities[symbol], adjustments[symbol])
            comparison['stock_relative_windows'] = _relative_windows(
                _windows(days, securities[stock], adjustments[stock]), reference)
            comparison['benchmark_relative_windows'] = _relative_windows(
                reference, _windows(days, securities[benchmark], adjustments[benchmark]))
        result.append(comparison)
    return result


def _requested_end(snapshot, symbol, cutoff, requested):
    local = datetime.fromisoformat(cutoff).astimezone(SHANGHAI)
    complete = local.date() - timedelta(days=local.time() < time(15, 5))
    if requested:
        return min(date.fromisoformat(requested), complete).isoformat()
    frozen = [date.fromisoformat(scope['end']) for scope in snapshot['scope']
              if scope['symbol'] == symbol and scope['series'] == 'daily_bar']
    if not frozen:
        raise ValueError(f'数据快照没有 {symbol} 的日线范围，请通过 --end 指定查询截止日')
    return min(complete, max(frozen), LAST_NOTICE_DAY).isoformat()


def export_market_research(data_dir, symbol, *, snapshot_id, start=DEFAULT_START, end=None,
                           as_of=None, benchmark=DEFAULT_BENCHMARK):
    """Read only the designated security and public comparison series at the chosen cutoff."""
    symbol, benchmark = symbol.upper(), benchmark.upper()
    snapshot = get_snapshot(data_dir, snapshot_id)
    cutoff = min(utc_timestamp(as_of), snapshot['as_of']) if as_of else snapshot['as_of']
    start = date.fromisoformat(start).isoformat()
    end = _requested_end(snapshot, symbol, cutoff, end)
    if start > end:
        raise ValueError('研究起始日晚于最近完整交易日')
    sessions, unknown = _session_dates(start, end)

    membership_replay = read_snapshot(
        data_dir, snapshot_id, series='industry_membership', symbol=symbol, end=end, cutoff=cutoff,
    )
    memberships = sorted(
        (row for row in membership_replay['observations'] if row['payload']['effective_end'] >= start),
        key=lambda row: (row['payload']['effective_start'], row['seq']), reverse=True,
    )
    indices = tuple(dict.fromkeys(row['payload']['index_symbol'] for row in memberships))
    proxy = METALS_ETF['symbol'] if symbol == STOCK else None
    candidates = (symbol, benchmark, *indices, proxy)
    securities = {}
    quotes = {}
    adjustments = {}
    for code in dict.fromkeys(candidate for candidate in candidates if candidate is not None):
        replay = read_snapshot(data_dir, snapshot_id, symbol=code, start=start, end=end, cutoff=cutoff)
        rows = {row['trade_date']: row for row in replay['observations']}
        if code == proxy and code not in (symbol, benchmark, *indices) and not replay['coverage']:
            proxy = None
            continue
        factors = read_snapshot(data_dir, snapshot_id, series='adjustment_factor', symbol=code,
                                start=start, end=end, cutoff=cutoff)['observations']
        quotes[code] = rows
        adjustments[code] = {row['trade_date']: row for row in factors}
        securities[code] = {
            'coverage': _coverage(start, end, sessions, unknown, rows, replay['coverage']),
            'windows': _windows(sessions, rows, adjustments[code]),
            'observations': [_public_observation(row, _BAR_FIELDS, ('price', 'volume', 'amount', 'turnover_rate'))
                             for row in replay['observations']],
            'adjustment_factors': [_public_observation(row, _ADJUSTMENT_FIELDS, ('offset', 'dividend_per_share'))
                                   for row in factors],
        }

    report = {
        'symbol': symbol, 'snapshot_id': snapshot_id, 'as_of': cutoff, 'start': start, 'end': end,
        'snapshot': {key: snapshot[key] for key in ('as_of', 'use_mode', 'selection_rules_version')},
        'methodology': {
            'calendar': '上交所历年休市通知与修订',
            'window': 'N 个交易日的收盘到收盘计算需要 N+1 个连续有效收盘价',
            'return': ('日收盘价与参考昨收之比连乘减 1。先用快照内生效的除权因子计算参考价，'
                       '再用日线参考昨收，缺少两者时按原始收盘价计算。原始收盘收益单列。'),
            'annualized_volatility': '日收益率样本标准差乘以 √252',
            'max_drawdown': '从窗口基期收盘起计算相对历次高点的最大跌幅',
            'volume_change': '窗口首末日的成交量变化率',
            'relative_return': '同区间收益率之差，0.01 表示 1 个百分点',
        },
        'securities': securities,
        'industry_memberships': [_public_observation(row, MEMBERSHIP_FIELDS) for row in memberships],
        'industry_comparisons': _industry_comparisons(
            sessions, quotes, adjustments, memberships, symbol, benchmark, proxy),
        'benchmark': {'symbol': benchmark, 'windows': _relative_windows(
            securities[symbol]['windows'], securities[benchmark]['windows'])},
    }
    encoded = json.dumps(report, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    return {**report, 'reference': 'market-research:' + sha256(encoded).hexdigest()}


def _export(args, data_dir):
    return export_market_research(data_dir, args.symbol, snapshot_id=args.snapshot,
                                  start=args.start, end=args.end, as_of=args.as_of,
                                  benchmark=args.benchmark)


def _import_industry(args, data_dir):
    with Path(args.trend_capture).open(encoding='utf-8') as trend:
        trend_capture = json.load(trend, parse_float=str)
    with Path(args.members_capture).open(encoding='utf-8') as members:
        members_capture = json.load(members)
    end = args.end or datetime.fromisoformat(trend_capture['received_at']).astimezone(SHANGHAI).date().isoformat()
    rows = shenwan_observations(trend_capture, members_capture, start=args.start, end=end)
    return append_observations(data_dir, rows)


def register_market_research(research_subparsers):
    export = research_subparsers.add_parser('export', help='从数据快照导出公开行情、覆盖及多周期指标')
    export.add_argument('symbol')
    export.add_argument('--snapshot', required=True)
    export.add_argument('--start', default=DEFAULT_START)
    export.add_argument('--end')
    export.add_argument('--as-of')
    export.add_argument('--benchmark', default=DEFAULT_BENCHMARK)
    export.set_defaults(handler=_export)

    industry = research_subparsers.add_parser('import-industry', help='导入申万工业金属日线与江西铜业归属证据')
    industry.add_argument('trend_capture')
    industry.add_argument('members_capture')
    industry.add_argument('--start', default=DEFAULT_START)
    industry.add_argument('--end')
    industry.set_defaults(handler=_import_industry)
