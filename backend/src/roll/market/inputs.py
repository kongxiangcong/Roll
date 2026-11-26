"""Dated AKShare market observations shared by the workbench, scoring and ETF replay."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from itertools import pairwise
import json
from pathlib import Path

from roll.db import connect
from roll.market.akshare_inputs import SourceFailure, share_units

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
BACKFILL_GROUPS = tuple(k for k in SYNC_GROUPS if k not in {"breadth", "valuation"})
SHANGHAI = timezone(timedelta(hours=8))


def initialize_inputs(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS market_inputs (
            series TEXT, symbol TEXT, trade_date TEXT, observation TEXT NOT NULL,
            PRIMARY KEY(series,symbol,trade_date));
        CREATE TABLE IF NOT EXISTS market_input_failures (
            series TEXT, symbol TEXT, trade_date TEXT, error TEXT NOT NULL, PRIMARY KEY(series,symbol,trade_date));
        CREATE TABLE IF NOT EXISTS market_input_status (
            series TEXT, symbol TEXT, last_success_at TEXT, last_error TEXT,
            PRIMARY KEY(series,symbol));
    """)


def input_rows(db, series, symbol, start, end):
    rows = [{"trade_date": day, **json.loads(payload)} for day, payload in db.execute(
        "SELECT trade_date,observation FROM market_inputs WHERE series=? AND symbol=? "
        "AND trade_date BETWEEN ? AND ? ORDER BY trade_date",
        (series, symbol, start or "", end or "9999"))]
    if series == "etf_shares":
        normalized = []
        for row in rows:
            try:
                row["shares"] = share_units(row["shares"])
            except (ValueError, ArithmeticError):
                continue
            normalized.append(row)
        return normalized
    return rows


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
    failures = {}
    fetch_error = None
    try:
        method = getattr(source, series.removeprefix("etf_"))
        for day, fields in method(symbol, days):
            if day not in wanted:
                continue
            if isinstance(fields, SourceFailure):
                failures[day] = fields.error
                continue
            if day in observations:
                raise ValueError("重复观察日")
            observations[day] = fields
    except Exception as exc:
        fetch_error = type(exc).__name__
    for day in wanted - observations.keys():
        failures.setdefault(day, fetch_error or "来源未返回该日")
    db.execute("BEGIN IMMEDIATE")
    try:
        _save(db, series, symbol, observations.items())
        db.executemany("DELETE FROM market_input_failures WHERE series=? AND symbol=? AND trade_date=?",
                       ((series, symbol, day) for day in observations))
        db.executemany("INSERT OR REPLACE INTO market_input_failures VALUES(?,?,?,?)",
                       ((series,symbol,day,error) for day,error in failures.items()))
        message = f"缺少 {len(failures)} 个交易日：" + "、".join(sorted(failures)[:8]) if failures else None
        _record_status(db, series, symbol, bool(observations), message)
        db.commit()
    except Exception:
        db.rollback()
        raise


def input_status(data_dir, start=None, end=None):
    with connect(data_dir / "roll.sqlite3") as db:
        initialize_inputs(db)
        result = [{**dict(row), "units": UNITS[row["series"]]} for row in db.execute("""
            SELECT s.*,MIN(m.trade_date) first_date,MAX(m.trade_date) last_date,
                COUNT(m.trade_date) count FROM market_input_status s LEFT JOIN market_inputs m
                ON s.series=m.series AND s.symbol=m.symbol AND m.trade_date BETWEEN ? AND ?
                GROUP BY s.series,s.symbol ORDER BY s.series,s.symbol""", (start or "", end or "9999"))]
        for row in result:
            row["failed_dates"] = [dict(r) for r in db.execute(
                "SELECT trade_date,error FROM market_input_failures WHERE series=? AND symbol=? "
                "AND trade_date BETWEEN ? AND ? ORDER BY trade_date",
                (row["series"],row["symbol"],start or "",end or "9999"))]
        return result


def sync_inputs(data_dir: Path, start=None, end=None, *, groups=None, funds=None, sector_etfs=(), source=None, missing_only=False):
    from roll.market.akshare_inputs import AkshareInputs
    from roll.market.akshare_timeout import bounded_requests

    if source is None:
        with bounded_requests(300 if start else 180):
            return sync_inputs(data_dir, start, end, groups=groups, funds=funds,
                               sector_etfs=sector_etfs, source=AkshareInputs(), missing_only=missing_only)

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
    def sync_series(series, exchange=None):
        if series.startswith("etf_"):
            symbols = tuple(dict.fromkeys((*funds, *sector_etfs)))
            if exchange:
                symbols = tuple(s for s in symbols if s.endswith("."+exchange))
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
                        first = max(finish - timedelta(days=30),
                                    min(begin, date.fromisoformat(row[0]) - timedelta(days=5)))
                days = [r["trade_date"] for r in input_rows(db, "calendar", "CN", first.isoformat(), finish.isoformat())]
                if days:
                    if missing_only:
                        present = {r["trade_date"] for r in input_rows(db, series, symbol,
                                                                      days[0], days[-1])}
                        days = [day for day in days if day not in present]
                    if days:
                        _sync_group(db, source, series, symbol, days)
                else:
                    _record_status(db, series, symbol, False, "请求范围无已知交易日")

    streams = [(series, exchange) for series in dict.fromkeys(groups)
               for exchange in (("SH","SZ") if series == "etf_shares" else (None,))]
    with ThreadPoolExecutor(max_workers=len(streams)) as pool:
        jobs = [pool.submit(copy_context().run, sync_series, series, exchange) for series,exchange in streams]
        for job in jobs:
            job.result()
    return input_status(data_dir, start, end) if missing_only else input_status(data_dir)
