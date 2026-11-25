"""Four-regime frequencies reconstructed from index closes and previously matured labels."""
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from decimal import Decimal, InvalidOperation

from roll.barometer import scores_in_transaction
from roll.db import connect
from roll.market.calendar import extended_sessions, is_session
from roll.market.daily import SHANGHAI, initialize_market
from roll.market.inputs import initialize_inputs
from roll.statistics import brier

REGIMES = ("防守", "谨慎", "均衡", "进攻")
HORIZON = 20


def index_label(start_close, end_close):
    try:
        start, end = Decimal(str(start_close)), Decimal(str(end_close))
    except InvalidOperation:
        return None
    if not start.is_finite() or not end.is_finite() or min(start, end) <= 0:
        return None
    return int(end > start)


def replay_predictions(sessions, closes):
    """Consume the complete ordered exchange calendar, including sessions without a signal/close."""
    counts, ups, forecasts = Counter(), Counter(), {}
    for i, session in enumerate(sessions):
        day = session["trade_date"]
        if i >= HORIZON:
            origin = sessions[i - HORIZON]["trade_date"]
            prior = forecasts.get(origin)
            if prior:
                outcome = index_label(closes.get(origin), closes.get(day))
                if outcome is not None:
                    prior.update(maturity_date=day, outcome=outcome)
                    counts[prior["regime"]] += 1
                    ups[prior["regime"]] += outcome
        if (regime := session["regime"]) is not None:
            count = counts[regime]
            forecast = {"trade_date": day, "regime": regime, "mature_sample_count": count,
                        "probability": ups[regime] / count if count else None}
        else:
            continue
        forecasts[day] = {**forecast, "maturity_date": None, "outcome": None}
    return list(forecasts.values())


def summarize(forecasts):
    result = {}
    for regime in REGIMES:
        group = [row for row in forecasts if row["regime"] == regime]
        mature = [r for r in group if r["outcome"] is not None]
        scored = [(r["probability"], r["outcome"]) for r in mature if r["probability"] is not None]
        up = sum(r["outcome"] for r in mature)
        result[regime] = {"predictions": len(group), "mature_count": len(mature), "up_count": up,
                          "up_frequency": up / len(mature) if mature else None,
                          "brier_count": len(scored), "brier": brier(scored)}
    return result


def _last_completed_day():
    now = datetime.now(SHANGHAI)
    return (now.date() if now.time() >= time(15) else now.date() - timedelta(days=1)).isoformat()


def calibration_in_transaction(db, start, end):
    """Replay against the caller's market-data snapshot without freezing any result."""
    replay_start = "2020-01-01"
    sessions = scores_in_transaction(db, replay_start, end) if end >= replay_start else []
    closes = dict(db.execute("SELECT trade_date,close_raw FROM daily_bars WHERE symbol='000300.SH' "
                             "AND trade_date BETWEEN ? AND ?", (replay_start, end)))
    forecasts = replay_predictions(sessions, closes)
    selected = [r for r in forecasts if r["trade_date"] >= start]
    latest = sessions[-1] if sessions else None
    regime = latest["regime"] if latest else None
    mature = [r["outcome"] for r in forecasts if r["regime"] == regime and r["outcome"] is not None]
    current = {"trade_date": latest["trade_date"] if latest else None, "regime": regime,
               "mature_sample_count": len(mature), "probability": sum(mature) / len(mature) if mature else None}
    return {"start": start, "end": end, "current": current, "by_regime": summarize(selected),
            "forecasts": selected}


def historical_calibration(data_dir: Path, start: str, end: str):
    start, end = date.fromisoformat(start).isoformat(), date.fromisoformat(end).isoformat()
    if start > end:
        raise ValueError("起始日期晚于截止日")
    end = min(end, _last_completed_day())
    with connect(data_dir / "roll.sqlite3") as db:
        initialize_market(db)
        initialize_inputs(db)
        db.execute("BEGIN")
        return calibration_in_transaction(db, start, end)


