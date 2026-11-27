"""Field selection and evidence for ETF observations in a DataSnapshot."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import re

from roll.market.calendar import is_session
from roll.v3.storage import SHANGHAI


ETF_UNITS = {'etf_shares': '份', 'etf_nav': '元/份', 'etf_split': '新份/旧份'}
ETF_SERIES = tuple(ETF_UNITS)
ETF_SELECTION_RULES = 'market-etf-v1'


def etf_symbol(symbol):
    normalized = symbol.upper()
    if not re.fullmatch(r'[0-9]{6}\.(SH|SZ)', normalized):
        raise ValueError('ETF 代码须带沪深市场后缀，例如 510300.SH 或 159915.SZ')
    return normalized


def exchange_source(symbol):
    return 'sse' if symbol.endswith('.SH') else 'szse'


def _amount(value, *, allow_zero):
    if not isinstance(value, (str, int)) or type(value) is bool:
        return None
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount < 0 or (not allow_zero and amount == 0):
        return None
    return amount


def etf_observation(item):
    """Normalize imported ETF evidence before it enters the shared observation store."""
    series = item['series']
    if series not in ETF_UNITS or item.get('unit') != ETF_UNITS[series]:
        raise ValueError('ETF 观察项单位须为份、元/份或新份/旧份')
    symbol = etf_symbol(item['symbol'])
    day = date.fromisoformat(item['trade_date'])
    if not is_session(day):
        raise ValueError(f'ETF 观察项日期 {day} 须为交易日')
    if not item.get('source') or not item.get('source_ref') or not item.get('received_at'):
        raise ValueError('ETF 观察项须保留来源、原始定位和实际取得时刻')
    if isinstance(item['received_at'], str) and len(item['received_at']) <= 10:
        raise ValueError('ETF 观察项的实际取得时间须具体到时刻')
    payload = item.get('payload', {})
    if not isinstance(payload, dict) or not isinstance(payload.get('verified', False), bool):
        raise ValueError('ETF 观察项须以 payload 保存原值和核验状态')
    raw_date = payload.get('source_date', str(day))
    date.fromisoformat(raw_date)
    disclosed = payload.get('disclosed_date')
    available = item.get('available_at')
    if isinstance(available, str) and len(available) == 10:
        if disclosed is not None and disclosed != available:
            raise ValueError('ETF 观察项的披露日期不一致')
        disclosed, available = available, None
    if disclosed is not None:
        date.fromisoformat(disclosed)
        if not item.get('available_evidence'):
            raise ValueError('ETF 披露日期须提供可核验的披露依据')
        payload = {**payload, 'disclosed_date': disclosed}

    quality = item.get('quality', 'usable')
    value = payload.get('value')
    amount = _amount(value, allow_zero=series == 'etf_shares')
    if amount is None and quality == 'usable' and not item.get('withdrawn'):
        raise ValueError('ETF 可用观察项须提供有效的十进制数值')
    return {**item, 'symbol': symbol, 'trade_date': str(day), 'quality': quality,
            'available_at': available,
            'payload': {**payload, 'value': str(value) if value is not None else None,
                        'source_date': raw_date, 'verified': payload.get('verified', False)}}


def etf_visible_at(row, snapshot):
    verified = row['available_at'] if row['available_evidence'] else None
    if snapshot['use_mode'] == 'RECONSTRUCTED_RESEARCH':
        if row['received_at'] > snapshot['as_of']:
            return None
        if verified:
            return verified
        disclosure_day = json.loads(row['payload']).get('disclosed_date')
        if disclosure_day and row['available_evidence']:
            boundary = date.fromisoformat(disclosure_day) + timedelta(days=1)
            return datetime.combine(boundary, time.min, SHANGHAI).astimezone(timezone.utc).isoformat(
                timespec='microseconds')
        return None
    if row['reconstruction_only'] or (snapshot['use_mode'] == 'STRICT_HISTORICAL_AS_OF' and not verified):
        return None
    return max(row['received_at'], verified or row['received_at'])


def _candidate_quality(row):
    series = row['series']
    payload = row['payload']
    if row['withdrawn']:
        return 'withdrawn'
    if row['quality'] != 'usable':
        return row['quality']
    if row['source'] in {'sse', 'szse'} and row['source'] != exchange_source(row['symbol']):
        return 'unverified'
    if payload.get('source_date') != row['trade_date']:
        return 'date_mismatch'
    if (payload.get('verified') is not True or not row['source_ref'] or
            not row['available_evidence']):
        return 'unverified'
    if row['unit'] != ETF_UNITS[series] or _amount(payload.get('value'), allow_zero=series == 'etf_shares') is None:
        return 'invalid_value'
    if series == 'etf_split' and row['source'] not in {exchange_source(row['symbol']), 'fund_manager'}:
        return 'unverified'
    return 'usable'


def _rank(row):
    source = row['source']
    if row['series'] == 'etf_nav':
        return 0 if source == 'fuyao' else 1 if source == 'fund_manager' else 2
    if row['series'] == 'etf_split':
        return 0
    return 0 if source == exchange_source(row['symbol']) else 1


def _basis(row):
    payload = row['payload']
    basis = (payload.get('split_required', False), payload.get('share_basis')) if row['series'] == 'etf_shares' else ()
    return Decimal(payload['value']), basis


def select_etf_observation(candidates):
    """Return the selected field and annotate each contemporaneous source."""
    for row in candidates:
        row['selection_quality'] = _candidate_quality(row)
    eligible = [row for row in candidates if row['selection_quality'] == 'usable']
    if not eligible:
        statuses = {row['selection_quality'] for row in candidates}
        if 'conflict' in statuses:
            return None, 'conflict'
        return None, next(iter(statuses)) if len(statuses) == 1 else 'unverified'
    eligible.sort(key=lambda row: (_rank(row), row['seq']))
    head = eligible[0]
    peers = [row for row in eligible if _rank(row) == _rank(head)]
    managers = [row for row in eligible if row['source'] == 'fund_manager']
    if head['series'] == 'etf_nav' and head['source'] == 'fuyao' and managers:
        if any(_basis(row) != _basis(managers[0]) for row in peers):
            peers = managers
            head = managers[0]
    unresolved = [row for row in candidates if row['selection_quality'] == 'conflict'
                  and _rank(row) <= _rank(head)]
    if head['series'] == 'etf_nav' and head['source'] == 'fund_manager':
        unresolved = [row for row in unresolved if row['source'] != 'fuyao']
    if unresolved or any(_basis(row) != _basis(head) for row in peers):
        return None, 'conflict'
    selected_value, _ = _basis(head)
    for row in candidates:
        if row is not head:
            value = _amount(row['payload'].get('value'), allow_zero=True)
            if value is not None and value != selected_value:
                row['difference'] = 'value_mismatch'
    return {**head, 'alternative_sources': [row['source'] for row in candidates if row is not head]}, 'usable'
