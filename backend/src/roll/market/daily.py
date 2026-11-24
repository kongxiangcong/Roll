"""Fuyao daily history, corporate actions and local, explicitly anchored price reads."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path

import httpx

from roll.config import load_runtime_environment
from roll.db import connect


FUYAO = "https://fuyao.aicubes.cn"
SHANGHAI = timezone(timedelta(hours=8))
SYMBOLS = {"600362.SH": "stock", "000300.SH": "index"}
OHLC = ("open", "high", "low", "close")
ZERO = Decimal(0)
ONE = Decimal(1)


def initialize_market(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS daily_bars (
            symbol TEXT, trade_date TEXT, open_raw TEXT NOT NULL, high_raw TEXT NOT NULL,
            low_raw TEXT NOT NULL, close_raw TEXT NOT NULL,
            PRIMARY KEY (symbol, trade_date));
        CREATE TABLE IF NOT EXISTS adjustment_factors (
            symbol TEXT, ex_date TEXT, multiplier TEXT NOT NULL, offset_yuan TEXT NOT NULL,
            PRIMARY KEY (symbol, ex_date));
        CREATE TABLE IF NOT EXISTS daily_sync (
            symbol TEXT PRIMARY KEY, last_success_at TEXT, error TEXT);
    """)


def _day(value):
    return datetime.fromtimestamp(int(value) / 1000, SHANGHAI).date().isoformat()


def _millis(day, at=time.min):
    return int(datetime.combine(date.fromisoformat(day), at, SHANGHAI).timestamp() * 1000)


