from roll.config import active_watchlist
from roll.market.daily import sync_market
import httpx


def test_edit_takes_effect_only_at_next_sync(tmp_path, monkeypatch):
    monkeypatch.setenv("FUYAO_API_KEY", "test")
    config = tmp_path / "watchlist.yaml"
    config.write_text("""
watchlist:
  - code: 600362.SH
    name: 江西铜业
    sector_etf: 512400.SH
    max_position_pct: 0.25
    atr_stop_multiplier: 2.2
""", encoding="utf-8")
    requests = []
    def provider(request):
        requests.append(request.url.params["thscode"])
        return httpx.Response(503)
    with httpx.Client(transport=httpx.MockTransport(provider)) as client:
        sync_market(tmp_path, "2025-01-01", "2025-01-02", client=client, watchlist=config)
        old = active_watchlist(tmp_path)
        assert old[0]["code"] == "600362.SH" and float(old[0]["max_position_pct"]) == 0.25
        config.write_text(config.read_text(encoding="utf-8").replace("600362.SH", "600150.SH")
                          .replace("江西铜业", "中国船舶").replace("0.25", "0.20"), encoding="utf-8")
        assert active_watchlist(tmp_path) == old
        requests.clear()
        status = sync_market(tmp_path, "2025-01-01", "2025-01-02", client=client, watchlist=config)
        assert set(requests) == {"000300.SH", "600150.SH"}
        assert {r["symbol"] for r in status} == set(requests)
        updated = active_watchlist(tmp_path)
        assert len(updated) == 1 and updated[0]["code"] == "600150.SH"
        assert float(updated[0]["max_position_pct"]) == 0.20


def test_indicators_warm_up_before_displayed_range(tmp_path):
    from decimal import Decimal
    from datetime import date, timedelta
    from roll.db import connect
    from roll.market.daily import read_indicators, market_status
    market_status(tmp_path)
    first = date(2025, 1, 1)
    with connect(tmp_path / "roll.sqlite3") as db:
        for i in range(22):
            price = 100 + i if i < 20 else 99 + i
            db.execute("INSERT INTO daily_bars VALUES (?,?,?,?,?,?)",
                       ("600362.SH", (first+timedelta(days=i)).isoformat(), str(price),
                        str(price+1), str(price-1), str(price)))
        db.execute("INSERT INTO adjustment_factors VALUES (?,?,?,?)", ("600362.SH","2025-01-21","1","-1"))
    rows = read_indicators(tmp_path,"600362.SH","2025-01-21","2025-01-22","forward")
    assert Decimal(rows[0]["ma20"]) == Decimal("109.5") and Decimal(rows[0]["atr14"]) == 2
    assert rows[0]["ma60"] is None and Decimal(rows[-1]["ma20"]) == Decimal("110.5")


def test_index_keeps_new_year_when_old_window_fails_and_retries_gap(tmp_path, monkeypatch):
    from roll.market.daily import _millis
    monkeypatch.setenv("FUYAO_API_KEY", "test")
    config = tmp_path / "empty.yaml"
    config.write_text("watchlist: []", encoding="utf-8")
    allowed = False
    requested = []
    def provider(request):
        start = int(request.url.params["start"])
        requested.append(start)
        if start == _millis("2023-01-01") and not allowed:
            return httpx.Response(200, json={"code": 1003})
        from datetime import datetime,timedelta
        from roll.market.calendar import is_session
        from roll.market.daily import SHANGHAI
        cursor = datetime.fromtimestamp(start / 1000, SHANGHAI).date()
        last = datetime.fromtimestamp(int(request.url.params["end"]) / 1000, SHANGHAI).date()
        rows = []
        while cursor <= last:
            if is_session(cursor) and (allowed or str(cursor) != "2024-01-04"):
                rows.append({"date_ms": _millis(str(cursor)), **{k+"_price": 4100 for k in ("open","high","low","close")}})
            cursor += timedelta(days=1)
        return httpx.Response(200, json={"code":0,"data":{"thscode":"000300.SH","item":rows}})
    with httpx.Client(transport=httpx.MockTransport(provider)) as client:
        first, = sync_market(tmp_path, "2023-01-01", "2024-01-10", client=client, watchlist=config)
        assert first["last_date"] == "2024-01-10" and first["gaps"][0]["start"] == "2023-01-01"
        assert first["gaps"][1] == {"start":"2024-01-04","end":"2024-01-04","error":"指数缺交易日日线"}
        assert "1003" in first["gaps"][0]["error"]
        allowed = True
        requested.clear()
        updated, = sync_market(tmp_path, None, "2024-01-11", client=client, watchlist=config)
        assert _millis("2023-01-01") not in requested
        assert updated["last_date"] == "2024-01-11"
        assert len(updated["gaps"]) == 1 and updated["gaps"][0]["start"] == "2023-01-01"
        updated, = sync_market(tmp_path, updated["gaps"][0]["start"], updated["gaps"][0]["end"],
                               client=client, watchlist=config)
        assert _millis("2023-01-01") in requested
        assert updated["gaps"] == [] and updated["first_date"] == "2023-01-03"


def test_empty_index_window_keeps_actual_last_success(tmp_path, monkeypatch):
    from roll.market.daily import _millis

    monkeypatch.setenv("FUYAO_API_KEY", "test")
    config = tmp_path / "empty.yaml"
    config.write_text("watchlist: []", encoding="utf-8")
    rows = []

    def provider(request):
        return httpx.Response(200, json={"code": 0, "data": {"thscode": "000300.SH", "item": rows}})

    with httpx.Client(transport=httpx.MockTransport(provider)) as client:
        def sync(day):
            row, = sync_market(tmp_path, day, day, client=client, watchlist=config)
            return row

        first = sync("2025-07-21")
        assert first["last_success_at"] is None and first["count"] == 0 and first["gaps"]
        rows.append({"date_ms": _millis("2025-07-21"), **{k+"_price": 100 for k in ("open","high","low","close")}})
        successful = sync("2025-07-21")
        assert successful["last_success_at"] and successful["gaps"] == []
        rows.clear()
        assert sync("2025-07-26")["last_success_at"] == successful["last_success_at"]
        failed = sync("2025-07-22")
        assert failed["last_success_at"] == successful["last_success_at"] and failed["gaps"]
