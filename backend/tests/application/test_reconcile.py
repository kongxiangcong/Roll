from fastapi.testclient import TestClient
from roll.app import create_app
from test_account import submit
from test_fills import establish, fill
from test_cash_events import pending,settle,cash,correct
from test_csv_import import upload,confirm
import json
from concurrent.futures import ThreadPoolExecutor


def trade(version,record,direction,price,at):
    command=fill(version,record,direction)
    command["payload"].update(quantity="100",price=price,effective_at=at)
    return command


def test_backfilled_trade_rebuilds_fifo_current_but_preserves_known_history_and_confirmed_versions(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        submit(client,trade(1,"later-buy","BUY","10.00","2026-10-07T12:00:00+08:00"),"buy")
        sale=trade(2,"sale","SELL","12.00","2026-10-07T13:00:00+08:00")
        sale["payload"]["broker_available_after"]="99000.00"
        old_receipt=submit(client,sale,"sale").json()
        old=client.get("/api/account/versions/3").json()
        assert old["cash_balance"]=="100190.00"
        assert old["realized_gain"]=="190.00"
        missed=trade(3,"missed-buy","BUY","5.00","2026-10-07T11:00:00+08:00")
        missed["payload"]["broker_available_after"]="99495.00"
        late=submit(client,missed,"backfill")
        assert late.status_code==200
        current=client.get("/api/account").json()
        assert current["cash_balance"]=="99685.00"
        assert current["positions"][0]["acquisition_cost"]=="1005.00"
        assert current["realized_gain"]=="690.00"
        assert current["effective_at"]==current["latest_effective_fact_at"]=="2026-10-07T13:00:00+08:00"
        assert current["latest_confirmed_input_at"]=="2026-10-07T11:00:00+08:00"
        assert current["system_known_at"]==late.json()["confirmed_at"]
        assert current["broker_available"]=="99000.00"
        assert current["broker_available_as_of"]=="2026-10-07T13:00:00+08:00"
        assert client.get("/api/account/versions/3").json()==old
        assert client.get("/api/account/receipts/"+old_receipt["receipt_id"]).json()==old_receipt
        at="2026-10-07T12:30:00+08:00"
        historical=client.get("/api/account/as-of",params={"known_by":old_receipt["confirmed_at"],"effective_at":at}).json()
        assert historical["account"]["cash_balance"]=="98995.00"
        assert historical["account"]["positions"][0]["quantity"]=="100"
        now_known=client.get("/api/account/as-of",params={"effective_at":at}).json()
        assert now_known["account"]["cash_balance"]=="98490.00"
        assert now_known["account"]["positions"][0]["quantity"]=="200"
        assert client.get("/api/account/replay").json()["realized_gain"]=="690.00"


def correction(version,record,target,replacement):
    return {"kind":"CORRECTION","expected_account_version":version,"payload":{
        "effective_at":"2026-10-07T14:00:00+08:00","source":"用户核对原始凭证","record_id":record,
        "target_event_id":target,"reason":"原成交价格录入有误，保留原件追加更正","replacement":replacement}}


def test_append_replacement_chain_and_reversal_rebuilds_dependents_without_mutating_originals(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        buy=trade(1,"buy","BUY","10.00","2026-10-07T11:00:00+08:00")
        buy_receipt=submit(client,buy,"buy").json()
        sale_receipt=submit(client,trade(2,"sale","SELL","12.00","2026-10-07T12:00:00+08:00"),"sale").json()
        original_events=client.get("/api/account/events").json()
        old=client.get("/api/account/versions/3").json()
        replacement={"kind":"FILL","payload":{**buy["payload"],"price":"8.00"}}
        first=submit(client,correction(3,"fix-buy",buy_receipt["event_ids"][0],replacement),"fix").json()
        assert client.get("/api/account").json()["cash_balance"]=="100390.00"
        assert client.get("/api/account").json()["realized_gain"]=="390.00"
        replacement["payload"]["price"]="9.00"
        second=submit(client,correction(4,"fix-again",first["event_ids"][0],replacement),"fix-again").json()
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="100290.00"
        assert account["corrections"][-1]["previous_correction_id"]==first["event_ids"][0]
        assert account["fills"][0]["receipt_id"]==second["receipt_id"]
        assert client.get("/api/account/events").json()[:len(original_events)]==original_events
        assert client.get("/api/account/versions/3").json()==old
        stale=client.post("/api/account/drafts",json=correction(5,"stale-chain",buy_receipt["event_ids"][0],replacement)).json()
        assert stale["status"]=="QUARANTINED"
        submit(client,correction(5,"reverse-sale",sale_receipt["event_ids"][0],None),"reverse-sale").raise_for_status()
        assert client.get("/api/account").json()["cash_balance"]=="99095.00"
        assert client.get("/api/account").json()["positions"][0]["quantity"]=="100"
        submit(client,correction(6,"reverse-buy",second["event_ids"][0],None),"reverse-buy").raise_for_status()
        replay=client.get("/api/account/replay").json()
        assert replay["cash_balance"]=="100000.00"
        assert replay["positions"]==[]


def declaration(version,scope,at="2026-10-07T14:00:00+08:00",changes="NONE",record="declare"):
    return {"kind":"ACCOUNT_DECLARATION","expected_account_version":version,"payload":{
        "effective_at":at,"source":"用户本次核对","record_id":record,"scope":scope,"changes":changes,"basis":"已查询券商记录，本次范围无未记录变化"}}


def test_scoped_no_change_declaration_is_used_only_for_requested_purpose_without_daily_backfill(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        request={"purpose":"NEW_RISK","required_as_of":"2026-10-07T13:00:00+08:00"}
        stale=client.post("/api/account/use-check",json=request).json()
        assert stale["state"]=="STALE_DECLARATION"
        assert stale["allowed"] is False
        market=client.post("/api/account/use-check",json={**request,"purpose":"MARKET_OBSERVATION"}).json()
        assert market["allowed"] is True
        assert "HOLD" not in str(stale)
        submit(client,declaration(1,["CASH"]),"cash-only").raise_for_status()
        partial=client.post("/api/account/use-check",json=request).json()
        assert partial["state"]=="STALE_DECLARATION"
        assert partial["missing_scope"]==["TRADES","ORDERS","EQUITY"]
        submit(client,declaration(2,["TRADES","ORDERS","CASH","EQUITY"],record="all"),"all").raise_for_status()
        complete=client.post("/api/account/use-check",json=request).json()
        assert complete["state"]=="CONFIRMED_AS_OF"
        assert complete["allowed"] is True
        assert complete["account_version"]==3
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="100000.00"
        assert account["positions"]==[]
        assert len(account["declarations"])==2
        assert account["declarations"][-1]["confirmed_as_of"]=="2026-10-07T14:00:00+08:00"
        outdated=client.post("/api/account/use-check",json={**request,"required_as_of":"2026-10-07T15:00:00+08:00"}).json()
        assert outdated["state"]=="STALE_DECLARATION"
        assert len(client.get("/api/account").json()["declarations"])==2


def reconcile(version,record,snapshot,resolved=None):
    return {"kind":"RECONCILIATION","expected_account_version":version,"payload":{
        "effective_at":"2026-10-07T14:00:00+08:00","source":"用户核对券商账户快照","record_id":record,
        "reason":"逐项核对，差异不证明哪方正确","snapshot":snapshot,"resolved_draft_ids":resolved or []}}


def broker_snapshot(cash_balance="100052.00",income="60.00",expenses="8.00"):
    return {"cash_balance":cash_balance,"broker_available":cash_balance,"broker_frozen":"0.00","withdrawable":None,
        "positions":[],"pending_items":[{"record_id":"due","outstanding_amount":"60.00"}],
        "investment_income":income,"investment_expenses":expenses}


def test_reconcile_interest_missing_partial_dividend_and_tax_correction_separately_without_guessed_income(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        submit(client,pending(1,"due"),"due")
        submit(client,settle(2,"paid","40.00","due"),"paid")
        submit(client,cash("TAX",3,"tax","10.00"),"tax")
        old=client.get("/api/account/versions/4").json()
        draft=client.post("/api/account/drafts",json=reconcile(4,"broker-first",broker_snapshot())).json()
        assert draft["status"]=="READY"
        differences=draft["reconciliation_differences"]
        assert next(d for d in differences if d["field"]=="cash_balance")["delta"]=="22.00"
        assert next(d for d in differences if d["field"]=="investment_income")["delta"]=="20.00"
        assert next(d for d in differences if d["field"]=="investment_expenses")["delta"]=="-2.00"
        assert client.get("/api/account").json()["cash_balance"]=="100030.00"
        assert client.get("/api/account").json()["state"]=="RECONCILE_REQUIRED"
        submit(client,cash("INTEREST",4,"missed-interest","20.00"),"interest")
        submit(client,correct(5,"tax","8.00","tax-correct"),"tax-correct")
        final=submit(client,reconcile(6,"broker-final",broker_snapshot(),[draft["draft_id"]]),"reconciled").json()
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="100052.00"
        assert account["investment_income"]=="60.00"
        assert account["investment_expenses"]=="8.00"
        assert account["pending_income"]=="60.00"
        assert account["broker_available"]=="100052.00"
        assert account["reconciliation"]["unresolved"]==[]
        assert account["state"]=="CONFIRMED_AS_OF"
        assert client.get("/api/account/drafts/"+draft["draft_id"]).json()["status"]=="RESOLVED"
        assert client.get("/api/account/versions/4").json()==old
        assert client.get("/api/account/receipts/"+final["receipt_id"]).json()==final
        replay=client.get("/api/account/replay").json()
        assert replay["cash_balance"]=="100052.00"
        assert replay["pending_items"]==account["pending_items"]


def test_quantity_difference_stays_unconfirmed_until_explicit_snapshot_then_unknown_sellable_blocks_reduction(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        submit(client,trade(1,"buy","BUY","10.00","2026-10-07T12:00:00+08:00"),"buy")
        snapshot=broker_snapshot("99000.00","0.00","0.00")
        snapshot.update(positions=[{"instrument":"SSE:600000","quantity":"120","sellable_quantity":None}],pending_items=[])
        command=reconcile(2,"qty-diff",snapshot)
        draft=client.post("/api/account/drafts",json=command).json()
        assert client.get("/api/account").json()["positions"][0]["quantity"]=="100"
        assert client.get("/api/account/drafts/"+draft["draft_id"]).json()["reconciliation_differences"]==draft["reconciliation_differences"]
        mismatch=next(d for d in draft["reconciliation_differences"] if d["field"]=="quantity")
        assert (mismatch["mirror"],mismatch["broker"],mismatch["status"])==("100","120","MISMATCH")
        client.post("/api/account/confirm",json={"draft_id":draft["draft_id"],"idempotency_key":"qty-confirm"}).raise_for_status()
        account=client.get("/api/account").json()
        assert account["positions"][0]["quantity"]=="120"
        assert account["positions"][0]["sellable_quantity"] is None
        assert account["positions"][0]["acquisition_cost"] is None
        assert account.get("investment_income","0.00")=="0.00"
        assert account["reconciliation"]["cash_alignment_delta"]=="5.00"
        assert account["reconciliation"]["historical_cash_classification"]=="UNEXPLAINED_ALIGNMENT"
        assert client.get("/api/today").json()["account"]["state"]==account["state"]=="RECONCILE_REQUIRED"
        check={"purpose":"REDUCTION","required_as_of":"2026-10-07T14:00:00+08:00"}
        use=client.post("/api/account/use-check",json=check).json()
        assert use["state"]=="RECONCILE_REQUIRED" and not use["allowed"]
        assert use["executable_quantity"] is None
        assert client.post("/api/account/use-check",json={**check,"purpose":"MARKET_OBSERVATION"}).json()["allowed"]
        assert client.get("/api/account/replay").json()["reconciliation"]==account["reconciliation"]


def test_v3_csv_supports_real_replacement_reconciliation_and_scoped_declaration_atomically(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        receipt=submit(client,cash("INTEREST",1,"interest","10.00"),"interest").json()
        replacement=cash("INTEREST",2,"interest","20.00")["payload"]
        snapshot=broker_snapshot("100020.00","20.00","0.00")
        snapshot["pending_items"]=[]
        rows=[{"kind":"CORRECTION","record_id":"csv-correction","target_event_id":receipt["event_ids"][0],"reason":"利息凭证为20元",
               "replacement_kind":"INTEREST","replacement_payload":json.dumps(replacement)},
              {"kind":"RECONCILIATION","record_id":"csv-reconcile","reason":"逐项核对","snapshot":json.dumps(snapshot),"resolved_draft_ids":"[]"},
              {"kind":"ACCOUNT_DECLARATION","record_id":"csv-declare","scope":json.dumps(["TRADES","ORDERS","CASH","EQUITY"]),"changes":"NONE","basis":"本次券商核对无其他变化"}]
        for row in rows:row["effective_at"]="2026-10-07T14:00:00+08:00"
        draft=upload(client,rows,2,template_version="ROLL-CSV-3").json()
        assert draft["status"]=="READY",draft
        final=confirm(client,draft,"v3").json()
        assert final["account_version"]==3 and len(final["event_ids"])==3
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="100020.00" and account["investment_income"]=="20.00"
        assert account["corrections"][-1]["receipt_id"]==final["receipt_id"]
        assert account["declarations"][-1]["receipt_id"]==final["receipt_id"]
        assert account["reconciliation"]["receipt_id"]==final["receipt_id"]
        assert client.post("/api/account/use-check",json={"purpose":"NEW_RISK","required_as_of":"2026-10-07T14:00:00+08:00"}).json()["allowed"]
        assert client.get("/api/account/csv/files/"+draft["file"]["sha256"]).content
        old_row={"kind":"ACCOUNT_DECLARATION","record_id":"old-v2-kind","basis":"旧格式不能改变含义"}
        assert upload(client,[old_row],3,template_version="ROLL-CSV-2").json()["status"]=="QUARANTINED"


def test_append_corrections_cover_partial_settlement_paid_rights_fees_and_declarations(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        submit(client,pending(1,"due"),"due")
        paid=settle(2,"paid","60.00","due")
        r=submit(client,paid,"paid").json()
        paid["payload"]["amount"]="40.00"
        submit(client,correction(3,"fix-paid",r["event_ids"][0],{"kind":"SETTLEMENT","payload":paid["payload"]}),"fix-paid").raise_for_status()
        account=client.get("/api/account").json()
        assert account["investment_income"]=="40.00" and account["pending_income"]=="60.00"
        right={"kind":"RIGHTS_SUBSCRIPTION","expected_account_version":4,"payload":{
            "effective_at":"2026-10-07T12:00:00+08:00","source":"个人实际配股凭证","record_id":"rights","instrument":"SSE:600000",
            "quantity":"100","amount":"501.00","fee_amount":"1.00","basis":"本金与费用分拆已核对","broker_available_after":None}}
        r=submit(client,right,"rights").json()
        right["payload"].update(amount="601.00",fee_amount="1.00")
        submit(client,correction(5,"fix-rights",r["event_ids"][0],{"kind":"RIGHTS_SUBSCRIPTION","payload":right["payload"]}),"fix-rights").raise_for_status()
        assert client.get("/api/account").json()["positions"][0]["acquisition_cost"]=="601.00"
        declare=declaration(6,["CASH"],changes="UNRECORDED")
        r=submit(client,declare,"declare").json()
        declare["payload"]["changes"]="NONE"
        result=submit(client,correction(7,"fix-declare",r["event_ids"][0],{"kind":"ACCOUNT_DECLARATION","payload":declare["payload"]}),"fix-declare")
        assert result.status_code==200,result.json()
        account=client.get("/api/account").json()
        assert account["declarations"][-1]["changes"]=="NONE"
        assert account["effective_at"]=="2026-10-07T12:00:00+08:00"
        assert client.get("/api/account/replay").json()["cash_balance"]==account["cash_balance"]


def test_correction_concurrency_retries_and_original_known_cutoff_have_one_atomic_winner(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        original=submit(client,cash("INTEREST",1,"interest","10.00"),"interest").json()
        material=[]
        for amount in ["20.00","30.00"]:
            replacement=cash("INTEREST",2,"interest",amount)
            command=correction(2,"correct-"+amount,original["event_ids"][0],{"kind":"INTEREST","payload":replacement["payload"]})
            material.append(client.post("/api/account/drafts",json=command).json())
        confirmations=[{"draft_id":d["draft_id"],"idempotency_key":"key-"+d["draft_id"]} for d in material]
        with ThreadPoolExecutor(2) as pool:
            responses=list(pool.map(lambda c:client.post("/api/account/confirm",json=c),confirmations))
        assert sorted(r.status_code for r in responses)==[200,409]
        winner=next(i for i,r in enumerate(responses) if r.status_code==200)
        receipt=responses[winner].json()
        assert client.post("/api/account/confirm",json=confirmations[winner]).json()==receipt
        assert client.get("/api/account").json()["version"]==3
        assert len(client.get("/api/account/events").json())==4
        assert client.get("/api/account/as-of",params={"known_by":original["confirmed_at"]}).json()["account"]["cash_balance"]=="100010.00"
        bad=correction(3,"invalid-time",receipt["event_ids"][0],{"kind":"INTEREST","payload":{**cash("INTEREST",3,"interest","40.00")["payload"],"effective_at":"2026-10-06T09:00:00+08:00"}})
        raw=client.post("/api/account/drafts",json=bad).json()
        assert raw["status"]=="QUARANTINED"
        assert raw["command"]["payload"]==bad["payload"]
        assert client.get("/api/account").json()["version"]==3


def test_changed_declaration_and_unknown_broker_facts_remain_visible_without_blocking_market(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        submit(client,declaration(1,["ORDERS"],changes="EXTERNAL_ORDER_PENDING"),"external").raise_for_status()
        assert client.get("/api/account").json()["state"]==client.get("/api/today").json()["account"]["state"]=="UPDATE_PENDING"
        request={"purpose":"NEW_RISK","required_as_of":"2026-10-07T14:00:00+08:00"}
        assert client.post("/api/account/use-check",json=request).json()["state"]=="UPDATE_PENDING"
        assert client.post("/api/account/use-check",json={**request,"purpose":"MARKET_OBSERVATION"}).json()["allowed"]
        unknown=broker_snapshot(None,None,None)
        unknown.update(broker_available=None,broker_frozen=None,pending_items=[])
        result=submit(client,reconcile(2,"unknown",unknown),"unknown")
        assert result.status_code==200
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="100000.00" and account["broker_available"] is None
        assert account["reconciliation"]["unresolved"]
        # Outstanding external-order declaration remains an explicit pending fact.
        assert account["state"]=="UPDATE_PENDING"
        assert client.post("/api/account/use-check",json=request).json()["executable_quantity"] is None


def test_cash_only_gap_does_not_close_independently_eligible_reduction_fact_path(tmp_path):
    from test_account import baseline
    with TestClient(create_app(tmp_path)) as client:
        base=baseline()
        base["payload"]["positions"][0]["sellable_quantity"]="100"
        submit(client,base,"baseline").raise_for_status()
        submit(client,declaration(1,["TRADES","ORDERS","EQUITY"]),"reduction-scope").raise_for_status()
        unknown=cash("INTEREST",2,"unknown-interest",None)
        draft=client.post("/api/account/drafts",json=unknown).json()
        assert draft["status"]=="QUARANTINED"
        request={"purpose":"REDUCTION","required_as_of":"2026-10-07T14:00:00+08:00"}
        facts=client.post("/api/account/use-check",json=request).json()
        assert facts["state"]=="RECONCILE_REQUIRED"
        assert facts["allowed"] is True
        assert facts["required_scope"]==["TRADES","ORDERS","EQUITY"]
        assert facts["fact_scope_state"]=="CONFIRMED_AS_OF"
        assert facts["executable_quantity"] is None
        assert facts["known_positions"][0]["sellable_quantity"]=="100"
        newrisk=client.post("/api/account/use-check",json={**request,"purpose":"NEW_RISK"}).json()
        assert not newrisk["allowed"]
        bad=fill(2,"unrecorded-fill")
        bad["payload"]["quantity"]="未知"
        assert client.post("/api/account/drafts",json=bad).json()["status"]=="QUARANTINED"
        facts=client.post("/api/account/use-check",json=request).json()
        assert not facts["allowed"] and facts["fact_scope_state"]=="RECONCILE_REQUIRED"


def test_unknown_fees_do_not_block_verified_sellable_facts_but_unknown_sellable_does(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        submit(client,fill(1,"provisional",fee_status="PROVISIONAL"),"provisional").raise_for_status()
        snapshot=broker_snapshot("96990.00","0.00","0.00")
        snapshot.update(positions=[{"instrument":"SSE:600000","quantity":"300","sellable_quantity":"300"}],pending_items=[])
        submit(client,reconcile(2,"verified-sellable",snapshot),"verified").raise_for_status()
        submit(client,declaration(3,["TRADES","ORDERS","EQUITY"]),"scope").raise_for_status()
        request={"purpose":"REDUCTION","required_as_of":"2026-10-07T14:00:00+08:00"}
        facts=client.post("/api/account/use-check",json=request).json()
        assert facts["state"]=="RECONCILE_REQUIRED" and facts["allowed"]
        assert facts["executable_quantity"] is None
        invalid={**snapshot,"positions":[{"instrument":"SSE:600000","quantity":"unknown","sellable_quantity":"300"}]}
        raw=client.post("/api/account/drafts",json=reconcile(4,"unresolved-quantity",invalid)).json()
        assert raw["status"]=="QUARANTINED"
        assert not client.post("/api/account/use-check",json=request).json()["allowed"]
        snapshot["positions"][0]["sellable_quantity"]=None
        submit(client,reconcile(4,"unknown-sellable",snapshot),"unknown").raise_for_status()
        facts=client.post("/api/account/use-check",json=request).json()
        assert not facts["allowed"]
        assert facts["fact_scope_state"]=="RECONCILE_REQUIRED"


def test_replacing_actual_fill_fee_rebuilds_partial_sale_allocations_and_keeps_original_resolution(tmp_path):
    from test_fills import fee_adjustment
    with TestClient(create_app(tmp_path)) as client:
        establish(client)
        buy=trade(1,"buy","BUY","10.00","2026-10-07T11:00:00+08:00")
        buy["payload"]["fee"]={"status":"PROVISIONAL","amount":None,"reserve_amount":"10.00","basis":"有据保守费用预留"}
        submit(client,buy,"buy").raise_for_status()
        sell=trade(2,"sale","SELL","12.00","2026-10-07T13:00:00+08:00")
        sell["payload"]["quantity"]="50"
        submit(client,sell,"sale").raise_for_status()
        fee=fee_adjustment(3,amount="6.00",target="buy")
        receipt=submit(client,fee,"actual-fee").json()
        old=client.get("/api/account/versions/4").json()
        assert old["cash_balance"]=="99589.00" and old["realized_gain"]=="92.00"
        fee["payload"]["actual_fee_amount"]="2.00"
        submit(client,correction(4,"correct-actual-fee",receipt["event_ids"][0],{"kind":"FEE_ADJUSTMENT","payload":fee["payload"]}),"fee-correction").raise_for_status()
        account=client.get("/api/account").json()
        assert account["cash_balance"]=="99593.00" and account["realized_gain"]=="94.00"
        assert account["positions"][0]["acquisition_cost"]=="501.00"
        assert account["fee_resolutions"]["buy"]["actual_fee_amount"]=="2.00"
        original=next(e for e in client.get("/api/account/events").json() if e["event_id"]==receipt["event_ids"][0])
        assert original["payload"]["actual_fee_amount"]=="6.00"
        assert client.get("/api/account/versions/4").json()==old
        assert client.get("/api/account/replay").json()["realized_gain"]=="94.00"


def test_permission_fact_does_not_move_baseline_frozen_and_withdrawable_snapshot_time(tmp_path):
    from test_account import baseline
    with TestClient(create_app(tmp_path)) as client:
        base=baseline()
        base["payload"].update(positions=[],withdrawable="80000.00")
        submit(client,base,"baseline").raise_for_status()
        submit(client,{"kind":"PERMISSIONS","expected_account_version":1,"payload":{"effective_at":"2026-10-07T12:00:00+08:00","source":"仅核对权限","permission_profile":[]}},"permissions").raise_for_status()
        submit(client,trade(2,"buy","BUY","10.00","2026-10-07T13:00:00+08:00"),"buy").raise_for_status()
        account=client.get("/api/account").json()
        assert account["broker_frozen_as_of"]=="2026-10-07T10:00:00+08:00"
        assert account["withdrawable_as_of"]=="2026-10-07T10:00:00+08:00"
        assert account["withdrawable"]=="80000.00"
        assert account["broker_available"] is None and account["broker_available_as_of"] is None
        assert client.get("/api/account/replay").json()["broker_frozen_as_of"]==account["broker_frozen_as_of"]
