import httpx
import pytest
from test_account_process import Server


BASELINE={"kind":"BASELINE","expected_account_version":0,"payload":{
    "effective_at":"2026-10-07T10:00:00+08:00","source":"脱敏成交恢复基线","cash_balance":"100000.00",
    "broker_available":"100000.00","broker_frozen":"0.00","withdrawable":None,"positions":[],"permission_profile":[]}}


@pytest.mark.parametrize("fault,expected_version",[("before_commit",1),("after_commit",2),("after_receipt",2)])
def test_actual_fill_receipt_and_cash_survive_real_process_fault(tmp_path,fault,expected_version):
    directory=tmp_path/"data"
    server=Server(directory)
    draft=server.client.post("/api/account/drafts",json=BASELINE).json()
    assert server.client.post("/api/account/confirm",json={"draft_id":draft["draft_id"],"idempotency_key":"baseline"}).status_code==200
    fill={"kind":"FILL","expected_account_version":1,"payload":{
        "effective_at":"2026-10-07T11:00:00+08:00","source":"脱敏成交回报","instrument":"SSE:600000",
        "direction":"BUY","quantity":"300","price":"10.00","record_id":"recovery-fill","fill_id":"actual-fill-1",
        "order_id":"order-1","behavior_context":"NO_RECOMMENDATION","broker_available_after":None,
        "fee":{"status":"KNOWN","amount":"5.00","reserve_amount":None,"basis":"券商费用回报"}}}
    draft=server.client.post("/api/account/drafts",json=fill).json()
    command={"draft_id":draft["draft_id"],"idempotency_key":"actual-fill"}
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
        assert client.get("/api/account").json()["cash_balance"]=="96995.00"
        assert len(client.get("/api/account").json()["fills"])==1
        assert len(client.get("/api/account/events").json())==3
        assert client.get("/api/account/replay").json()["cash_balance"]=="96995.00"
    finally:
        recovered.stop()
