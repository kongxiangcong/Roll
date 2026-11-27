"""Local watchlist persistence for the Roll workbench."""
import re

from roll.v3.market import utc_timestamp
from roll.v3.storage import database, ensure_schema


DEFAULT_WATCHLIST = (("600362.SH", "江西铜业"),)
KNOWN_NAMES = {
    "600362.SH": "江西铜业",
    "000300.SH": "沪深 300",
    "801055.SI": "申万工业金属",
    "512400.SH": "有色金属 ETF",
    "600150.SH": "中国船舶",
    "510300.SH": "沪深 300 ETF",
    "510500.SH": "中证 500 ETF",
    "159915.SZ": "创业板 ETF",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist_item (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    added_at TEXT NOT NULL
)
"""

_SYMBOL_RE = re.compile(r"^[0-9A-Z]{4,10}\.[A-Z]{2,4}$")


def normalize_symbol(symbol):
    code = (symbol or "").strip().upper()
    if not _SYMBOL_RE.fullmatch(code):
        raise ValueError("证券代码格式须如 600362.SH 或 000001.SZ")
    return code


def display_name(symbol, fallback=None):
    code = symbol.upper()
    return (fallback or "").strip() or KNOWN_NAMES.get(code) or code


def _initialize(db):
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='watchlist_item'"
    ).fetchone()
    if exists:
        return
    ensure_schema(db, _SCHEMA)
    now = utc_timestamp(None)
    db.executemany(
        "INSERT INTO watchlist_item (symbol, name, sort_order, added_at) VALUES (?, ?, ?, ?)",
        [(symbol, name, index, now) for index, (symbol, name) in enumerate(DEFAULT_WATCHLIST)],
    )


def _items(db):
    rows = db.execute(
        "SELECT symbol, name, sort_order, added_at FROM watchlist_item ORDER BY sort_order, added_at, symbol"
    ).fetchall()
    return [dict(row) for row in rows]


def list_watchlist(data_dir):
    with database(data_dir, write=True) as db:
        _initialize(db)
        return _items(db)


def add_watchlist(data_dir, symbol, *, name=None):
    code = normalize_symbol(symbol)
    label = display_name(code, name)
    now = utc_timestamp(None)
    with database(data_dir, write=True) as db:
        _initialize(db)
        existing = db.execute("SELECT symbol, name, sort_order, added_at FROM watchlist_item WHERE symbol=?", (code,)).fetchone()
        if existing:
            if name and name.strip() and existing["name"] != name.strip():
                db.execute("UPDATE watchlist_item SET name=? WHERE symbol=?", (name.strip(), code))
                return {**dict(existing), "name": name.strip()}
            return dict(existing)
        max_order = db.execute("SELECT COALESCE(MAX(sort_order), -1) FROM watchlist_item").fetchone()[0]
        db.execute(
            "INSERT INTO watchlist_item (symbol, name, sort_order, added_at) VALUES (?, ?, ?, ?)",
            (code, label, max_order + 1, now),
        )
    return {"symbol": code, "name": label, "sort_order": max_order + 1, "added_at": now}


def remove_watchlist(data_dir, symbol):
    code = normalize_symbol(symbol)
    with database(data_dir, write=True) as db:
        _initialize(db)
        db.execute("DELETE FROM watchlist_item WHERE symbol=?", (code,))
    return {"removed": code}


def reorder_watchlist(data_dir, symbols):
    requested = [normalize_symbol(symbol) for symbol in symbols]
    with database(data_dir, write=True) as db:
        _initialize(db)
        current = {item["symbol"]: item for item in _items(db)}
        ordered = [code for code in dict.fromkeys([*requested, *current]) if code in current]
        db.executemany(
            "UPDATE watchlist_item SET sort_order=? WHERE symbol=?",
            enumerate(ordered),
        )
        return _items(db)
