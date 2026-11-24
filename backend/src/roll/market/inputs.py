"""Dated AKShare market observations shared by the workbench, scoring and ETF replay."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from itertools import pairwise
import json
from pathlib import Path

from roll.db import connect

BROAD_ETFS = ("510300.SH", "510500.SH", "159915.SZ", "588000.SH")
UNITS = {
    "etf_bars": {"open": "CNY/unit", "high": "CNY/unit", "low": "CNY/unit", "close": "CNY/unit"},
    "etf_shares": {"shares": "unit"},
    "etf_nav": {"nav": "CNY/unit"},
    "etf_flow": {"net_flow_yuan": "CNY"},
    "margin": {"balance_yuan": "CNY"},
    "breadth": {"advancing": "stocks", "declining": "stocks"},
    "turnover": {"turnover_yuan": "CNY"},
    "valuation": {"pe_ttm": "multiple", "pb": "multiple"},
    "calendar": {},
}
SYNC_GROUPS = tuple(k for k in UNITS if k not in {"etf_flow", "calendar"})
SHANGHAI = timezone(timedelta(hours=8))


def initialize_inputs(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS market_inputs (
            series TEXT, symbol TEXT, trade_date TEXT, observation TEXT NOT NULL,
            PRIMARY KEY(series,symbol,trade_date));
        CREATE TABLE IF NOT EXISTS market_input_status (
            series TEXT, symbol TEXT, last_success_at TEXT, last_error TEXT,
            PRIMARY KEY(series,symbol));
    """)


def input_rows(db, series, symbol, start, end):
    return [{"trade_date": day, **json.loads(payload)} for day, payload in db.execute(
        "SELECT trade_date,observation FROM market_inputs WHERE series=? AND symbol=? "
        "AND trade_date BETWEEN ? AND ? ORDER BY trade_date",
        (series, symbol, start or "", end or "9999"))]


def read_inputs(data_dir: Path, series: str, symbol: str, start=None, end=None):
    """Read an entire date range with one connection. Money and prices are decimal strings."""
    if series not in UNITS:
        raise ValueError("未知市场数据类型")
    with connect(data_dir / "roll.sqlite3") as db:
        initialize_inputs(db)
        if series != "etf_flow":
            return input_rows(db, series, symbol, start, end)
        previous = db.execute("SELECT MAX(trade_date) FROM market_inputs WHERE series='calendar' "
                              "AND symbol='CN' AND trade_date<?", (start or "",)).fetchone()[0]
        days = [r["trade_date"] for r in input_rows(db, "calendar", "CN", previous or start, end)]
        shares = {r["trade_date"]: Decimal(r["shares"])
                  for r in input_rows(db, "etf_shares", symbol, previous or start, end)}
        nav = {r["trade_date"]: Decimal(r["nav"]) for r in input_rows(db, "etf_nav", symbol, start, end)}
    return [{"trade_date": day, "previous_trade_date": prev,
             "net_flow_yuan": str((shares[day] - shares[prev]) * nav[day])}
            for prev, day in pairwise(days) if prev in shares and day in shares and day in nav]


def _save(db, series, symbol, observations):
    db.executemany("INSERT OR REPLACE INTO market_inputs VALUES(?,?,?,?)", [
        (series, symbol, day, json.dumps(fields)) for day, fields in observations])


def _record_status(db, series, symbol, success, error):
    now = datetime.now(SHANGHAI).isoformat() if success else None
    db.execute("""INSERT INTO market_input_status VALUES(?,?,?,?)
                  ON CONFLICT(series,symbol) DO UPDATE SET
                  last_success_at=COALESCE(excluded.last_success_at,market_input_status.last_success_at),
                  last_error=excluded.last_error""", (series, symbol, now, error))


