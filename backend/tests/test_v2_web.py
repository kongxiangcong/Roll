import sqlite3
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
from roll.web import create_app


def test_market_page_can_load_without_an_account_and_cli_web_freeze_agree(tmp_path):
    client = TestClient(create_app(tmp_path))
    day = "2025-08-01"
    resp = client.get("/api/market", params={"day": day})
    assert resp.status_code == 200 and resp.json()["barometer"]["trade_date"] == day
    with sqlite3.connect(tmp_path / "roll.sqlite3") as db:
        assert (
            db.execute(
                "SELECT count(*) FROM sqlite_master WHERE name='account_events'"
            ).fetchone()[0]
            == 0
        )

    def cli_freeze():
        env = dict(
            os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src")
        )
        output = subprocess.check_output(
            [
                sys.executable,
                "-X",
                "utf8",
                "-m",
                "roll.cli",
                "--data-dir",
                str(tmp_path),
                "report",
                "freeze",
                day,
            ],
            env=env,
        )
        return json.loads(output)

    with ThreadPoolExecutor(max_workers=2) as pool:
        cli = pool.submit(cli_freeze)
        web = pool.submit(client.post, f"/api/reports/{day}")
        frozen = web.result().json()
        assert cli.result() == frozen
    assert client.get(f"/api/reports/{day}/export?format=json").json() == frozen
    assert (
        frozen["cutoff_at"]
        in client.get(f"/api/reports/{day}/export?format=markdown").text
    )

def test_offline_default_and_published_sessions_after_calendar_rollover(tmp_path, monkeypatch):
    from datetime import datetime
    from fastapi.testclient import TestClient
    from roll import web, reports, calibration
    from roll.db import connect
    from roll.market.inputs import initialize_inputs

    class January(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2027, 1, 5, 18, tzinfo=tz)

    for module in (web, reports, calibration):
        monkeypatch.setattr(module, "datetime", January)
    with TestClient(web.create_app(tmp_path)) as client:
        fallback = client.get("/api/session").json()
        assert fallback["calendar_stale"] and fallback["trade_date"] == "2026-12-31"
        assert client.get("/api/market?day=2026-12-31").status_code == 200
        with connect(tmp_path / "roll.sqlite3") as db:
            initialize_inputs(db)
            for day in ("2027-01-04", "2027-01-05"):
                db.execute("INSERT INTO market_inputs VALUES('calendar','CN',?,'{}')", (day,))
        assert client.get("/api/session").json() == {
            "trade_date": "2027-01-05", "calendar_stale": False, "notice": None}
        assert client.get("/api/market?day=2027-01-05").status_code == 200
        assert client.get("/api/market?day=2027-01-01").status_code == 422
        report = client.post("/api/reports/2027-01-05").json()
        assert report["risk"]["trade_date"] == "2027-01-05"
        assert report["forward"]["trading_days"] == 2
