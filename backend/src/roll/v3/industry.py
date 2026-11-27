"""Published level-one industry observations for the market workbench."""

from collections import defaultdict
from datetime import date, time, timedelta
from decimal import Decimal, InvalidOperation
from itertools import groupby

from roll.market.calendar import extended_sessions, is_session, latest_session, SSE_HISTORICAL_HOLIDAYS
from roll.v3.market import DEFAULT_SOURCE_PRIORITY, LIVE_RUN, _SCHEMA, _choose, utc_timestamp
from roll.v3.overview import BENCHMARK_SYMBOL, market_trade_dates
from roll.v3.storage import database, ensure_schema, instant


INDUSTRY_SERIES = "industry_index"
TREND_SESSIONS = 20
MIN_CALENDAR_DAY = date(min(SSE_HISTORICAL_HOLIDAYS), 1, 1)


def _active_industries(db, day, cutoff):
    versions = db.execute(
        """SELECT * FROM observation
           WHERE series = ? AND trade_date <= ? AND item_id = ''
           ORDER BY symbol, trade_date, source, seq""",
        (INDUSTRY_SERIES, day),
    )
    policy = {"use_mode": LIVE_RUN, "source_priority": ("shenwan",)}
    latest = {}
    for (symbol, _), candidates in groupby(versions, lambda row: (row["symbol"], row["trade_date"])):
        chosen, status = _choose(list(candidates), policy, cutoff)
        if status != "not_visible":
            latest[symbol] = chosen

    for item in latest.values():
        if item is None or not item["source_ref"]:
            continue
        identity = item["payload"]
        end = identity.get("effective_end")
        if (identity.get("level") == 1 and identity.get("name") and identity.get("classification")
                and identity.get("classification_ref") and identity.get("effective_start") == item["trade_date"]
                and (end is None or day <= end)):
            yield item


def _recent_sessions(day, extension):
    sessions = []
    while day >= MIN_CALENDAR_DAY and len(sessions) <= TREND_SESSIONS:
        if is_session(day, extension):
            sessions.append(day.isoformat())
        day -= timedelta(days=1)
    return sessions[::-1]


def _decimal(value, *, positive=False):
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    if not number.is_finite() or number < 0 or (positive and number == 0):
        return None
    return number


def _source(row):
    return {key: row[key] for key in ("seq", "source", "source_ref", "received_at", "available_evidence")}


def _visible_bars(db, symbols, sessions, cutoff):
    placeholders = ",".join("?" for _ in symbols)
    versions = db.execute(
        f"""SELECT * FROM observation WHERE series = 'daily_bar' AND item_id = ''
            AND symbol IN ({placeholders}) AND trade_date BETWEEN ? AND ?
            ORDER BY symbol, trade_date, source, seq""",
        (*symbols, sessions[0], sessions[-1]),
    )
    bars = defaultdict(dict)
    for (symbol, day), candidates in groupby(versions, lambda row: (row["symbol"], row["trade_date"])):
        priority = DEFAULT_SOURCE_PRIORITY if symbol == BENCHMARK_SYMBOL else ("shenwan", *DEFAULT_SOURCE_PRIORITY)
        policy = {"use_mode": LIVE_RUN, "source_priority": priority}
        chosen, _ = _choose(list(candidates), policy, cutoff)
        if chosen is not None:
            bars[symbol][day] = chosen
    return bars


def _close(row):
    if row and row["payload"].get("trading_status") != "suspended":
        return _decimal(row["payload"].get("close"), positive=True)
    return None


def _price_unit(unit):
    return unit.get("price") if isinstance(unit, dict) else unit


def _bar(row, prior, prior_day):
    if row is None:
        return None
    payload = row["payload"]
    close = _close(row)
    prior_close = _close(prior) if prior and _price_unit(prior["unit"]) == _price_unit(row["unit"]) else None
    # Fuyao's index adapter derives pre_close by an exact previous-session lookup.
    if prior_day and (payload.get("pre_close_trade_date") == prior_day
                      or (row["source"] == "fuyao" and payload.get("pre_close_basis")
                          in {"prior_raw_close", "prior_close_no_adjustment_factor"})):
        prior_close = _decimal(payload.get("pre_close"), positive=True) or prior_close
    change = (close - prior_close) / prior_close * 100 if close is not None and prior_close is not None else None
    amounts = {key: _decimal(payload.get(key)) for key in ("volume", "amount")}
    prices = {key: _decimal(payload.get(key), positive=True) for key in ("open", "high", "low")}
    readings = {**prices, **amounts, "close": close, "previous_close": prior_close}
    return {
        "trade_date": row["trade_date"], **_source(row), "unit": row["unit"],
        **{key: format(value, "f") if value is not None else None for key, value in readings.items()},
        "previous_trade_date": prior_day if prior_close is not None else None,
        "change_pct": change,
    }


