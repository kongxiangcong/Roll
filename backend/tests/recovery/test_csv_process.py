import csv
import io

import httpx
import pytest
from test_account_process import Server
from test_fill_process import BASELINE


@pytest.mark.parametrize("fault,expected_version", [("before_commit", 1), ("after_commit", 2), ("after_receipt", 2)])
def test_whole_csv_batch_and_original_file_survive_real_process_crash(tmp_path, fault, expected_version):
    directory = tmp_path / "data"
    server = Server(directory)
    try:
        baseline = server.client.post("/api/account/drafts", json=BASELINE).json()
        server.client.post("/api/account/confirm", json={"draft_id": baseline["draft_id"], "idempotency_key": "baseline"}).raise_for_status()
        columns = next(csv.reader(io.StringIO(server.client.get("/api/account/csv/template",params={"version":"ROLL-CSV-1"}).text.lstrip("\ufeff"))))
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, columns)
        writer.writeheader()
        for fill_id in ["process-a", "process-b"]:
            writer.writerow({"template_version": "ROLL-CSV-1", "kind": "FILL", "effective_at": "2026-10-07T11:00:00+08:00", "source": "进程恢复脱敏文件", "exchange": "SZSE", "code": "000001", "direction": "BUY", "quantity": "100", "price": "10.00", "fee_status": "KNOWN", "fee_amount": "5.00", "basis": "实际费用", "fill_id": fill_id, "order_id": "one-order"})
        raw = output.getvalue().encode("utf-8")
        draft = server.client.post("/api/account/csv/drafts", params={"filename": "恢复.csv", "encoding": "utf-8", "expected_account_version": 1}, content=raw).json()
        command = {"draft_id": draft["draft_id"], "idempotency_key": "csv-process"}
    finally:
        server.stop()
    server = Server(directory, None if fault == "after_receipt" else fault)
    original = None
    try:
        if fault == "after_receipt":
            response = server.client.post("/api/account/confirm", json=command)
            response.raise_for_status()
            original = response.json()
            server.stop()
        else:
            with pytest.raises(httpx.TransportError):
                server.client.post("/api/account/confirm", json=command)
            assert server.process.wait(timeout=10) == 86
    finally:
        server.stop()
    recovered = Server(directory)
    try:
        client = recovered.client
        account = client.get("/api/account").json()
        assert account["version"] == expected_version
        assert len(account.get("fills", [])) == (0 if expected_version == 1 else 2)
        assert client.get("/api/account/csv/files/" + draft["file"]["sha256"]).content == raw
        receipt = client.post("/api/account/confirm", json=command).json()
        assert client.post("/api/account/confirm", json=command).json() == receipt
        if original:
            assert receipt == original
        assert client.get("/api/account/csv/drafts/" + draft["draft_id"]).json()["receipt"] == receipt
        assert client.get("/api/account").json()["cash_balance"] == "97990.00"
        assert len(client.get("/api/account/audit").json()) == 2
        assert len(client.get("/api/account/events").json()) == 4
        assert client.get("/api/account/replay").json()["cash_balance"] == "97990.00"
    finally:
        recovered.stop()
