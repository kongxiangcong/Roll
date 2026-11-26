from datetime import date, timedelta

import pytest

from roll.db import connect
from roll.market import sync
from roll.market.daily import _windows, initialize_market, sync_market


def test_backfill_is_explicit_bounded_and_skips_latest_only_breadth(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(sync, "sync_market", lambda *_a, **kw: calls.append(kw))
    monkeypatch.setattr(sync, "sync_inputs", lambda *_a, **kw: calls.append(kw))
    sync.sync_workbench(tmp_path, "2025-01-01", "2025-03-31", scope="backfill")
    assert calls[0] == {"index_only": True}
    assert calls[1]["missing_only"] is True
    assert set(calls[1]["groups"]) == {"etf_bars", "etf_shares", "etf_nav", "margin", "turnover"}
    for start, end, options in [
        (None, None, {}),
        ("2025-01-01", "2025-04-04", {}),
        ("2025-01-01", "2025-03-31", {"groups": ["breadth"]}),
    ]:
        with pytest.raises(ValueError):
            sync.sync_workbench(tmp_path, start, end, scope="backfill", **options)
    assert len(calls) == 2


def test_daily_sync_doesnt_replay_old_gaps_and_index_backfill_skips_covered_window(tmp_path):
    today = date(2025, 7, 21)
    with connect(tmp_path / "roll.sqlite3") as db:
        initialize_market(db)
        begin = (today - timedelta(days=180)).isoformat()
        assert list(_windows(db, "000300.SH", None, str(today))) == [(begin, str(today))]
        assert list(_windows(db, "000300.SH", "2020-01-01", "2020-09-01")) == [
            ("2020-01-01", "2020-09-01")]
        db.execute("INSERT INTO daily_gaps VALUES ('000300.SH', '2020-01-02', '2020-01-03', 'source gap')")
        db.execute("INSERT INTO daily_bars VALUES ('000300.SH', '2025-07-21', '1', '1', '1', '1')")
        assert list(_windows(db, "000300.SH", None, str(today))) == [
            ("2025-07-16", str(today))]
    sync_market(tmp_path, str(today), str(today), client=object(), index_only=True)
    with connect(tmp_path / "roll.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM daily_gaps").fetchone()[0] == 1
        assert db.execute("SELECT 1 FROM sqlite_master WHERE name='watchlist_config'").fetchone() is None
