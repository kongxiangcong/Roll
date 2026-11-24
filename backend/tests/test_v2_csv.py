"""Import trade rows and reconcile their receipt through the v2 account entry."""
import csv

from roll.accounts.csv_import import COLUMNS, VERSION
from test_v2_account import account


def test_csv_receipt_reconciles_cash_fills_positions_and_retry(tmp_path):
    def write_file(name, rows):
        path = tmp_path / name
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({
                    "template_version": VERSION, "effective_at": "2025-05-06T10:00:00+08:00",
                    "source": "券商流水", **row,
                })
        return str(path)

    baseline = write_file("opening.csv", [{"kind": "BASELINE_CASH", "cash_balance": "10000.00"}])
    opening = account(tmp_path, "import-csv", baseline)
    initial_receipt = account(tmp_path, "confirm", opening["draft_id"], "opening")
    fill = {"kind": "FILL", "exchange": "SSE", "direction": "BUY", "quantity": "100",
            "fee_status": "KNOWN", "fee_amount": "5.00", "basis": "交割单"}
    trades = write_file("trades.csv", [
        {**fill, "code": "600362", "price": "23.75", "fill_id": "broker-1"},
        {**fill, "code": "600000", "price": "10.10", "fill_id": "broker-2"},
    ])
    preview = account(tmp_path, "import-csv", trades)
    assert preview["status"] == "READY" and preview["receipt"] is None
    receipt = account(tmp_path, "confirm", preview["draft_id"], "two-fills")
    retry = account(tmp_path, "import-csv", trades)
    assert retry["receipt"] == receipt
    result = account(tmp_path, "reconcile", receipt["receipt_id"])
    assert result["account_version"] == 2
    assert result["cash_balance"] == "6605.00"
    assert {p["instrument"]: p["quantity"] for p in result["positions"]} == {
        "SSE:600362": "100", "SSE:600000": "100",
    }
    assert [row["fill_id"] for row in result["fills"]] == ["broker-1", "broker-2"]
    assert account(tmp_path, "show")["version"] == 2
    original = account(tmp_path, "reconcile", initial_receipt["receipt_id"])
    assert (original["cash_balance"], original["positions"], original["fills"]) == ("10000.00", [], [])
