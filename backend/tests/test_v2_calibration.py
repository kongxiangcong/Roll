from datetime import date, timedelta

from roll.calibration import replay_predictions, summarize
from roll.market.calendar import is_session


def test_cold_start_matures_on_twentieth_session_and_counts_only_scored_predictions():
    days = []
    cursor = date(2025, 1, 2)
    while len(days) < 41:
        if is_session(cursor):
            days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    signals = [{"trade_date": day, "regime": "防守" if i in (0, 20) else None}
               for i, day in enumerate(days)]
    close = {day: "100" for day in days}
    close[days[20]] = "101"
    early = replay_predictions(signals[:20], close)
    assert early[0]["probability"] is None and early[0]["outcome"] is None
    first, second = replay_predictions(signals[:21], close)
    assert (first["maturity_date"], first["outcome"]) == (days[20], 1)
    assert second["mature_sample_count"] == 1 and second["probability"] == 1
    assert summarize([first, second])["防守"]["brier_count"] == 0
    final = replay_predictions(signals, close)
    assert final[1]["outcome"] == 0 and final[1]["maturity_date"] == days[40]
    assert summarize(final)["防守"] == {"predictions": 2, "mature_count": 2, "up_count": 1,
                                       "up_frequency": .5, "brier_count": 1, "brier": 1}
    del close[days[20]]
    incomplete = replay_predictions(signals, close)
    assert all(r["outcome"] is None and r["probability"] is None for r in incomplete)


def test_calibration_archive_retains_probability_after_source_revisions(tmp_path, monkeypatch):
    from roll.barometer import score_features
    from roll.calibration import historical_calibration
    from roll.db import connect
    from roll.market.daily import initialize_market

    sessions = []
    cursor = date(2020, 1, 2)
    while len(sessions) < 41:
        if is_session(cursor):
            sessions.append(cursor.isoformat())
        cursor += timedelta(days=1)
    def scores(db, start, end):
        return [{**score_features({}), "trade_date": day, "regime": "防守" if i in (0, 20) else None}
                for i, day in enumerate(sessions) if start <= day <= end]
    monkeypatch.setattr("roll.calibration.scores_in_transaction", scores)
    with connect(tmp_path / "roll.sqlite3") as db:
        initialize_market(db)
        for i in (0, 20, 40):
            close = str(101 if i == 20 else 100)
            db.execute("INSERT INTO daily_bars VALUES ('000300.SH',?,?,?,?,?)",
                       (sessions[i], close, close, close, close))
    first = historical_calibration(tmp_path, sessions[0], sessions[20])
    assert first["current"]["probability"] == 1
    assert first["by_regime"]["防守"]["brier_count"] == 0
    with connect(tmp_path / "roll.sqlite3") as db:
        db.execute("UPDATE daily_bars SET close_raw='200' WHERE symbol='000300.SH' AND trade_date=?", (sessions[0],))
    after = historical_calibration(tmp_path, sessions[20], sessions[40])
    assert after["forecasts"][0]["probability"] == 1
    assert after["by_regime"]["防守"]["brier_count"] == 1
    assert after["by_regime"]["防守"]["predictions"] == 1
    earlier = historical_calibration(tmp_path, sessions[0], sessions[0])
    assert earlier["forecasts"][0]["probability"] is None and earlier["forecasts"][0]["outcome"] is None


def test_four_regimes_have_separate_mse_denominators():
    forecasts = [
        {"regime": "防守", "probability": None, "outcome": 1},
        {"regime": "谨慎", "probability": .75, "outcome": 1},
        {"regime": "谨慎", "probability": .25, "outcome": 1},
        {"regime": "均衡", "probability": 1, "outcome": None},
        {"regime": "进攻", "probability": .5, "outcome": 0},
    ]
    rows = summarize(forecasts)
    assert [(r["mature_count"], r["brier_count"], r["brier"]) for r in rows.values()] == [
        (1, 0, None), (2, 2, .3125), (0, 0, None), (1, 1, .25)]
