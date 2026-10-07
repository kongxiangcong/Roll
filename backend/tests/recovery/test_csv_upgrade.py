"""An actual v1 service writes the archived CSV draft, v2 confirms it after upgrade."""
import csv
import io
import subprocess
from pathlib import Path

from test_account_process import Server


def test_original_csv_v1_draft_and_archive_can_be_confirmed_after_real_upgrade(tmp_path):
    repo = Path(__file__).resolve().parents[3]
    source = tmp_path/"csv-v1-source"
    files = ["__init__.py", "config.py", "app.py", "accounts/__init__.py", "accounts/ledger.py", "accounts/fills.py", "accounts/csv_import.py", "decisions/funding.py"]
    for name in files:
        contents = subprocess.run(["git", "show", f"855cfe8:backend/src/roll/{name}"], cwd=repo, capture_output=True, check=True).stdout.decode("utf-8")
        destination = source/"roll"/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(contents,encoding="utf-8")
    old = Server(tmp_path/"data", source_directory=source)
    try:
        columns = next(csv.reader(io.StringIO(old.client.get("/api/account/csv/template").text.lstrip("\ufeff"))))
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output,columns)
        writer.writeheader()
        writer.writerow({"template_version":"ROLL-CSV-1","kind":"BASELINE_CASH","effective_at":"2026-10-07T10:00:00+08:00","source":"原v1用户快照","cash_balance":"10000.10"})
        raw = output.getvalue().encode("utf-8")
        draft = old.client.post("/api/account/csv/drafts",params={"filename":"old.csv","encoding":"utf-8","expected_account_version":0},content=raw).json()
        assert draft["status"] == "READY"
    finally:
        old.stop()
    new = Server(tmp_path/"data")
    try:
        client = new.client
        assert client.get("/api/account/csv/drafts/"+draft["draft_id"]).json() == draft
        assert client.get("/api/account/csv/files/"+draft["file"]["sha256"]).content == raw
        receipt = client.post("/api/account/confirm",json={"draft_id":draft["draft_id"],"idempotency_key":"original-csv-v1"}).json()
        assert receipt["account_version"] == 1
        assert client.get("/api/account").json()["cash_balance"] == "10000.10"
        assert client.get("/api/account/csv/drafts/"+draft["draft_id"]).json()["receipt"] == receipt
    finally:
        new.stop()
