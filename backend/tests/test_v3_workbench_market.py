"""Exercise the market workbench against a watchlist and account from the existing app."""
import io
import json
import sys

from fastapi.testclient import TestClient

from roll.v3.cli import run
from roll.v3.web import create_app


CLOCK = "2026-11-26T18:00:00+08:00"
COPPER = "600362.SH"
SHIP = "600150.SH"
BANK = "601398.SH"


def test_observation_pool_keeps_watchlist_and_account_at_current_time_but_uses_selected_market_day(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "cash": "3000", "available_cash": "3000", "effective_at": CLOCK, "known_at": CLOCK,
        "lots": [
            {"lot_id": "ship", "symbol": SHIP, "quantity": 100, "cost": "1000"},
            {"lot_id": "bank", "symbol": BANK, "quantity": 100, "cost": "500"},
        ],
    })))
    run(("account", "init"), data_dir=tmp_path)
    bars = tmp_path / "bars.json"
    bars.write_text(json.dumps([
        {
            "series": "daily_bar", "symbol": symbol, "trade_date": day, "source": "fixture",
            "available_at": f"{day}T15:05:00+08:00", "received_at": f"{day}T15:05:00+08:00",
            "payload": {"close": close, "prior_close": "10", "trading_status": "trading"},
        }
        for symbol, day, close in (
            (SHIP, "2026-11-24", "11"), (SHIP, "2026-11-26", "18"), (COPPER, "2026-11-25", "40"),
        )
    ]))
    run(("market", "import", str(bars)), data_dir=tmp_path)
    with TestClient(create_app(tmp_path)) as browser:
        browser.get("/api/watchlist")
        browser.post("/api/watchlist", json={"symbol": SHIP, "name": "自定义中国船舶"}).raise_for_status()
        browser.put("/api/watchlist/order", json={"symbols": [SHIP, COPPER]}).raise_for_status()

    with TestClient(create_app(tmp_path)) as browser:
        params = {"trade_date": "2026-11-24", "as_of": CLOCK}
        response = browser.get("/api/market/watchlist", params=params)
        assert response.status_code == 200, response.text
        pool = response.json()
        assert pool["trade_date"] == "2026-11-24"
        assert pool["account_as_of"].startswith("2026-11-26T10:00:00")
        assert pool["watchlist_as_of"]
        assert [(row["symbol"], row["in_watchlist"], row["holding_shares"], row["close"]) for row in pool["rows"]] == [
            (SHIP, True, 100, 11), (COPPER, True, 0, None), (BANK, False, 100, None),
        ]
        assert pool["rows"][0]["name"] == "自定义中国船舶"
        assert pool["rows"][0]["trade_date"] == "2026-11-24"

        rehearsal = browser.get("/api/market/watchlist", params={**params, "book_id": "m0a-example"}).json()
        assert [row["symbol"] for row in rehearsal["rows"]] == [SHIP, COPPER]
        assert all(row["holding_shares"] == 0 for row in rehearsal["rows"])


def test_watchlist_reordering_and_removal_survive_reopening(tmp_path):
    with TestClient(create_app(tmp_path)) as browser:
        assert [row["symbol"] for row in browser.get("/api/watchlist").json()] == [COPPER]
        browser.post("/api/watchlist", json={"symbol": SHIP, "name": "船舶自选"}).raise_for_status()
        browser.post("/api/watchlist", json={"symbol": BANK}).raise_for_status()
        order = browser.put("/api/watchlist/order", json={"symbols": [BANK, SHIP, BANK]})
        assert order.status_code == 200, order.text
        assert [row["symbol"] for row in order.json()] == [BANK, SHIP, COPPER]

    with TestClient(create_app(tmp_path)) as browser:
        saved = browser.get("/api/watchlist").json()
        assert [(row["symbol"], row["name"]) for row in saved[1:]] == [(SHIP, "船舶自选"), (COPPER, "江西铜业")]
        for symbol in (BANK, SHIP, COPPER):
            browser.delete(f"/api/watchlist/{symbol}").raise_for_status()

    with TestClient(create_app(tmp_path)) as browser:
        assert browser.get("/api/watchlist").json() == []
        assert browser.get("/api/market/watchlist").json()["rows"] == []
