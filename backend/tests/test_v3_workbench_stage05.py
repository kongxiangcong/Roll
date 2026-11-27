"""Stage 05 acceptance tests: watchlist persistence, overview aggregation, non-blocking sync and UI hygiene."""
import io
import json
import sys
import time

from fastapi.testclient import TestClient

from roll.v3.cli import run
from roll.v3.web import create_app


DECISION = "2026-11-27T16:00:00+08:00"
SYMBOL = "600362.SH"


def test_watchlist_crud_and_overview_graceful_empty(tmp_path):
    with TestClient(create_app(tmp_path)) as browser:
        wl = browser.get("/api/watchlist")
        assert wl.status_code == 200
        assert [item["symbol"] for item in wl.json()] == [SYMBOL]

        added = browser.post("/api/watchlist", json={"symbol": "600150.SH"})
        assert added.status_code == 200
        assert added.json()["name"] == "中国船舶"

        reordered = browser.put("/api/watchlist/order", json={"symbols": ["600150.SH", SYMBOL]})
        assert [item["symbol"] for item in reordered.json()] == ["600150.SH", SYMBOL]

        ov = browser.get("/api/overview")
        assert ov.status_code == 200, ov.text
        data = ov.json()
        assert data["account_summary"]["initialized"] is False
        assert data["market_env"]["sentiment"] is None
        assert data["market_env"]["broad_etf_flow"] is None
        assert len(data["watchlist"]) == 2
        assert data["watchlist"][0]["probability"] is None

        deleted = browser.delete("/api/watchlist/600150.SH")
        assert deleted.status_code == 200
        assert [item["symbol"] for item in browser.get("/api/watchlist").json()] == [SYMBOL]


def test_overview_populates_metrics_account_and_sync_without_harness(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "cash": "50000", "available_cash": "50000", "effective_at": DECISION, "known_at": DECISION,
        "lots": [{"lot_id": "init-1", "symbol": SYMBOL, "quantity": 1000, "cost": "20000", "known_sellable": 1000}],
    })))
    run(("account", "init"), data_dir=tmp_path)
    bars = []
    from roll.v3.storage import sessions
    days = list(sessions("2026-08-01", "2026-11-27"))
    for idx, day in enumerate(days):
        close = round(20.0 + idx * 0.05, 2)
        prior = round(20.0 + max(0, idx - 1) * 0.05, 2)
        bars.append({
            "series": "daily_bar", "symbol": SYMBOL, "trade_date": day, "source": "fixture",
            "available_at": f"{day}T15:05:00+08:00", "received_at": f"{day}T15:05:00+08:00",
            "payload": {"close": str(close), "prior_close": str(prior), "pre_close": str(prior), "trading_status": "trading"},
        })
        bench = round(3800.0 + idx * 2.0, 2)
        bench_prior = round(3800.0 + max(0, idx - 1) * 2.0, 2)
        bars.append({
            "series": "daily_bar", "symbol": "000300.SH", "trade_date": day, "source": "fixture",
            "available_at": f"{day}T15:05:00+08:00", "received_at": f"{day}T15:05:00+08:00",
            "payload": {"close": str(bench), "prior_close": str(bench_prior), "pre_close": str(bench_prior), "trading_status": "trading"},
        })
    bars_file = tmp_path / "bars.json"
    bars_file.write_text(json.dumps(bars), encoding="utf-8")
    run(("market", "import", str(bars_file)), data_dir=tmp_path)

    sync_calls = []
    harness_calls = []

    def fake_sync(data_dir, *, symbols, start, refresh):
        sync_calls.append(tuple(symbols))
        return {"appended": 2, "failures": [], "fallbacks": [], "coverage": []}

    def forbidden_harness(_manifest):
        harness_calls.append(1)
        raise AssertionError("日常同步不得触发研究助手")

    with TestClient(create_app(tmp_path, research_executor=forbidden_harness, market_sync_fn=fake_sync)) as browser:
        ov = browser.get("/api/overview", params={"as_of": DECISION}).json()
        assert ov["trade_date"] == "2026-11-27"
        assert ov["market_env"]["benchmark"]["close"] is not None
        assert ov["market_env"]["benchmark"]["trend_state"] == "uptrend"
        acct = ov["account_summary"]
        assert acct["initialized"] is True
        assert acct["total_nav"] > 50000
        assert acct["position_ratio"] > 0
        row = ov["watchlist"][0]
        assert row["symbol"] == SYMBOL
        assert row["metrics"]["return_5d"] is not None
        assert row["metrics"]["return_20d"] is not None
        assert row["metrics"]["rel_benchmark_20d"] is not None

        triggered = browser.post("/api/market/sync", json={})
        assert triggered.status_code == 200
        for _ in range(40):
            st = browser.get("/api/market/sync/status").json()
            if st["status"] in ("done", "error"):
                break
            time.sleep(0.05)
        assert st["status"] == "done"
        assert st["appended"] == 2
        assert len(sync_calls) == 1
        assert len(harness_calls) == 0


def test_rebuilt_ui_contains_no_audit_evidence_or_warm_paper_legacy(tmp_path):
    with TestClient(create_app(tmp_path)) as browser:
        html = browser.get("/").text
        css = browser.get("/assets/workbench.css").text
        js = browser.get("/assets/workbench.js").text
        assert "盘后工作台" in html
        # No warm paper / serif legacy styling
        assert "#f7f6f0" not in css
        assert "#242e27" not in css
        # No raw JSON dumps, evidence lists, or audit receipt labels in UI assets
        for forbidden in ("完整计划记录", "完整复盘记录", "账户快照完整记录", "档案 Markdown 原文", "公开证据", "证据引用"):
            assert forbidden not in js, f"UI 不应包含审计/证据文案：{forbidden}"