def _daily_bars(sessions, observations, start=None):
    bars = {}
    for prior_day, day in list(zip([None, *sessions], sessions))[-TREND_SESSIONS:]:
        if start and prior_day and prior_day < start:
            prior_day = None
        bars[day] = _bar(observations.get(day), observations.get(prior_day), prior_day)
    return bars


def _comparison(day, industry, benchmark):
    relative = None
    if industry and benchmark and industry["change_pct"] is not None and benchmark["change_pct"] is not None:
        relative = industry["change_pct"] - benchmark["change_pct"]
    return {"trade_date": day, "industry": industry, "benchmark": benchmark,
            "relative_percentage_points": relative}


def _industry_row(identity, sessions, observations, benchmark):
    details = identity["payload"]
    start = details["effective_start"]
    quotes = {day: row for day, row in observations.items() if day >= start}
    bars = _daily_bars(sessions, quotes, start)
    comparisons = [_comparison(day, bar, benchmark[day]) for day, bar in bars.items() if day >= start]
    first = next((i for i, point in enumerate(comparisons) if point["industry"] or point["benchmark"]),
                 len(comparisons) - 1)
    selected = comparisons[-1]
    return {
        "symbol": identity["symbol"], "name": details["name"], "level": details["level"],
        "identity": {**details, **_source(identity)}, "bar": selected["industry"],
        "relative_percentage_points": selected["relative_percentage_points"], "trend": comparisons[first:],
    }


def _group(classification, rows):
    sizes = {row["identity"].get("classification_size") for row in rows}
    expected = sizes.pop() if len(sizes) == 1 else None
    valid_days = [{point["trade_date"] for point in row["trend"] if point["relative_percentage_points"] is not None}
                  for row in rows]
    return {
        "classification": classification, "rows": rows,
        "coverage": {
            "classified": len(rows), "expected": expected,
            "priced": sum(bool(row["bar"] and row["bar"]["close"] is not None) for row in rows),
            "comparable": sum(row["relative_percentage_points"] is not None for row in rows),
        },
        "last_comparable_trade_date": max(set.intersection(*valid_days), default=None),
    }


def build_industry_report(data_dir, *, trade_date=None, as_of=None):
    """Read exact-session industry and benchmark bars from one local SQLite view."""
    clock = instant(as_of)
    cutoff = utc_timestamp(clock)
    day = trade_date or market_trade_dates(data_dir, as_of=clock)["latest_trade_date"]
    result = {"trade_date": day, "benchmark": {"symbol": BENCHMARK_SYMBOL, "name": "沪深 300", "bar": None}, "groups": []}
    if day is None:
        return result
    with database(data_dir) as db:
        ensure_schema(db, _SCHEMA)
        db.execute("BEGIN")
        selected = date.fromisoformat(day)
        extension = extended_sessions(db)
        last_closed, _ = latest_session(db, clock.date() - timedelta(days=clock.time() < time(15)))
        if selected > last_closed or not is_session(selected, extension):
            raise ValueError("请选择已收盘的交易日")
        identities = list(_active_industries(db, day, cutoff))
        sessions = _recent_sessions(selected, extension)
        symbols = [BENCHMARK_SYMBOL, *(item["symbol"] for item in identities)]
        observations = _visible_bars(db, symbols, sessions, cutoff)
    benchmark = _daily_bars(sessions, observations[BENCHMARK_SYMBOL])
    result["benchmark"]["bar"] = benchmark[day]
    grouped = defaultdict(list)
    for identity in identities:
        grouped[identity["payload"]["classification"]].append(
            _industry_row(identity, sessions, observations[identity["symbol"]], benchmark),
        )
    result["groups"] = [_group(classification, rows) for classification, rows in sorted(grouped.items())]
    return result