def initialize_forward(db):
    db.execute("""CREATE TABLE IF NOT EXISTS forward_forecasts (
        trade_date TEXT PRIMARY KEY REFERENCES frozen_reports(trade_date) DEFERRABLE INITIALLY DEFERRED,
        cutoff_at TEXT NOT NULL, regime TEXT NOT NULL, mature_sample_count INTEGER NOT NULL,
        probability REAL NOT NULL CHECK (probability BETWEEN 0 AND 1), index_close TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS forward_labels (
        trade_date TEXT PRIMARY KEY REFERENCES forward_forecasts(trade_date),
        maturity_date TEXT NOT NULL, outcome INTEGER NOT NULL CHECK (outcome IN (0,1)))""")


def register_frozen_forecast(db, report):
    day, cutoff = report["trade_date"], datetime.fromisoformat(report["cutoff_at"]).astimezone(SHANGHAI)
    prediction = report["calibration"]
    if (day != cutoff.date().isoformat() or cutoff.time() < time(15) or prediction["trade_date"] != day
            or prediction["regime"] is None or prediction["probability"] is None):
        return
    db.execute("""INSERT INTO forward_forecasts VALUES (?,?,?,?,?,(
        SELECT close_raw FROM daily_bars WHERE symbol='000300.SH' AND trade_date=?))""",
               (day, cutoff.isoformat(), prediction["regime"], prediction["mature_sample_count"],
                prediction["probability"], day))


def forward_in_transaction(db, start, end):
    """Evaluate predictions dated in the period using closes available through its end."""
    cursor, stop = date.fromisoformat(start), date.fromisoformat(end)
    sessions = []
    extension = extended_sessions(db)
    while cursor <= stop:
        if is_session(cursor, extension):
            sessions.append(cursor.isoformat())
        cursor += timedelta(days=1)
    positions = {day: index for index, day in enumerate(sessions)}
    predictions = [dict(r) for r in db.execute(
        "SELECT * FROM forward_forecasts WHERE trade_date BETWEEN ? AND ? ORDER BY trade_date", (start, end))]
    labels = {r["trade_date"]: dict(r) for r in db.execute(
        "SELECT * FROM forward_labels WHERE trade_date>=? AND maturity_date<=?", (start, end))}
    closes = dict(db.execute("SELECT trade_date,close_raw FROM daily_bars WHERE symbol='000300.SH' "
                             "AND trade_date BETWEEN ? AND ?", (start, end)))
    for row in predictions:
        day = row["trade_date"]
        target = positions[day] + HORIZON
        if day not in labels and target < len(sessions):
            maturity = sessions[target]
            outcome = index_label(row["index_close"] or closes.get(day), closes.get(maturity))
            if outcome is not None:
                db.execute("INSERT INTO forward_labels VALUES (?,?,?)", (day, maturity, outcome))
                labels[day] = {"maturity_date": maturity, "outcome": outcome}
        row.update(maturity_date=None, outcome=None)
        row.update(labels.get(day, {}))
    scored = [(r["probability"], r["outcome"]) for r in predictions if r["outcome"] is not None]
    return {"start": start, "end": end, "trading_days": len(sessions),
            "registered_count": len(predictions), "mature_count": len(scored), "brier_count": len(scored),
            "brier": brier(scored), "predictions": predictions}


def forward_statistics(data_dir: Path, start: str, end: str):
    start, end = date.fromisoformat(start).isoformat(), date.fromisoformat(end).isoformat()
    if start > end:
        raise ValueError("起始日期晚于截止日")
    end = min(end, _last_completed_day())
    with connect(data_dir / "roll.sqlite3") as db:
        initialize_market(db)
        initialize_forward(db)
        db.execute("BEGIN IMMEDIATE")
        result = forward_in_transaction(db, start, end)
        db.commit()
        return result
