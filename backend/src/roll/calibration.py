"""Four-regime frequencies reconstructed from index closes and previously matured labels."""
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from decimal import Decimal, InvalidOperation

from roll.barometer import scores_in_transaction
from roll.db import connect
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


def replay_predictions(sessions, closes, archived=None, labels=None):
    """Consume the complete ordered exchange calendar, including sessions without a signal/close."""
    archived, labels = archived or {}, labels or {}
    counts, ups, forecasts = Counter(), Counter(), {}
    for i, session in enumerate(sessions):
        day = session["trade_date"]
        if i >= HORIZON:
            origin = sessions[i - HORIZON]["trade_date"]
            prior = forecasts.get(origin)
            if prior:
                outcome = labels.get(origin)
                if outcome is None:
                    outcome = index_label(closes.get(origin), closes.get(day))
                if outcome is not None:
                    prior.update(maturity_date=day, outcome=outcome)
                    counts[prior["regime"]] += 1
                    ups[prior["regime"]] += outcome
        if day in archived:
            forecast = dict(archived[day])
        elif (regime := session["regime"]) is not None:
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


def initialize_calibration(db):
    db.execute("""CREATE TABLE IF NOT EXISTS replay_forecasts (
        trade_date TEXT PRIMARY KEY, regime TEXT NOT NULL,
        mature_sample_count INTEGER NOT NULL, probability REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS replay_labels (
        trade_date TEXT PRIMARY KEY REFERENCES replay_forecasts(trade_date),
        maturity_date TEXT NOT NULL, outcome INTEGER NOT NULL CHECK (outcome IN (0,1)))""")


def _last_completed_day():
    now = datetime.now(SHANGHAI)
    return (now.date() if now.time() >= time(15) else now.date() - timedelta(days=1)).isoformat()


def calibration_in_transaction(db, start, end):
    """Archive reconstructed forecasts and append labels in the caller's transaction."""
    replay_start = "2020-01-01"
    sessions = scores_in_transaction(db, replay_start, end) if end >= replay_start else []
    archived = {r["trade_date"]: dict(r) for r in db.execute(
        "SELECT * FROM replay_forecasts WHERE trade_date<=? ORDER BY trade_date", (end,))}
    labels = dict(db.execute("SELECT trade_date,outcome FROM replay_labels WHERE maturity_date<=?", (end,)))
    closes = dict(db.execute("SELECT trade_date,close_raw FROM daily_bars WHERE symbol='000300.SH' "
                             "AND trade_date BETWEEN ? AND ?", (replay_start, end)))
    forecasts = replay_predictions(sessions, closes, archived, labels)
    db.executemany("INSERT INTO replay_forecasts VALUES (:trade_date,:regime,:mature_sample_count,:probability)",
                   (r for r in forecasts if r["trade_date"] not in archived))
    db.executemany("INSERT INTO replay_labels VALUES (:trade_date,:maturity_date,:outcome)",
                   (r for r in forecasts if r["outcome"] is not None and r["trade_date"] not in labels))
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
        initialize_calibration(db)
        db.execute("BEGIN IMMEDIATE")
        result = calibration_in_transaction(db, start, end)
        db.commit()
        return result
