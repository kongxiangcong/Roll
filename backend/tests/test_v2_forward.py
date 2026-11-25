"""Forward statistics count only an explicit same-session daily freeze."""
from datetime import date, datetime, timedelta
import json

from roll.calibration import forward_statistics, historical_calibration
from roll.db import connect
from roll.market.calendar import is_session
from roll.market.daily import SHANGHAI, initialize_market
from roll.market.inputs import BROAD_ETFS, initialize_inputs
from roll.reports import freeze_report, read_report


def test_only_first_same_day_freeze_registers_and_twentieth_close_matures(tmp_path, monkeypatch):
    day = date(2025, 7, 1)
    clock = datetime.combine(day, datetime.min.time(), SHANGHAI).replace(hour=16)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.astimezone(tz)

    monkeypatch.setattr("roll.reports.datetime", Clock)
    monkeypatch.setattr("roll.calibration.datetime", Clock)
    sessions = []
    cursor = date(2024, 1, 1)
    while cursor <= day or len([d for d in sessions if d > day.isoformat()]) < 20:
        if is_session(cursor):
            sessions.append(cursor.isoformat())
        cursor += timedelta(days=1)
    t = sessions.index(day.isoformat())
    previous, trade, maturity = sessions[t-1], sessions[t], sessions[t+20]
    with connect(tmp_path / "roll.sqlite3") as db:
        initialize_market(db)
        initialize_inputs(db)
        db.execute("BEGIN")
        db.executemany("INSERT INTO daily_bars VALUES ('000300.SH',?,'100','101','100',?)",
                       [(d, "101" if d == maturity else "100") for d in sessions])
        for series, symbol, value in [
            ("turnover", "CN", {"turnover_yuan": 100}), ("margin", "CN", {"balance_yuan": 100}),
            *(("etf_shares", f, {"shares": "200"}) for f in BROAD_ETFS),
            *(("etf_nav", f, {"nav": "2"}) for f in BROAD_ETFS),
        ]:
            db.executemany("INSERT INTO market_inputs VALUES(?,?,?,?)",
                           [(series, symbol, d, json.dumps(value)) for d in sessions])
        db.commit()

    history = historical_calibration(tmp_path, previous, trade)
    assert history["current"]["probability"] == 0  # An eligible zero forecast remains a prediction.
    assert forward_statistics(tmp_path, previous, trade)["registered_count"] == 0
    retroactive = freeze_report(tmp_path, previous)
    assert retroactive["calibration"]["probability"] == 0
    assert retroactive["forward"]["registered_count"] == 0
    frozen = freeze_report(tmp_path, trade)
    assert frozen["forward"]["registered_count"] == 1
    assert read_report(tmp_path, trade) == freeze_report(tmp_path, trade) == frozen
    clock = datetime.fromisoformat(maturity).replace(hour=14, minute=59, tzinfo=SHANGHAI)
    before = forward_statistics(tmp_path, trade, maturity)
    assert (before["trading_days"], before["registered_count"], before["mature_count"]) == (20, 1, 0)
    clock = clock.replace(hour=15, minute=0)
    result = forward_statistics(tmp_path, trade, maturity)
    assert (result["trading_days"], result["registered_count"], result["mature_count"]) == (21, 1, 1)
    assert result["brier"] == 1 and result["predictions"][0]["maturity_date"] == maturity
    assert read_report(tmp_path, trade)["forward"]["mature_count"] == 0
    assert forward_statistics(tmp_path, trade, trade)["mature_count"] == 0
