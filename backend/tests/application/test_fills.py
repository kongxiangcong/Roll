from fastapi.testclient import TestClient
from roll.app import create_app
from test_account import baseline, submit


def establish(client):
    command=baseline()
    command["payload"].update(cash_balance="100000.00",broker_available="100000.00",broker_frozen="0.00",positions=[])
    return submit(client,command,"baseline").json()


def fill(version=1,record="manual-1",direction="BUY",fee_status="KNOWN"):
    return {"kind":"FILL","expected_account_version":version,"payload":{
        "effective_at":"2026-10-07T11:00:00+08:00","source":"用户核对真实成交回报",
        "instrument":"SSE:600000","direction":direction,"quantity":"300","price":"10.00",
        "record_id":record,"fill_id":record,"order_id":"order-1","behavior_context":"NO_RECOMMENDATION",
        "fee":{"status":fee_status,"amount":"5.00" if fee_status=="KNOWN" else None,
               "reserve_amount":None if fee_status=="KNOWN" else "10.00","basis":"券商成交回报" if fee_status=="KNOWN" else "用户按券商费率及最低费用保守估计"},
        "broker_available_after":None}}


def test_actual_buy_preview_and_confirm_preserve_exact_cash_and_acquisition_cost(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        draft=client.post("/api/account/drafts",json=fill())
        assert draft.status_code==201
        draft=draft.json()
        assert draft["status"]=="READY"
        assert draft["preview"]["cash_balance"]["after"]=="96995.00"
        assert client.get("/api/account").json()["cash_balance"]=="100000.00"
        result=client.post("/api/account/confirm",json={"draft_id":draft["draft_id"],"idempotency_key":"buy"})
        assert result.status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="96995.00"
        assert account["positions"][0]["quantity"]=="300"
        assert account["positions"][0]["acquisition_cost"]=="3005.00"
        assert account["positions"][0]["sellable_quantity"] is None
        event=client.get("/api/account/events").json()[-1]
        assert event["event_type"]=="BUY_FILL"
        assert event["payload"]["price"]=="10.00"
        assert event["payload"]["action_association"]["status"]=="UNKNOWN"
        assert client.get("/api/account/receipts/"+result.json()["receipt_id"]).json()==result.json()
def test_partial_then_complete_sell_preserves_cost_remainder_and_cash(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        assert submit(client,fill(),"buy").status_code==200
        sell=fill(2,"sell-1","SELL")
        sell["payload"].update(quantity="100",price="12.00")
        assert submit(client,sell,"sell-1").status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="98190.00"
        assert account["positions"][0]["quantity"]=="200"
        assert account["positions"][0]["acquisition_cost"]=="2003.33"
        assert account["realized_gain"]=="193.33"
        sell=fill(3,"sell-2","SELL")
        sell["payload"].update(quantity="200",price="12.00")
        assert submit(client,sell,"sell-2").status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="100585.00"
        assert account["positions"]==[]
        assert account["realized_gain"]=="585.00"
def fee_adjustment(version,amount="5.00",target="manual-1"):
    return {"kind":"FEE_ADJUSTMENT","expected_account_version":version,"payload":{
        "effective_at":"2026-10-07T12:00:00+08:00","source":"补充实际费用回报",
        "target_record_id":target,"actual_fee_amount":amount,"basis":"券商已结算费用"}}


def test_unknown_fee_then_partial_sell_and_append_adjustment_matches_known_fee_replay(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        assert submit(client,fill(fee_status="PROVISIONAL"),"unknown-fee").status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="96990.00"
        assert account["cash_balance_basis"]=="PROVISIONAL_FEES"
        assert account["conservative_available"]=="96990.00"
        assert account["broker_available"] is None
        assert account["net_result_state"]=="FEE_PENDING"
        sell=fill(2,"sell-1","SELL")
        sell["payload"].update(quantity="100",price="12.00")
        assert submit(client,sell,"sell").status_code==200
        assert client.get("/api/account").json()["positions"][0]["acquisition_cost"]=="2006.67"
        assert submit(client,fee_adjustment(3),"fee-known").status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="98190.00"
        assert account["positions"][0]["acquisition_cost"]=="2003.33"
        assert account["realized_gain"]=="193.33"
        assert account["net_result_state"]=="KNOWN_FEES"
        assert account["fills"][0]["fee"]["status"]=="PROVISIONAL"
        assert account["fee_resolutions"]["manual-1"]["actual_fee_amount"]=="5.00"
        events=client.get("/api/account/events").json()
        assert events[-1]["event_type"]=="FEE_ADJUSTMENT"
        assert events[-1]["payload"]["cash_delta"]=="5.00"
        assert events[-3]["payload"]["fee"]["amount"] is None
        replay=client.get("/api/account/replay").json()
        assert replay["cash_balance"]==account["cash_balance"]
        assert replay["positions"]==account["positions"]
        assert replay["lots"]==account["lots"]
        assert replay["realized_gain"]=="193.33"
def test_contradictory_and_malformed_actual_inputs_remain_quarantined_without_partial_bookings(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        before=client.get("/api/account").json()
        for record,price in [("negative-position","10.00"),("malformed-price","不能推定")]:
            command=fill(1,record,"SELL")
            command["payload"]["price"]=price
            result=client.post("/api/account/drafts",json=command)
            assert result.status_code==201
            draft=result.json()
            assert draft["status"]=="QUARANTINED"
            assert draft["command"]==command
            assert draft["issues"]
            assert client.get("/api/account/drafts/"+draft["draft_id"]).json()["command"]==command
            assert client.post("/api/account/confirm",json={"draft_id":draft["draft_id"],"idempotency_key":record}).status_code==422
        account=client.get("/api/account").json()
        assert account["cash_balance"]==before["cash_balance"]
        assert account["version"]==1
        assert account["state"]=="RECONCILE_REQUIRED"
        assert len(client.get("/api/account/quarantined-drafts").json())==2
        assert len(client.get("/api/account/events").json())==2
        assert "成交输入待核" in " ".join(client.get("/api/today").json()["pending_items"])
def test_distinct_same_price_fills_one_order_and_adverse_no_action_facts_are_retained(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        first=fill()
        first["payload"]["behavior_context"]="CONTRARY"
        receipt=submit(client,first,"first").json()
        second=fill(2,"manual-2")
        second["payload"]["behavior_context"]="EXCESS_QUANTITY"
        assert submit(client,second,"second").status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="93990.00"
        assert account["positions"][0]["quantity"]=="600"
        assert len(account["fills"])==2
        assert len({f["order_id"] for f in account["fills"]})==1
        assert all(f["action_association"]["status"]=="UNKNOWN" for f in account["fills"])
        duplicate=fill(3,"different-manual-capture")
        duplicate["payload"]["fill_id"]="manual-1"
        response=client.post("/api/account/drafts",json=duplicate)
        assert response.status_code==409
        assert response.json()["detail"]["receipt_id"]==receipt["receipt_id"]
        assert client.get("/api/account").json()["version"]==3
        assert "新增" in " ".join(client.get("/api/today").json()["pending_items"])


def test_missing_fill_identity_is_not_merged_and_ambiguity_is_explicit(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        for version,record in [(1,"manual-a"),(2,"manual-b")]:
            command=fill(version,record)
            command["payload"].update(fill_id=None,behavior_context="OFFLINE")
            draft=client.post("/api/account/drafts",json=command).json()
            assert draft["status"]=="READY"
            assert "缺少券商分笔成交标识" in " ".join(draft["issues"])
            assert client.post("/api/account/confirm",json={"draft_id":draft["draft_id"],"idempotency_key":record}).status_code==200
        account=client.get("/api/account").json()
        assert len(account["fills"])==2
        assert account["positions"][0]["quantity"]=="600"
def test_sell_from_initial_position_with_unknown_historical_cost_does_not_invent_gain(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        command=baseline()
        command["payload"].update(cash_balance="100000.00")
        command["payload"]["positions"][0]["reference_cost"]=None
        submit(client,command,"baseline")
        sell=fill(1,"sell-baseline","SELL")
        sell["payload"].update(quantity="100",price="12.00")
        response=submit(client,sell,"sell")
        assert response.status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="101195.00"
        assert account["positions"][0]["quantity"]=="200"
        assert account["positions"][0]["acquisition_cost"] is None
        assert account["realized_gain"] is None
        assert account["net_result_state"]=="COST_UNKNOWN"
        assert client.get("/api/account/replay").json()["cash_balance"]=="101195.00"
def test_fill_does_not_reconfirm_permissions_and_original_price_precision_survives(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        original=client.get("/api/account").json()["permission_profile"]
        command=fill()
        command["payload"].update(quantity="300.00000000",price="10.12345678",broker_available_after="90001.20")
        assert submit(client,command,"precision").status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="96957.96"
        assert account["positions"][0]["acquisition_cost"]=="3042.04"
        assert account["broker_available"]=="90001.20"
        assert account["conservative_available"]=="90001.20"
        assert account["broker_available_as_of"]=="2026-10-07T11:00:00+08:00"
        assert account["broker_frozen_as_of"]=="2026-10-07T10:00:00+08:00"
        assert account["permission_profile"]==original
        assert client.get("/api/account/versions/1").json()["permission_profile"]==original
        event=client.get("/api/account/events").json()[-1]
        assert event["payload"]["price"]=="10.12345678"
        assert event["payload"]["quantity"]=="300.00000000"
        assert event["payload"]["gross_amount"]=="3037.04"
        assert len(client.get("/api/account/events").json())==3


def test_fee_correction_preserves_original_known_fee_and_retry_cannot_apply_twice(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        submit(client,fill(),"buy")
        draft=client.post("/api/account/drafts",json=fee_adjustment(2,"8.00")).json()
        command={"draft_id":draft["draft_id"],"idempotency_key":"adjust"}
        receipt=client.post("/api/account/confirm",json=command).json()
        assert client.post("/api/account/confirm",json=command).json()==receipt
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="96992.00"
        assert account["positions"][0]["acquisition_cost"]=="3008.00"
        assert account["fills"][0]["fee"]["amount"]=="5.00"
        assert client.get("/api/account/replay").json()["cash_balance"]=="96992.00"


def test_unknown_account_permission_cannot_reject_an_actual_star_board_fill(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        command=fill()
        command["payload"].update(instrument="SSE:688001",behavior_context="OFFLINE")
        assert submit(client,command,"already-happened").status_code==200
        assert client.get("/api/account").json()["positions"][0]["instrument"]=="SSE:688001"
        assert client.get("/api/today").json()["formal_judgment"]=="DISABLED"


def test_reused_broker_fill_id_with_different_content_is_preserved_as_quarantine(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        submit(client,fill(),"buy")
        changed=fill(2,"different-capture")
        changed["payload"].update(fill_id="manual-1",quantity="301")
        draft=client.post("/api/account/drafts",json=changed).json()
        assert draft["status"]=="QUARANTINED"
        assert draft["command"]==changed
        assert client.get("/api/account").json()["positions"][0]["quantity"]=="300"


def test_concurrent_fill_confirmation_is_atomic_and_idempotent(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        draft=client.post("/api/account/drafts",json=fill()).json()
        command={"draft_id":draft["draft_id"],"idempotency_key":"double-fill"}
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses=list(pool.map(lambda _:client.post("/api/account/confirm",json=command),range(4)))
        assert all(r.status_code==200 for r in responses)
        assert len({r.json()["receipt_id"] for r in responses})==1
        assert client.get("/api/account").json()["cash_balance"]=="96995.00"
        assert client.get("/api/account").json()["positions"][0]["quantity"]=="300"
