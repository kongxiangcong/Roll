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
