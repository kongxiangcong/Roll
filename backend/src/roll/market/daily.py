"""Fuyao daily history, corporate actions and local, explicitly anchored price reads."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from contextlib import nullcontext
import json
import os
from pathlib import Path

import httpx

from roll.config import load_runtime_environment, load_watchlist
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
        CREATE TABLE IF NOT EXISTS daily_gaps(
            symbol TEXT, start TEXT, end TEXT, error TEXT NOT NULL, PRIMARY KEY(symbol,start,end));
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
    if not isinstance(body, dict) or type(body.get("code")) is not int:
        raise ValueError("扶摇业务响应缺少数字码")
    if body["code"] != 0:
        raise ValueError(f"扶摇业务码 {body['code']}")
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


def _windows(db, symbol, start, end):
    finish = date.fromisoformat(end)
    pending = []
    if start is None:
        last = db.execute("SELECT MAX(trade_date) FROM daily_bars WHERE symbol=?", (symbol,)).fetchone()[0]
        first = min(date.fromisoformat(last), finish)-timedelta(days=5) if last else finish-timedelta(days=365*6)
        pending.extend((date.fromisoformat(r[0]), min(date.fromisoformat(r[1]), finish))
                       for r in db.execute("SELECT start,end FROM daily_gaps WHERE symbol=? AND start<=?",
                                           (symbol, end)))
    else:
        first = date.fromisoformat(start)
    pending.append((first, finish))
    # Merge overlapping retry and refresh windows before dividing into bounded source requests.
    combined = []
    for left, right in sorted(pending):
        if combined and left <= combined[-1][1] + timedelta(days=1):
            combined[-1] = (combined[-1][0], max(right, combined[-1][1]))
        else:
            combined.append((left, right))
    for left, right in combined:
        while left <= right:
            stop = min(left+timedelta(days=364), right)
            yield left.isoformat(), stop.isoformat()
            left = stop + timedelta(days=1)


def _clear_gaps(db, symbol, start, end):
    overlapping = db.execute("SELECT start,end,error FROM daily_gaps WHERE symbol=? AND start<=? AND end>=?",
                             (symbol, end, start)).fetchall()
    for left, right, error in overlapping:
        db.execute("DELETE FROM daily_gaps WHERE symbol=? AND start=? AND end=?", (symbol,left,right))
        if left < start:
            previous = date.fromisoformat(start)-timedelta(days=1)
            db.execute("INSERT INTO daily_gaps VALUES (?,?,?,?)", (symbol,left,str(previous),error))
        if right > end:
            following = date.fromisoformat(end)+timedelta(days=1)
            db.execute("INSERT INTO daily_gaps VALUES (?,?,?,?)", (symbol,str(following),right,error))


def _sync_window(db, client, symbol, kind, start, end, today):
    # Source forward series uses its current anchor, including actions after historical end.
    actions = _actions(client, symbol, start, today) if kind == "stock" else {}
    bars = _prices(client, symbol, kind, start, end, "none" if kind == "stock" else None)
    if kind == "stock":
        check = _prices(client, symbol, kind, start, end, "forward")
        if bars.keys() != check.keys():
            raise ValueError("原始与前复权交易日不匹配")
        for day, values in bars.items():
            scale, shift = _transform(actions, day, today)
            if any(abs(price * scale + shift - target) > Decimal("0.011")
                   for price, target in zip(values, check[day])):
                raise ValueError(f"{day} 除权因子与扶摇前复权 OHLC 不符")
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
        _clear_gaps(db, symbol, start, end)
        db.execute("INSERT OR REPLACE INTO daily_sync VALUES (?,?,NULL)",
                   (symbol, datetime.now(SHANGHAI).isoformat()))
        db.commit()
    except Exception:
        db.rollback()
        raise


def sync_market(data_dir: Path, start=None, end=None, *, client=None, watchlist=None):
    load_runtime_environment()
    now = datetime.now(SHANGHAI)
    today = now.date().isoformat()
    end = end or (now.date() if now.hour >= 15 else now.date() - timedelta(days=1)).isoformat()
    if date.fromisoformat(end) > now.date() or (start and date.fromisoformat(start) > date.fromisoformat(end)):
        raise ValueError("无效行情日期区间")
    items = load_watchlist(watchlist)
    symbols = {item["code"]: "stock" for item in items}
    symbols["000300.SH"] = "index"
    connection = nullcontext(client) if client is not None else httpx.Client()
    with connection as client, connect(data_dir / "roll.sqlite3") as db:
        initialize_market(db)
        db.execute("CREATE TABLE IF NOT EXISTS watchlist_config(id INTEGER PRIMARY KEY, items TEXT NOT NULL)")
        db.execute("INSERT OR REPLACE INTO watchlist_config VALUES (1,?)", (json.dumps(items, ensure_ascii=False),))
        for symbol, kind in symbols.items():
            for left, right in _windows(db, symbol, start, end):
                try:
                    _sync_window(db, client, symbol, kind, left, right, today)
                except (ValueError, KeyError, TypeError, InvalidOperation, httpx.HTTPError) as exc:
                    error = str(exc) if type(exc) is ValueError else type(exc).__name__
                    db.execute("BEGIN IMMEDIATE")
                    try:
                        _clear_gaps(db, symbol, left, right)
                        db.execute("INSERT INTO daily_gaps VALUES (?,?,?,?)", (symbol,left,right,error))
                        db.execute("""INSERT INTO daily_sync(symbol,error) VALUES (?,?)
                                      ON CONFLICT(symbol) DO UPDATE SET error=excluded.error""", (symbol,error))
                        db.commit()
                    except Exception:
                        db.rollback()
                        raise
    return market_status(data_dir)


def read_bars(data_dir: Path, symbol, start=None, end=None, adjustment="raw"):
    return _history(data_dir, symbol, start, end, adjustment, indicators=False)


def read_indicators(data_dir: Path, symbol, start=None, end=None, adjustment="forward"):
    return _history(data_dir, symbol, start, end, adjustment, indicators=True)


def _history(data_dir, symbol, start, end, adjustment, indicators):
    with connect(data_dir / "roll.sqlite3") as db:
        initialize_market(db)
        return history_in_transaction(db, symbol, start, end, adjustment, indicators)


def history_in_transaction(db, symbol, start, end, adjustment, indicators):
    if adjustment not in {"raw", "forward", "backward"}:
        raise ValueError("未知行情口径")
    rows = db.execute("""SELECT * FROM daily_bars WHERE symbol=? AND trade_date BETWEEN ? AND ?
                         ORDER BY trade_date""", (symbol, "" if indicators else start or "", end or "9999")).fetchall()
    actions = {r["ex_date"]: (Decimal(r["multiplier"]), Decimal(r["offset_yuan"]))
               for r in db.execute("SELECT * FROM adjustment_factors WHERE symbol=?", (symbol,))}
    first = next((row["trade_date"] for row in rows if row["trade_date"] >= (start or "")), None)
    if first is None:
        return []
    anchor = rows[-1]["trade_date"] if adjustment == "forward" else first
    closes = []
    atr = None
    tr_sum = ZERO
    history = []
    for row in rows:
        day = row["trade_date"]
        scale, shift = (ONE, ZERO) if adjustment == "raw" else _transform(actions, day, anchor)
        prices = {key: Decimal(row[key + "_raw"]) * scale + shift for key in OHLC}
        item = {"symbol": symbol, "trade_date": day, **{key: str(value) for key, value in prices.items()}}
        if indicators:
            high, low = prices["high"], prices["low"]
            previous = closes[-1] if closes else prices["close"]
            tr = max(high-low, abs(high-previous), abs(low-previous))
            closes.append(prices["close"])
            if len(closes) <= 14:
                tr_sum += tr
                if len(closes) == 14:
                    atr = tr_sum / 14
            else:
                atr = (13 * atr + tr) / 14
            item["atr14"] = str(atr) if atr is not None else None
            for n in (20, 60):
                item[f"ma{n}"] = str(sum(closes[-n:]) / n) if len(closes) >= n else None
        if day >= first:
            history.append(item)
    return history


def market_status(data_dir: Path, end=None):
    with connect(data_dir / "roll.sqlite3") as db:
        initialize_market(db)
        return status_in_transaction(db, end)


def status_in_transaction(db, end):
    rows = []
    symbols = dict(SYMBOLS)
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='watchlist_config'").fetchone():
        config = db.execute("SELECT items FROM watchlist_config WHERE id=1").fetchone()
        symbols = {item["code"]: "stock" for item in json.loads(config[0])} if config else {}
        symbols["000300.SH"] = "index"
    for symbol, kind in symbols.items():
        bounds = db.execute("""SELECT MIN(trade_date) first_date, MAX(trade_date) last_date,
                               COUNT(*) count FROM daily_bars WHERE symbol=? AND trade_date<=?""",
                            (symbol, end or "9999")).fetchone()
        last = db.execute("SELECT close_raw FROM daily_bars WHERE symbol=? AND trade_date=?",
                          (symbol, bounds["last_date"])).fetchone()
        status = db.execute("SELECT last_success_at, error FROM daily_sync WHERE symbol=?", (symbol,)).fetchone()
        gaps = [dict(r) for r in db.execute(
            "SELECT start,end,error FROM daily_gaps WHERE symbol=? AND start<=? ORDER BY start",
            (symbol, end or "9999"))]
        rows.append({"symbol": symbol, "kind": kind, "gaps": gaps, **dict(bounds), "close": last[0] if last else None,
                     "last_success_at": status[0] if status else None, "error": status[1] if status else None})
    return rows
