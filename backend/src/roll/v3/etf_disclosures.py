"""Read verified ETF disclosures and derive point-in-time basket membership."""

from collections import defaultdict
from datetime import date, datetime, time

from roll.v3.etf_observations import (
    DISCLOSURE_EVENT_SERIES, DISCLOSURE_EVENT_SYMBOL, HOLDING_REPORT_SERIES,
)
from roll.v3.market import RECONSTRUCTED_RESEARCH, read_snapshot, utc_timestamp
from roll.v3.storage import SHANGHAI, database


DISCLOSED_BASKET_VERSION = 'huijin-disclosed-wide-v1'
DISCLOSED_BASKET_NAME = '汇金已披露宽基 ETF 规则池'
HOLDERS = ('中央汇金投资有限责任公司', '中央汇金资产管理有限责任公司')


def etf_disclosure_scope(symbols, end):
    """Reports can carry forward from any earlier period."""
    return [
        {'series': HOLDING_REPORT_SERIES, 'symbol': symbol, 'start': str(date.min), 'end': end}
        for symbol in symbols
    ] + [{'series': DISCLOSURE_EVENT_SERIES, 'symbol': DISCLOSURE_EVENT_SYMBOL,
          'start': str(date.min), 'end': end}]


def etf_disclosure_day_cutoff(trade_date):
    """Bound a daily view at the end of its selected Shanghai calendar day."""
    return datetime.combine(date.fromisoformat(trade_date), time.max, SHANGHAI)


def _evidence(row):
    return {
        **row['payload'],
        'observation_seq': row['seq'], 'revision': row['revision'],
        'source': row['source'], 'source_ref': row['source_ref'],
        'source_locator': row['available_evidence'],
        'disclosed_at': row['available_at'], 'received_at': row['received_at'],
        'selected_available_at': row['selected_available_at'],
    }


def _report(row):
    return {**_evidence(row), 'report_id': row['item_id'], 'symbol': row['symbol'],
            'report_period_end': row['trade_date']}


def _fund_disclosure(reports, events):
    ordered = sorted(reports, key=lambda item: (item['report_period_end'],
                                                item['selected_available_at'], item['observation_seq']),
                     reverse=True)
    latest = next(iter(ordered), None)
    basis = next((report for report in ordered if report['comparable_named_holders']), None)
    disclosed = {row['holder']: row for row in basis['holders']} if basis else {}
    holders = []
    for name in HOLDERS:
        match = disclosed.get(name)
        status = 'listed' if match else 'not_listed_in_report' if basis else 'no_comparable_report'
        holders.append({
            **(match or {}), 'holder': name, 'status': status,
            'shares': match['shares'] if match else None,
            'listed_shares_pct': match['listed_shares_pct'] if match else None,
            'current_shares': None,
        })
    return {'latest_report': latest, 'basis_report': basis, 'holders': holders, 'events': events}


def _eligible(member, trade_date, cutoff, use_mode):
    if not member.get('eligible_by_wide_index_type'):
        return False
    if trade_date < max(member['listing_date'], member['effective_from']):
        return False
    if member['effective_to'] and trade_date >= member['effective_to']:
        return False
    return use_mode == RECONSTRUCTED_RESEARCH or utc_timestamp(member['known_at']) <= cutoff


def read_etf_disclosures(data_dir, snapshot_id, *, members, trade_date, cutoff=None, db=None):
    """Read scoped source facts and the single-per-fund rule pool at a frozen cutoff."""
    cutoff = cutoff or etf_disclosure_day_cutoff(trade_date)
    with database(data_dir, db=db) as connection:
        reports_read = read_snapshot(
            data_dir, snapshot_id, series=HOLDING_REPORT_SERIES, end=trade_date, cutoff=cutoff, db=connection,
        )
        snapshot = reports_read['snapshot']
        event_rows = read_snapshot(
            data_dir, snapshot, series=DISCLOSURE_EVENT_SERIES, end=trade_date, cutoff=cutoff, db=connection,
        )['observations']

    events = [{**_evidence(row), 'event_id': row['item_id']} for row in reversed(event_rows)
              if row['payload']['holder'] in HOLDERS]
    reports_by_symbol = defaultdict(list)
    for row in reports_read['observations']:
        reports_by_symbol[row['symbol']].append(_report(row))
    events_by_symbol = defaultdict(list)
    for event in events:
        if event['scope'] == 'fund':
            events_by_symbol[event['symbol']].append(event)

    funds = {}
    selected_members = []
    for member in members:
        symbol = member['symbol']
        fund = _fund_disclosure(reports_by_symbol[symbol], events_by_symbol[symbol])
        funds[symbol] = fund
        if (_eligible(member, trade_date, reports_read['cutoff'], snapshot['use_mode'])
                and any(row['status'] == 'listed' for row in fund['holders'])):
            selected_members.append(member)

    rule_pool = {
        'version': DISCLOSED_BASKET_VERSION, 'name': DISCLOSED_BASKET_NAME,
        'holders': list(HOLDERS), 'member_count': len(selected_members), 'members': selected_members,
    }
    return {
        'snapshot': snapshot, 'trade_date': trade_date, 'cutoff': reports_read['cutoff'],
        'rule_pool': rule_pool, 'funds': funds, 'events': events,
        'event_status': 'available' if events else 'no_verified_event',
        'availability_assumption': (
            'date_only_next_day_shanghai_and_catalog_listing_period'
            if snapshot['use_mode'] == RECONSTRUCTED_RESEARCH else 'actual_receipt_and_catalog_knowledge'
        ),
    }