def _sync_group(db, source, series, symbol, days):
    wanted = set(days)
    observations = {}
    problems = []
    try:
        method = getattr(source, series.removeprefix("etf_"))
        for day, fields in method(symbol, days):
            if day not in wanted:
                continue
            if day in observations:
                raise ValueError("重复观察日")
            observations[day] = fields
    except Exception as exc:
        problems.append(f"{series} 获取失败 ({type(exc).__name__})")
    missing = sorted(wanted - observations.keys())
    if missing:
        problems.append(f"缺少 {len(missing)} 个交易日：" + "、".join(missing[:8]))
    db.execute("BEGIN IMMEDIATE")
    try:
        _save(db, series, symbol, observations.items())
        _record_status(db, series, symbol, bool(observations), "；".join(problems) or None)
        db.commit()
    except Exception:
        db.rollback()
        raise


def input_status(data_dir, start=None, end=None):
    with connect(data_dir / "roll.sqlite3") as db:
        initialize_inputs(db)
        return [{**dict(row), "units": UNITS[row["series"]]} for row in db.execute("""
            SELECT s.*,MIN(m.trade_date) first_date,MAX(m.trade_date) last_date,
                COUNT(m.trade_date) count FROM market_input_status s LEFT JOIN market_inputs m
                ON s.series=m.series AND s.symbol=m.symbol AND m.trade_date BETWEEN ? AND ?
                GROUP BY s.series,s.symbol ORDER BY s.series,s.symbol""", (start or "", end or "9999"))]


def sync_inputs(data_dir: Path, start=None, end=None, *, groups=None, funds=None, sector_etfs=(), source=None):
    from roll.market.akshare_inputs import AkshareInputs
    from roll.market.akshare_timeout import bounded_requests

    if source is None:
        with bounded_requests(300 if start else 180):
            return sync_inputs(data_dir, start, end, groups=groups, funds=funds,
                               sector_etfs=sector_etfs, source=AkshareInputs())

    groups = tuple(groups or SYNC_GROUPS)
    if set(groups) - set(SYNC_GROUPS):
        raise ValueError("未知市场同步类型")
    now = datetime.now(SHANGHAI)
    last_complete = now.date() if now.hour >= 15 else now.date() - timedelta(days=1)
    finish = date.fromisoformat(end) if end else last_complete
    begin = date.fromisoformat(start) if start else finish - timedelta(days=5)
    if begin > finish or finish > last_complete:
        raise ValueError("无效盘后交易日范围")

    funds = tuple(funds or BROAD_ETFS)
    with connect(data_dir / "roll.sqlite3") as db:
        initialize_inputs(db)
        try:
            calendar = sorted(set(day for day in source.calendar() if day <= last_complete.isoformat()))
            if not calendar:
                raise ValueError("交易日历为空")
            db.execute("BEGIN IMMEDIATE")
            _save(db, "calendar", "CN", [(day, {}) for day in calendar])
            _record_status(db, "calendar", "CN", True, None)
            db.commit()
        except Exception as exc:
            db.rollback()
            _record_status(db, "calendar", "CN", False, f"交易日历获取失败 ({type(exc).__name__})")
    def sync_series(series):
        if series.startswith("etf_"):
            symbols = tuple(dict.fromkeys((*funds, *sector_etfs))) if series == "etf_bars" else funds
        else:
            symbols = ("000300.SH",) if series == "valuation" else ("CN",)
        with connect(data_dir / "roll.sqlite3") as db:
            for symbol in symbols:
                first = begin
                if start is None:
                    row = db.execute("SELECT MAX(trade_date) FROM market_inputs WHERE "
                                     "series=? AND symbol=? AND trade_date<=?",
                                     (series, symbol, finish.isoformat())).fetchone()
                    if row[0]:
                        first = min(begin, date.fromisoformat(row[0]) - timedelta(days=5))
                days = [r["trade_date"] for r in input_rows(db, "calendar", "CN", first.isoformat(), finish.isoformat())]
                if days:
                    _sync_group(db, source, series, symbol, days)
                else:
                    _record_status(db, series, symbol, False, "请求范围无已知交易日")

    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(copy_context().run, sync_series, series) for series in dict.fromkeys(groups)]
        for job in jobs:
            job.result()
    return input_status(data_dir)
