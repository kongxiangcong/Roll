import httpx
import pytest
from test_account_process import Server
from test_fill_process import BASELINE


@pytest.mark.parametrize("fault,expected_version",[("before_commit",2),("after_commit",3),("after_receipt",3)])
def test_linked_settlement_receipt_and_pending_balance_survive_real_process_fault(tmp_path,fault,expected_version):
    directory=tmp_path/"data"
    server=Server(directory)
    for command,key in [(BASELINE,"baseline"),({"kind":"PENDING_ITEM","expected_account_version":1,"payload":{
        "effective_at":"2026-10-07T11:00:00+08:00","source":"合成个人应收凭证","record_id":"due",
        "item_type":"DIVIDEND","amount":"100.00","instrument":None,"basis":"账户权益明细"}},"due")]:
        draft=server.client.post("/api/account/drafts",json=command).json()
        assert server.client.post("/api/account/confirm",json={"draft_id":draft["draft_id"],"idempotency_key":key}).status_code==200
    settlement={"kind":"SETTLEMENT","expected_account_version":2,"payload":{
        "effective_at":"2026-10-07T12:00:00+08:00","source":"合成部分到账凭证","record_id":"paid",
        "target_record_id":"due","amount":"40.00","basis":"实际到账","broker_available_after":None}}
    draft=server.client.post("/api/account/drafts",json=settlement).json()
    command={"draft_id":draft["draft_id"],"idempotency_key":"settlement"}
    server.stop()
    server=Server(directory,None if fault=="after_receipt" else fault)
    original=None
    try:
        if fault=="after_receipt":
            response=server.client.post("/api/account/confirm",json=command)
            assert response.status_code==200
            original=response.json()
            server.stop()
        else:
            with pytest.raises(httpx.TransportError):
                server.client.post("/api/account/confirm",json=command)
            assert server.process.wait(timeout=10)==86
    finally:
        server.stop()
    recovered=Server(directory)
    try:
        client=recovered.client
        assert client.get("/api/account").json()["version"]==expected_version
        receipt=client.post("/api/account/confirm",json=command).json()
        assert client.post("/api/account/confirm",json=command).json()==receipt
        if original:
            assert receipt==original
        assert client.get("/api/account/receipts/"+receipt["receipt_id"]).json()==receipt
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="100040.00"
        assert account["investment_income"]=="40.00"
        assert account["pending_income"]=="60.00"
        assert account["pending_items"][0]["settlement_ids"]==["paid"]
        assert len(client.get("/api/account/events").json())==4
        assert client.get("/api/account/replay").json()["pending_items"]==account["pending_items"]
    finally:
        recovered.stop()
