from fastapi.testclient import TestClient
from roll.app import create_app
from test_account import submit
from test_fills import establish,fill,fee_adjustment


def cash(kind,version,record,amount="100.00"):
    return {"kind":kind,"expected_account_version":version,"payload":{
        "effective_at":"2026-10-07T11:00:00+08:00","source":"用户核对真实账户流水",
        "record_id":record,"amount":amount,"instrument":None,"basis":"券商已到账记录",
        "broker_available_after":None}}


def test_interest_and_deposit_are_distinct_actual_income_and_external_flows(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        draft=client.post("/api/account/drafts",json=cash("INTEREST",1,"interest","20.00"))
        assert draft.status_code==201
        assert draft.json()["preview"]["cash_balance"]["after"]=="100020.00"
        assert client.get("/api/account").json()["cash_balance"]=="100000.00"
        receipt=client.post("/api/account/confirm",json={"draft_id":draft.json()["draft_id"],"idempotency_key":"interest"}).json()
        assert client.get("/api/account/receipts/"+receipt["receipt_id"]).json()==receipt
        assert submit(client,cash("CASH_IN",2,"deposit","5000.00"),"deposit").status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="105020.00"
        assert account["investment_income"]=="20.00"
        assert account["external_cash_in"]=="5000.00"
        assert account["external_cash_out"]=="0.00"
        assert account["broker_available"] is None
        events=client.get("/api/account/events").json()
        assert [e["event_type"] for e in events[-2:]]==["INTEREST","CASH_IN"]
        assert events[-1]["payload"]["flow_category"]=="EXTERNAL_IN"
        assert client.get("/api/account/replay").json()["investment_income"]=="20.00"


def pending(version,record="dividend-due",amount="100.00",item_type="DIVIDEND"):
    return {"kind":"PENDING_ITEM","expected_account_version":version,"payload":{
        "effective_at":"2026-10-07T11:00:00+08:00","source":"用户确认个人账户应收事项",
        "record_id":record,"item_type":item_type,"amount":amount,"instrument":"SSE:600000","basis":"账户权益明细"}}


def settle(version,record="settlement-1",amount="40.00",target="dividend-due"):
    return {"kind":"SETTLEMENT","expected_account_version":version,"payload":{
        "effective_at":"2026-10-07T12:00:00+08:00","source":"用户核对实际到账",
        "record_id":record,"target_record_id":target,"amount":amount,"basis":"券商到账流水","broker_available_after":None}}


def test_confirmed_receivable_then_partial_and_full_settlement_do_not_count_income_twice(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        before=client.get("/api/account").json()
        result=submit(client,pending(1),"pending")
        assert result.status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="100000.00"
        assert account["broker_available"]==before["broker_available"]
        assert account["positions"]==before["positions"]
        assert account["pending_income"]=="100.00"
        assert account["investment_income"]=="0.00"
        item=account["pending_items"][0]
        assert item["status"]=="OPEN"
        assert item["confirmed_at"]==result.json()["confirmed_at"]
        first=submit(client,settle(2),"settlement")
        assert first.status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="100040.00"
        assert account["investment_income"]=="40.00"
        assert account["pending_income"]=="60.00"
        assert account["pending_items"][0]["status"]=="PARTIAL"
        duplicate=client.post("/api/account/drafts",json=settle(3)).json()
        assert duplicate["status"]=="QUARANTINED"
        assert client.post("/api/account/confirm",json={"draft_id":duplicate["draft_id"],"idempotency_key":"duplicate-record"}).status_code==422
        assert submit(client,settle(3,"settlement-2","60.00"),"rest").status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="100100.00"
        assert account["investment_income"]=="100.00"
        assert account["pending_income"]=="0.00"
        assert account["pending_items"][0]["amount"]=="100.00"
        assert account["pending_items"][0]["status"]=="SETTLED"
        replay=client.get("/api/account/replay").json()
        assert replay["pending_items"]==account["pending_items"]
        assert replay["cash_balance"]=="100100.00"


def shares(version,quantity="300",record="shares-1"):
    return {"kind":"SHARE_CHANGE","expected_account_version":version,"payload":{
        "effective_at":"2026-10-07T12:30:00+08:00","source":"用户核对实际股份到账",
        "record_id":record,"instrument":"SSE:600000","new_quantity":quantity,"basis":"券商数量权益明细"}}


def test_share_change_carries_exact_cost_and_later_fee_adjustment_through_partial_sales(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        submit(client,fill(fee_status="PROVISIONAL"),"buy")
        sell=fill(2,"pre-split-sell","SELL")
        sell["payload"].update(quantity="100",price="12.00")
        submit(client,sell,"first-sale")
        assert client.get("/api/account").json()["positions"][0]["acquisition_cost"]=="2006.67"
        draft=client.post("/api/account/drafts",json=shares(3)).json()
        assert draft["status"]=="READY"
        assert client.get("/api/account").json()["positions"][0]["quantity"]=="200"
        assert client.post("/api/account/confirm",json={"draft_id":draft["draft_id"],"idempotency_key":"shares"}).status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="98185.00"
        assert account["positions"][0]["quantity"]=="300"
        assert account["positions"][0]["acquisition_cost"]=="2006.67"
        sell=fill(4,"post-split-sell","SELL")
        sell["payload"].update(quantity="100",price="8.00",effective_at="2026-10-07T13:00:00+08:00")
        submit(client,sell,"second-sale")
        actual_fee=fee_adjustment(5)
        actual_fee["payload"]["effective_at"]="2026-10-07T14:00:00+08:00"
        assert submit(client,actual_fee,"actual-fee").status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="98985.00"
        assert account["positions"][0]["quantity"]=="200"
        assert account["positions"][0]["acquisition_cost"]=="1335.55"
        assert account["realized_gain"]=="320.55"
        assert account["fills"][0]["quantity"]=="300"
        replay=client.get("/api/account/replay").json()
        assert replay["cash_balance"]=="98985.00"
        assert replay["lots"]==account["lots"]
        assert replay["realized_gain"]=="320.55"


def test_web_claim_is_only_pending_material_and_unknown_personal_amount_or_time_is_not_booked(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        before=client.get("/api/account").json()
        hint={"source":"https://example.invalid/announcement","declared_at":"2026-10-06",
              "instrument":"SSE:600000","content":"公告称每10股送3股并已分红，不代表该用户到账"}
        response=client.post("/api/account/equity-hints",json=hint)
        assert response.status_code==201
        saved=response.json()
        assert saved["content"]==hint["content"]
        assert saved["declared_at"]=="2026-10-06"
        assert saved["learned_at"]
        assert saved["actual_effective_at"] is None
        assert client.get("/api/account/equity-hints").json()==[saved]
        assert client.get("/api/account").json()==before
        assert "外部权益线索待核" in " ".join(client.get("/api/today").json()["pending_items"])
        for field in ["amount","effective_at"]:
            command=pending(1,"unknown-"+field)
            command["payload"][field]=None
            draft=client.post("/api/account/drafts",json=command).json()
            assert draft["status"]=="QUARANTINED"
            assert draft["command"]==command
            assert client.post("/api/account/confirm",json={"draft_id":draft["draft_id"],"idempotency_key":field}).status_code==422
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="100000.00"
        assert account["version"]==1


def correct(version,target,amount,record="correction-1"):
    return {"kind":"CASH_CORRECTION","expected_account_version":version,"payload":{
        "effective_at":"2026-10-07T13:00:00+08:00","source":"用户追加核对更正",
        "record_id":record,"target_record_id":target,"corrected_amount":amount,"basis":"原材料金额核对错误，追加更正","broker_available_after":None}}


def test_payable_partial_settlement_and_append_corrections_preserve_originals_and_net_balance(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        assert submit(client,pending(1,"tax-due","30.00","TAX"),"tax").status_code==200
        assert submit(client,settle(2,"tax-paid","10.00","tax-due"),"part").status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="99990.00"
        assert account["investment_expenses"]=="10.00"
        assert account["pending_expenses"]=="20.00"
        assert submit(client,correct(3,"tax-due","25.00"),"correct-due").status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="99990.00"
        assert account["pending_expenses"]=="15.00"
        assert account["pending_items"][0]["amount"]=="30.00"
        assert account["pending_items"][0]["resolved_amount"]=="25.00"
        assert submit(client,correct(4,"tax-paid","8.00","correction-2"),"correct-payment").status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="99992.00"
        assert account["investment_expenses"]=="8.00"
        assert account["pending_expenses"]=="17.00"
        assert submit(client,settle(5,"tax-rest","17.00","tax-due"),"rest").status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="99975.00"
        assert account["investment_expenses"]=="25.00"
        assert account["pending_expenses"]=="0.00"
        events=client.get("/api/account/events").json()
        assert events[2]["payload"]["amount"]=="30.00"
        assert events[3]["payload"]["amount"]=="10.00"
        assert events[4]["payload"]["target_record_id"]=="tax-due"
        replay=client.get("/api/account/replay").json()
        assert replay["cash_balance"]=="99975.00"
        assert replay["pending_items"]==account["pending_items"]


def test_all_cash_categories_and_multiple_corrections_keep_independent_literal_totals(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        for version,kind,record,amount in [(1,"CASH_OUT","withdraw","50.00"),(2,"DIVIDEND","div","12.34"),
                                         (3,"FEE","fee","2.00"),(4,"TAX","tax","3.21"),(5,"CASH_IN","deposit-cent","0.01")]:
            assert submit(client,cash(kind,version,record,amount),record).status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="99957.14"
        assert account["investment_income"]=="12.34"
        assert account["investment_expenses"]=="5.21"
        assert account["external_cash_in"]=="0.01"
        assert account["external_cash_out"]=="50.00"
        assert submit(client,correct(6,"div","15.00","div-correction-1"),"correction-1").status_code==200
        assert submit(client,correct(7,"div","14.00","div-correction-2"),"correction-2").status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="99958.80"
        assert account["investment_income"]=="14.00"
        assert account["cash_records"][1]["amount"]=="12.34"
        assert account["cash_records"][-1]["previous_correction_id"]=="div-correction-1"
        assert client.get("/api/account/replay").json()["cash_balance"]=="99958.80"


def test_cash_failures_unknown_tax_and_over_settlement_preserve_raw_inputs_and_booked_state(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        submit(client,pending(1,"due","100.00"),"pending")
        submit(client,settle(2,"part","40.00","due"),"part")
        before=client.get("/api/account").json()
        commands=[settle(3,"over","60.01","due"),correct(3,"due","39.99"),cash("CASH_OUT",3,"overdraw","1000000.00"),
                  cash("TAX",3,"unknown-tax",None),cash("FEE",3,"float-fee",0.1),shares(3,None)]
        for i,command in enumerate(commands):
            draft=client.post("/api/account/drafts",json=command).json()
            assert draft["status"]=="QUARANTINED"
            assert draft["command"]==command
            assert client.post("/api/account/confirm",json={"draft_id":draft["draft_id"],"idempotency_key":f"bad-{i}"}).status_code==422
        after=client.get("/api/account").json()
        assert after["version"]==before["version"]==3
        assert after["cash_balance"]=="100040.00"
        assert after["pending_income"]=="60.00"
        assert len(client.get("/api/account/quarantined-drafts").json())==6
        assert "资金或权益输入待核" in " ".join(client.get("/api/today").json()["pending_items"])


def test_cash_confirmation_concurrency_and_stale_draft_use_the_existing_atomic_writer(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        interest=client.post("/api/account/drafts",json=cash("INTEREST",1,"interest","20.00")).json()
        stale=client.post("/api/account/drafts",json=cash("CASH_IN",1,"stale","10.00")).json()
        command={"draft_id":interest["draft_id"],"idempotency_key":"concurrent-interest"}
        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts=list(pool.map(lambda _:client.post("/api/account/confirm",json=command),range(4)))
        assert all(r.status_code==200 for r in receipts)
        assert len({r.json()["receipt_id"] for r in receipts})==1
        assert client.post("/api/account/confirm",json={"draft_id":stale["draft_id"],"idempotency_key":"stale"}).status_code==409
        assert client.get("/api/account").json()["cash_balance"]=="100020.00"
        assert len(client.get("/api/account/events").json())==3


def test_share_change_distributes_eight_decimal_quantity_and_cent_cost_with_last_lot_remainder(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        for version,record,quantity,price in [(1,"buy-1","100.00000001","1.00000001"),(2,"buy-2","100","1")]:
            command=fill(version,record)
            command["payload"].update(quantity=quantity,price=price)
            submit(client,command,record)
        submit(client,shares(3,"300.00000001"),"share")
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="99790.00"
        assert account["positions"][0]["quantity"]=="300.00000001"
        assert account["positions"][0]["acquisition_cost"]=="210.00"
        event=client.get("/api/account/events").json()[-1]
        assert [row["quantity"] for row in event["payload"]["lot_transfers"]]==["150.00000001","150.00000000"]
        assert [row["cost"] for row in event["payload"]["lot_transfers"]]==["105.00","105.00"]
        assert client.get("/api/account/replay").json()["lots"]==account["lots"]


def test_share_reference_cost_at_maximum_input_precision_does_not_claim_known_acquisition_cost(tmp_path):
    from test_account import baseline
    with TestClient(create_app(tmp_path)) as client:
        command=baseline()
        command["payload"]["positions"][0].update(quantity="999999999999999999.99999999",reference_cost="999999999999999999.99999999",sellable_quantity=None)
        submit(client,command,"large-baseline")
        submit(client,shares(1,"999999999999999998.99999999"),"actual-quantity")
        account=client.get("/api/account").json()
        assert account["positions"][0]["acquisition_cost"] is None
        assert account["positions"][0]["quantity"]=="999999999999999998.99999999"
        assert account["positions"][0]["reference_cost"] is None
        assert client.get("/api/account/versions/1").json()["positions"][0]["reference_cost"]=="999999999999999999.99999999"
        transfer=client.get("/api/account/events").json()[-1]["payload"]["lot_transfers"][0]
        assert transfer["cost"]=="999999999999999999999999980000000000.00"
        assert client.get("/api/account/replay").json()["lots"]==account["lots"]


def test_fee_resolution_across_two_share_transfers_and_partial_sales_keeps_literal_total_cost(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        submit(client,fill(fee_status="PROVISIONAL"),"buy")
        submit(client,shares(2,"600","first-share"),"share-1")
        first_sale=fill(3,"sale-1","SELL")
        first_sale["payload"].update(quantity="100",price="5.00",effective_at="2026-10-07T12:45:00+08:00")
        submit(client,first_sale,"sale-1")
        second_share=shares(4,"250","second-share")
        second_share["payload"]["effective_at"]="2026-10-07T13:00:00+08:00"
        submit(client,second_share,"share-2")
        second_sale=fill(5,"sale-2","SELL")
        second_sale["payload"].update(quantity="50",price="10.00",effective_at="2026-10-07T13:30:00+08:00")
        submit(client,second_sale,"sale-2")
        fee=fee_adjustment(6)
        fee["payload"]["effective_at"]="2026-10-07T14:00:00+08:00"
        submit(client,fee,"fee")
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="97985.00"
        assert account["positions"][0]["quantity"]=="200"
        assert account["positions"][0]["acquisition_cost"]=="2003.34"
        assert account["realized_gain"]=="-11.66"
        assert account["fills"][0]["quantity"]=="300"
        replay=client.get("/api/account/replay").json()
        assert replay["cash_balance"]=="97985.00"
        assert replay["lots"]==account["lots"]
        assert replay["realized_gain"]=="-11.66"
