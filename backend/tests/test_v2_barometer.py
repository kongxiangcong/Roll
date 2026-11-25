import pytest

from roll.barometer import score_features, regime_for_score


FEATURES = {
    "close_ma20": 0, "close_ma60": 0, "close_ma120": 0, "ma20_ma60": 0, "ma60_ma120": 0,
    "volatility_rank": .50, "turnover_confirmation": 0,
    "flow_z5": .5, "flow_z20": .5, "margin10": 0, "margin5": 0,
    "breadth5": .55, "pe_rank": .775, "pb_rank": .775,
}


@pytest.mark.parametrize("excluded, coverage, score", [
    ([], 1, 56.875), (["margin5"], .70, 38.125 / .70),
    (["breadth5", "pb_rank"], .65, 36.25 / .65),
    (["margin5", "breadth5", "pb_rank"], .35, None),
    (["close_ma20", "margin5", "breadth5", "pb_rank"], 0, None),
])
def test_frozen_scoring_table(excluded, coverage, score):
    features = {k: v for k, v in FEATURES.items() if k not in excluded}
    result = score_features(features)
    assert result["coverage"] == coverage
    if score is None:
        assert result["score"] is result["regime"] is result["position_cap"] is None
    else:
        assert result["score"] == pytest.approx(score)
        assert (result["regime"], result["position_cap"]) == ("均衡", .60)
    if not excluded:
        assert result["dimensions"] == pytest.approx({"trend": 50, "funding": 62.5, "breadth": 75, "valuation": 37.5})


def test_regime_boundaries():
    assert [regime_for_score(x) for x in [0, 25, 50, 75, 100]] == [
        ("防守", .15), ("谨慎", .35), ("均衡", .60), ("进攻", .80), ("进攻", .80)]


def test_workbench_recomputes_but_frozen_report_keeps_same_score_after_backfill(tmp_path):
    import json
    from datetime import date, timedelta
    from roll.db import connect
    from roll.market.calendar import is_session
    from roll.market.daily import initialize_market
    from roll.market.inputs import BROAD_ETFS, input_status
    from roll.barometer import barometer_at, barometer_history
    from roll.reports import freeze_report, read_report, report_markdown

    day = date(2025, 8, 1)
    days = []
    cursor = day
    while len(days) < 1260:
        if is_session(cursor):
            days.append(cursor.isoformat())
        cursor -= timedelta(days=1)
    days.reverse()
    input_status(tmp_path)
    with connect(tmp_path / "roll.sqlite3") as db:
        initialize_market(db)
        db.execute("BEGIN")
        db.executemany("INSERT INTO daily_bars VALUES ('000300.SH', ?, '100','100','100','100')",
                       [(d,) for d in days])
        def put(series, symbol, records):
            db.executemany("INSERT OR REPLACE INTO market_inputs VALUES(?,?,?,?)",
                           [(series, symbol, d, json.dumps(values)) for d, values in records])
        put("turnover", "CN", [(d, {"turnover_yuan": "100"}) for d in days[-20:]])
        put("valuation", "000300.SH", [(d, {"pe_ttm": "10", "pb": "2"}) for d in days])
        put("breadth", "CN", [(d, {"advancing": u, "declining": v}) for d, (u, v) in
                             zip(days[-5:], [(1, 1), (60, 40), (55, 45), (55, 45), (55, 45)])])
        put("margin", "CN", [(d, {"balance_yuan": "100"}) for d in days[-11:-1]])
        for symbol in BROAD_ETFS:
            put("etf_shares", symbol, [(d, {"shares": "1000"}) for d in days[-270:]])
            put("etf_nav", symbol, [(d, {"nav": "2"}) for d in days[-269:]])
        db.commit()
    latest = days[-1]
    partial = barometer_at(tmp_path, latest)
    assert partial["coverage"] == .70 and partial["score"] == pytest.approx(40 / .70)
    assert partial["dimensions"] == {"trend": 50, "funding": None, "breadth": 75, "valuation": 50}
    frozen = freeze_report(tmp_path, latest)
    assert frozen["barometer"] == partial
    with connect(tmp_path / "roll.sqlite3") as db:
        db.execute("INSERT INTO market_inputs VALUES ('margin','CN',?,?)", (latest, '{"balance_yuan":"100"}'))
    now = barometer_at(tmp_path, latest)
    assert (now["score"], now["coverage"]) == (55, 1)
    with connect(tmp_path / "roll.sqlite3") as db:
        db.execute("CREATE TABLE IF NOT EXISTS watchlist_config(id INTEGER PRIMARY KEY, items TEXT NOT NULL)")
        db.execute("INSERT OR REPLACE INTO watchlist_config VALUES (1,?)", (json.dumps([{"code": "600150.SH"}]),))
    assert barometer_at(tmp_path, latest) == now
    assert barometer_history(tmp_path, days[-2], latest)[-1] == now
    assert read_report(tmp_path, latest) == freeze_report(tmp_path, latest) == frozen
    assert "70%" in report_markdown(frozen)
    with connect(tmp_path / "roll.sqlite3") as db:
        db.execute("DELETE FROM market_inputs WHERE series='margin' AND trade_date=?", (days[-3],))
    assert barometer_at(tmp_path, latest) == partial
