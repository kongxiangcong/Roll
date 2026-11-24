"""Exercise the independent v2 entry point across actual process restarts."""
import json
import os
from pathlib import Path
import subprocess
import sys


def account(directory, *args, command=None):
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "roll.cli", "--data-dir", str(directory), "account", *args],
        input=json.dumps(command), text=True, encoding="utf-8", capture_output=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_new_account_can_be_read_offline(tmp_path):
    initial = account(tmp_path, "show")
    assert initial["version"] == 0
    assert initial["positions"] == []


def test_cash_and_actual_fill_survive_restart_and_retry(tmp_path):
    source = {"source": "券商流水", "effective_at": "2025-03-03T09:31:00+08:00"}

    def post(kind, version, payload):
        draft = account(tmp_path, "draft", command={
            "kind": kind, "expected_account_version": version, "payload": {**source, **payload},
        })
        return draft["draft_id"], account(tmp_path, "confirm", draft["draft_id"], kind)

    post("BASELINE", 0, {
        "cash_balance": "0.00", "positions": [], "permission_profile": [],
        "broker_available": None, "broker_frozen": None, "withdrawable": None,
    })
    post("CASH_IN", 1, {
        "record_id": "deposit-1", "amount": "5000.10", "basis": "转入",
        "instrument": None, "broker_available_after": None,
    })
    draft_id, receipt = post("FILL", 2, {
        "record_id": "buy-1", "instrument": "SSE:600362", "direction": "BUY",
        "quantity": "100", "price": "21.321", "behavior_context": "OFFLINE",
        "fee": {"status": "KNOWN", "amount": "5.01", "reserve_amount": None, "basis": "交割单"},
        "fill_id": "fill-1", "order_id": None, "broker_available_after": None,
    })
    assert account(tmp_path, "confirm", draft_id, "FILL") == receipt
    snapshot = account(tmp_path, "show")
    assert snapshot["cash_balance"] == "2862.99"
    assert snapshot["version"] == 3
    assert [(p["instrument"], p["quantity"]) for p in snapshot["positions"]] == [("SSE:600362", "100")]
    assert [row["record_id"] for row in snapshot["fills"]] == ["buy-1"]