def _number(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("非有限数值")
    return result


def _get(client, path, symbol, params):
    token = os.environ.get("FUYAO_API_KEY")
    if not token:
        raise ValueError("FUYAO_API_KEY 未配置")
    response = client.get(FUYAO + path, params={"thscode": symbol, **params},
                          headers={"X-api-key": token}, follow_redirects=False, timeout=20)
    if response.status_code != 200:
        raise ValueError(f"扶摇 HTTP {response.status_code}")
    body = response.json()
    if type(body.get("code")) is not int or body["code"] != 0:
        raise ValueError("扶摇业务响应失败")
    data = body["data"]
    if not isinstance(data, dict) or not isinstance(data.get("item"), list):
        raise ValueError("扶摇响应缺少明细")
    if data.get("thscode", symbol if "a-share-index" in path else None) != symbol:
        raise ValueError("证券代码不符")
    return data


def _prices(client, symbol, kind, start, end, adjustment):
    prefix = "a-share-index" if kind == "index" else "a-share"
    params = {"start": _millis(start), "end": _millis(end, time.max), "interval": "1d"}
    if adjustment is not None:
        params["adjust"] = adjustment
    data = _get(client, f"/api/{prefix}/prices/historical", symbol, params)
    if data.get("adjust") != adjustment or data.get("interval", "1d") != "1d":
        raise ValueError("行情口径不符")
    bars = {}
    for item in data["item"]:
        day = _day(item["date_ms"])
        if start <= day <= end:
            prices = tuple(_number(item[key + "_price"]) for key in OHLC)
            o, h, low, c = prices
            if day in bars or min(o, c) < low or max(o, c) > h:
                raise ValueError("重复日期或 OHLC 范围错误")
            if adjustment != "forward" and low <= 0:
                raise ValueError("原始价格必须大于零")
            bars[day] = prices
    return bars


def _actions(client, symbol, start, end):
    data = _get(client, "/api/a-share/corporate-actions/adjustment-factors",
                symbol, {"from": start, "to": end})
    result = {}
    for item in data["item"]:
        day = _day(item["ex_date_ms"])
        if not start <= day <= end:
            continue
        if item["ticker"] != symbol.split(".")[0] or day in result:
            raise ValueError("除权事件代码或日期冲突")
        cash = _number(item["dividend_per_share"])
        bonus = _number(item["per_share_bonus"])
        rights = _number(item.get("allotment_ratio", 0))
        subscription = _number(item["allotment_price"]) if rights else ZERO
        if min(cash, bonus, rights, subscription) < 0:
            raise ValueError("无效公司行动数值")
        scale = ONE / (ONE + bonus + rights)
        result[day] = (scale, (rights * subscription - cash) * scale)
    return result


def _transform(actions, day, anchor):
    scale, shift = ONE, ZERO
    for event_day, (factor, offset) in sorted(actions.items()):
        if min(day, anchor) < event_day <= max(day, anchor):
            scale, shift = scale * factor, shift * factor + offset
    if anchor < day:
        return ONE / scale, -shift / scale
    return scale, shift


def _sync_symbol(db, client, symbol, kind, start, end, today):
    last_day = db.execute("SELECT MAX(trade_date) FROM daily_bars WHERE symbol=?", (symbol,)).fetchone()[0]
    finish = date.fromisoformat(end)
    if start is None:
        start = ((min(date.fromisoformat(last_day), finish) - timedelta(days=5))
                 if last_day else finish - timedelta(days=365 * 6)).isoformat()
    # Source forward series uses its current anchor, including actions after historical end.
    actions = _actions(client, symbol, start, today) if kind == "stock" else {}
    bars = {}
    cursor = date.fromisoformat(start)
    while cursor <= finish:
        stop = min(cursor + timedelta(days=364), finish)
        window = (cursor.isoformat(), stop.isoformat())
        raw = _prices(client, symbol, kind, *window, "none" if kind == "stock" else None)
        if kind == "stock":
            check = _prices(client, symbol, kind, *window, "forward")
            if raw.keys() != check.keys():
                raise ValueError("原始与前复权交易日不匹配")
            for day, values in raw.items():
                scale, shift = _transform(actions, day, today)
                if any(abs(price * scale + shift - target) > Decimal("0.011")
                       for price, target in zip(values, check[day])):
                    raise ValueError(f"{day} 除权因子与扶摇前复权 OHLC 不符")
        bars.update(raw)
        cursor = stop + timedelta(days=1)
    if not bars:
        raise ValueError("请求区间无日线")
    db.execute("BEGIN IMMEDIATE")
    try:
        db.executemany("INSERT OR REPLACE INTO daily_bars VALUES (?,?,?,?,?,?)",
                       [(symbol, day, *map(str, values)) for day, values in bars.items()])
        if kind == "stock":
            db.execute("DELETE FROM adjustment_factors WHERE symbol=? AND ex_date BETWEEN ? AND ?",
                       (symbol, start, today))
            db.executemany("INSERT INTO adjustment_factors VALUES (?,?,?,?)",
                           [(symbol, day, str(s), str(b)) for day, (s, b) in actions.items()])
        db.execute("INSERT OR REPLACE INTO daily_sync VALUES (?,?,NULL)",
                   (symbol, datetime.now(SHANGHAI).isoformat()))
        db.commit()
    except Exception:
        db.rollback()
        raise


def sync_market(data_dir: Path, start=None, end=None, *, client=None):
    load_runtime_environment()
    now = datetime.now(SHANGHAI)
    today = now.date().isoformat()
    end = end or (now.date() if now.hour >= 15 else now.date() - timedelta(days=1)).isoformat()
    if date.fromisoformat(end) > now.date() or (start and date.fromisoformat(start) > date.fromisoformat(end)):
        raise ValueError("无效行情日期区间")
    if client is None:
        with httpx.Client() as live:
            return sync_market(data_dir, start, end, client=live)
    with connect(data_dir / "roll.sqlite3") as db:
        initialize_market(db)
        for symbol, kind in SYMBOLS.items():
            try:
                _sync_symbol(db, client, symbol, kind, start, end, today)
            except (ValueError, KeyError, TypeError, InvalidOperation, httpx.HTTPError) as exc:
                # Keep the last committed result and avoid echoing untrusted payloads.
                error = str(exc) if type(exc) is ValueError else type(exc).__name__
                db.execute("""INSERT INTO daily_sync(symbol,error) VALUES (?,?)
                              ON CONFLICT(symbol) DO UPDATE SET error=excluded.error""", (symbol, error))
    return market_status(data_dir)


def read_bars(data_dir: Path, symbol, start=None, end=None, adjustment="raw"):
    if adjustment not in {"raw", "forward", "backward"}:
        raise ValueError("未知行情口径")
    with connect(data_dir / "roll.sqlite3") as db:
        initialize_market(db)
        rows = db.execute("""SELECT * FROM daily_bars WHERE symbol=? AND trade_date BETWEEN ? AND ?
                             ORDER BY trade_date""", (symbol, start or "", end or "9999")).fetchall()
        actions = {r["ex_date"]: (Decimal(r["multiplier"]), Decimal(r["offset_yuan"]))
                   for r in db.execute("SELECT * FROM adjustment_factors WHERE symbol=?", (symbol,))}
    if not rows:
        return []
    anchor = rows[-1 if adjustment == "forward" else 0]["trade_date"]
    history = []
    for row in rows:
        day = row["trade_date"]
        scale, shift = (ONE, ZERO) if adjustment == "raw" else _transform(actions, day, anchor)
        history.append({"symbol": symbol, "trade_date": day, **{
            key: str(Decimal(row[key + "_raw"]) * scale + shift) for key in OHLC}})
    return history


def market_status(data_dir: Path, end=None):
    with connect(data_dir / "roll.sqlite3") as db:
        initialize_market(db)
        return status_in_transaction(db, end)


def status_in_transaction(db, end):
    rows = []
    for symbol, kind in SYMBOLS.items():
        bounds = db.execute("""SELECT MIN(trade_date) first_date, MAX(trade_date) last_date,
                               COUNT(*) count FROM daily_bars WHERE symbol=? AND trade_date<=?""",
                            (symbol, end or "9999")).fetchone()
        last = db.execute("SELECT close_raw FROM daily_bars WHERE symbol=? AND trade_date=?",
                          (symbol, bounds["last_date"])).fetchone()
        status = db.execute("SELECT last_success_at, error FROM daily_sync WHERE symbol=?", (symbol,)).fetchone()
        rows.append({"symbol": symbol, "kind": kind, **dict(bounds), "close": last[0] if last else None,
                     "last_success_at": status[0] if status else None, "error": status[1] if status else None})
    return rows
