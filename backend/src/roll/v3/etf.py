"""Exact, offline ETF daily estimates from a frozen DataSnapshot."""

from datetime import date, timedelta
from decimal import Decimal, localcontext

from roll.market.calendar import SSE_HISTORICAL_HOLIDAYS, extended_sessions, is_session
from roll.v3.etf_observations import ETF_SERIES, etf_symbol
from roll.v3.market import LIVE_RUN, freeze_snapshot, read_snapshot
from roll.v3.storage import database, instant, sessions


def previous_etf_session(trade_date, extension=None):
    day = date.fromisoformat(trade_date)
    if not is_session(day, extension):
        raise ValueError(f'{day} 不是交易日')
    day -= timedelta(days=1)
    first_year = min(SSE_HISTORICAL_HOLIDAYS)
    while day.year >= first_year:
        if is_session(day, extension):
            return str(day)
        day -= timedelta(days=1)
    return None


def _etf_sessions(start, end, extension):
    days = list(sessions(start, end, extension))
    if not days:
        raise ValueError('ETF 区间须包含交易日')
    return days


def etf_snapshot_scope(symbols, start, end, extension=None):
    """Scope ETF estimates including the prior session's shares."""
    days = _etf_sessions(start, end, extension)
    lookback = previous_etf_session(days[0], extension) or days[0]
    return [
        {'series': series, 'symbol': etf_symbol(symbol),
         'start': lookback if series == 'etf_shares' else days[0], 'end': days[-1]}
        for symbol in symbols for series in ETF_SERIES
    ]


def freeze_etf_snapshot(data_dir, *, symbols, start, end, as_of=None, use_mode=LIVE_RUN, db=None):
    """Freeze every field needed to replay ETF daily estimates in the range."""
    with database(data_dir, write=True, db=db) as connection:
        scope = etf_snapshot_scope(symbols, start, end, extended_sessions(connection))
        return freeze_snapshot(data_dir, as_of=instant(as_of), use_mode=use_mode, scope=scope, db=connection)


def _field(records, series, day):
    item = records[series].get(day)
    if item is None:
        return {'status': 'missing', 'selected': None, 'candidates': []}
    return {key: item[key] for key in ('status', 'selected', 'candidates')}


def _payload(field):
    return field['selected']['payload'] if field['selected'] else {}


def _value(field):
    value = _payload(field).get('value')
    return Decimal(value) if value is not None else None


def _text(amount):
    return format(amount, 'f') if amount is not None else None


def _etf_day(records, symbol, day, previous):
    inputs = {
        'shares': _field(records, 'etf_shares', day),
        'previous_shares': _field(records, 'etf_shares', previous),
        'nav': _field(records, 'etf_nav', day),
        'split': _field(records, 'etf_split', day),
    }
    shares, prior, nav, split = map(_value, inputs.values())
    missing = {field: inputs[field]['status']
               for field in ('shares', 'previous_shares', 'nav') if inputs[field]['selected'] is None}

    today_basis = _payload(inputs['shares'])
    previous_basis = _payload(inputs['previous_shares'])
    basis_changed = ('share_basis' in today_basis and 'share_basis' in previous_basis
                     and today_basis['share_basis'] != previous_basis['share_basis'])
    if split is None:
        split_status = inputs['split']['status']
        if basis_changed or today_basis.get('split_required') or split_status not in {'missing', 'withdrawn', 'not_visible'}:
            missing['split'] = 'conversion_basis_unverified' if split_status == 'missing' else split_status
    comparable = flow = assets = None
    with localcontext() as context:
        precision = [len(value.as_tuple().digits) + abs(value.as_tuple().exponent)
                     for value in (shares, prior, nav, split) if value is not None]
        context.prec = max(context.prec, 4 * max(precision, default=0))
        if prior is not None and 'split' not in missing:
            comparable = prior if split is None else prior * split
        if not missing:
            flow = (shares - comparable) * nav
        if shares is not None and nav is not None:
            assets = shares * nav
    return {
        'symbol': symbol, 'trade_date': day, 'previous_trade_date': previous,
        'shares': _text(shares), 'previous_shares': _text(prior),
        'comparable_previous_shares': _text(comparable), 'nav': _text(nav),
        'split_ratio': _text(split), 'flow_cny': _text(flow), 'assets_cny': _text(assets),
        'missing': missing, 'inputs': inputs,
    }


def read_etf_days(data_dir, snapshot_id, *, symbol, start, end, cutoff=None, db=None, extension=None):
    """Calculate ordered ETF rows and return the evidence for each input."""
    symbol = etf_symbol(symbol)
    records = {}
    with database(data_dir, db=db) as connection:
        if extension is None:
            extension = extended_sessions(connection)
        days = _etf_sessions(start, end, extension)
        previous = previous_etf_session(days[0], extension)
        for series in ETF_SERIES:
            report = read_snapshot(data_dir, snapshot_id, series=series, symbol=symbol, start=previous or days[0],
                                   end=days[-1], cutoff=cutoff, include_candidates=True, db=connection)
            records[series] = {item['trade_date']: item for item in report['items']}
    return [_etf_day(records, symbol, day, prior)
            for day, prior in zip(days, [previous, *days[:-1]])]


def read_etf_day(data_dir, snapshot_id, *, symbol, trade_date, cutoff=None, db=None):
    """Read and independently calculate one trading-day ETF row."""
    return read_etf_days(data_dir, snapshot_id, symbol=symbol, start=trade_date,
                         end=trade_date, cutoff=cutoff, db=db)[0]
