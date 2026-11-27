"""Append-only versions of the fixed ETF comparison basket."""

from datetime import date
import json
from pathlib import Path

from roll.v3.etf_observations import etf_symbol
from roll.v3.market import utc_timestamp
from roll.v3.storage import database, ensure_schema, json_text


FIXED_BASKET_VERSION = 'fixed-35-v1'
_SCHEMA = """
CREATE TABLE IF NOT EXISTS etf_basket_version (
    version TEXT PRIMARY KEY,
    known_at TEXT NOT NULL,
    manifest TEXT NOT NULL
);
"""
_MEMBER_TEXT = (
    'symbol', 'name', 'fund_manager', 'listing_date', 'listing_source_ref', 'index_code',
    'index_name', 'group_name', 'index_source_ref', 'fund_tracking_source_ref', 'effective_from', 'known_at',
)


def get_fixed_basket(version=FIXED_BASKET_VERSION):
    """Load the original fixed comparison basket shipped with the workbench."""
    if version != FIXED_BASKET_VERSION:
        raise ValueError(f'未知 ETF 对照篮子版本 {version}')
    return json.loads(Path(__file__).with_name('fixed_etf_basket_v1.json').read_text(encoding='utf-8'))


def _text_fields(item, fields):
    return isinstance(item, dict) and all(isinstance(item.get(key), str) and item[key].strip() for key in fields)


def _known_at(value):
    if len(value) <= 10:
        raise ValueError('ETF 篮子及成员须记录实际获知时刻')
    return utc_timestamp(value)


def append_comparison_basket(data_dir, basket):
    """Append a complete identity manifest under a new immutable basket version."""
    if not _text_fields(basket, ('version', 'known_at', 'name', 'basket_sample_ref')):
        raise ValueError('ETF 对照篮子须提供名称、版本、原始依据及获知时刻')
    version, known = basket['version'], _known_at(basket['known_at'])
    if version == FIXED_BASKET_VERSION:
        raise ValueError('ETF 对照篮子修订须使用新版本')
    members = basket.get('members')
    if not isinstance(members, list) or not members or basket.get('member_count') != len(members):
        raise ValueError('ETF 对照篮子须提供与成员只数一致的完整成员名单')
    seen = set()
    for member in members:
        if not _text_fields(member, _MEMBER_TEXT):
            raise ValueError('ETF 篮子成员须提供基金与指数身份、时点及原始依据')
        symbol = etf_symbol(member['symbol'])
        if member['symbol'] != symbol or symbol in seen:
            raise ValueError('ETF 篮子成员代码须为标准格式且唯一')
        seen.add(symbol)
        date.fromisoformat(member['listing_date'])
        start = date.fromisoformat(member['effective_from'])
        end = member.get('effective_to')
        if _known_at(member['known_at']) > known or (end is not None and date.fromisoformat(end) <= start):
            raise ValueError(f'ETF 篮子成员 {symbol} 的获知时刻或生效区间无效')
        if 'index_symbol' not in member or 'effective_to' not in member:
            raise ValueError(f'ETF 篮子成员 {symbol} 须注明指数行情代码和失效日期，未知时可留空')
    manifest = json_text(basket)
    with database(data_dir, write=True) as db:
        ensure_schema(db, _SCHEMA)
        existing = db.execute('SELECT manifest FROM etf_basket_version WHERE version=?', (version,)).fetchone()
        if existing is not None:
            if existing['manifest'] != manifest:
                raise ValueError(f'ETF 对照篮子版本已存在 {version}')
            return {'version': version, 'appended': False}
        db.execute('INSERT INTO etf_basket_version VALUES (?, ?, ?)', (version, known, manifest))
    return {'version': version, 'appended': True}


def resolve_comparison_basket(db, *, cutoff, version=None):
    """Resolve the newest known revision or the selected eligible version."""
    if version == FIXED_BASKET_VERSION:
        return get_fixed_basket()
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='etf_basket_version'").fetchone():
        row = db.execute("""
            SELECT manifest FROM etf_basket_version
            WHERE known_at <= ? AND (? IS NULL OR version = ?)
            ORDER BY known_at DESC, rowid DESC LIMIT 1
        """, (cutoff, version, version)).fetchone()
        if row is not None:
            return json.loads(row['manifest'])
    if version is not None:
        raise ValueError(f'截止时刻没有可用的 ETF 对照篮子版本 {version}')
    return get_fixed_basket()


def comparison_basket_timeline(db, *, cutoff):
    """Return complete catalog revisions in their observed order, with the shipped baseline first."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='etf_basket_version'").fetchone():
        return [get_fixed_basket()]
    rows = db.execute("""
        SELECT manifest FROM etf_basket_version
        WHERE known_at <= ? ORDER BY known_at, rowid
    """, (cutoff,))
    return [get_fixed_basket(), *(json.loads(row['manifest']) for row in rows)]


def list_comparison_baskets(data_dir, *, as_of=None):
    """Expose the available fixed comparisons without loading membership into the browser."""
    with database(data_dir) as db:
        timeline = comparison_basket_timeline(db, cutoff=utc_timestamp(as_of))
    return [{key: basket[key] for key in ('version', 'known_at', 'name', 'member_count')}
            for basket in reversed(timeline)]
