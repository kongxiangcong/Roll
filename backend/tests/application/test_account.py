from fastapi.testclient import TestClient
from roll.app import create_app


def baseline():
    return {
        "kind": "BASELINE", "expected_account_version": 0,
        "payload": {
            "effective_at": "2026-10-07T10:00:00+08:00", "source": "用户核对券商快照",
            "cash_balance": "100000.10", "broker_available": "90000.10", "broker_frozen": "10000.00",
            "withdrawable": None,
            "positions": [{"instrument": "SSE:600000", "quantity": "300", "sellable_quantity": None,
                           "reference_cost": "10.12345678"}],
            "permission_profile": [
                {"market": "SSE", "board": "MAIN", "status": "OPEN", "basis": "券商已开通"},
                {"market": "SSE", "board": "STAR", "status": "NOT_OPEN", "basis": "券商未开通"},
                {"market": "SZSE", "board": "CHINEXT", "status": "UNKNOWN", "basis": "未核对"},
            ],
        },
    }


def test_initial_position_is_only_published_after_explicit_confirmation(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        draft = client.post("/api/account/drafts", json=baseline())
        assert draft.status_code == 201
        draft = draft.json()
        assert client.get("/api/account").json()["version"] == 0
        assert draft["preview"]["cash_balance"]["after"] == "100000.10"
        receipt = client.post("/api/account/confirm", json={"draft_id": draft["draft_id"], "idempotency_key": "baseline-1"})
        assert receipt.status_code == 200
        receipt = receipt.json()
        account = client.get("/api/account").json()
        assert account["version"] == 1
        assert account["cash_balance"] == "100000.10"
        assert account["broker_available"] == "90000.10"
        assert account["broker_frozen"] == "10000.00"
        position = account["positions"][0]
        assert position["quantity"] == "300"
        assert position["sellable_quantity"] is None
        assert position["reference_cost"] == "10.12345678"
        assert position["buy_time"] is None and position["historical_fees"] is None
        assert account["historical_return"] is None
        assert account["confirmed_at"] == receipt["confirmed_at"]
        assert client.get(f"/api/account/receipts/{receipt['receipt_id']}").json() == receipt
        events = client.get("/api/account/events").json()
        assert [event["event_type"] for event in events] == ["INITIAL_CASH", "INITIAL_POSITION", "PERMISSION_CONFIRMATION"]
        assert events[1]["effective_at"] == "2026-10-07T10:00:00+08:00"
        assert events[1]["source"] == "用户核对券商快照"
        today = client.get("/api/today").json()
        assert today["formal_judgment"] == "DISABLED"
        assert "SSE:600000 可卖数量未知" in today["pending_items"]
import copy
from concurrent.futures import ThreadPoolExecutor

import pytest


def submit(client, command, key):
    draft = client.post("/api/account/drafts", json=command)
    assert draft.status_code == 201, draft.text
    return client.post("/api/account/confirm", json={"draft_id": draft.json()["draft_id"], "idempotency_key": key})


def permission_change(version, status="NOT_OPEN"):
    return {"kind": "PERMISSIONS", "expected_account_version": version,
            "payload": {"effective_at": "2026-10-07T11:00:00+08:00", "source": "再次核对券商权限",
                        "permission_profile": [{"market": "SSE", "board": "MAIN", "status": status, "basis": "券商权限页面"}]}}


def test_permission_draft_is_inactive_and_history_retains_three_states(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        first = submit(client, baseline(), "first").json()
        v1 = client.get("/api/account").json()
        assert [p["status"] for p in v1["permission_profile"]] == ["OPEN", "NOT_OPEN", "UNKNOWN"]
        assert all(p["confirmed_at"] == first["confirmed_at"] for p in v1["permission_profile"])
        draft = client.post("/api/account/drafts", json=permission_change(1)).json()
        assert client.get("/api/account").json() == v1
        assert client.post("/api/account/confirm", json={"draft_id": draft["draft_id"], "idempotency_key": "permissions"}).status_code == 200
        assert client.get("/api/account").json()["permission_profile"][0]["status"] == "NOT_OPEN"
        assert client.get("/api/account/versions/1").json() == v1
        assert client.get("/api/account").json()["cash_balance"] == "100000.10"
        assert len(client.get("/api/account/audit").json()) == 2


def test_retry_returns_original_receipt_even_after_later_version_and_rejects_changed_content(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        draft = client.post("/api/account/drafts", json=baseline()).json()
        command = {"draft_id": draft["draft_id"], "idempotency_key": "same-key"}
        original = client.post("/api/account/confirm", json=command).json()
        submit(client, permission_change(1), "second")
        assert client.post("/api/account/confirm", json=command).json() == original
        other = client.post("/api/account/drafts", json=permission_change(2,"OPEN")).json()
        conflict = client.post("/api/account/confirm", json={**command, "draft_id": other["draft_id"]})
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONTENT_CONFLICT"
        assert client.get("/api/account").json()["version"] == 2
        assert len(client.get("/api/account/events").json()) == 4


def test_concurrent_old_pages_cannot_overwrite_or_partially_publish(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        drafts = []
        for amount in ["100000.10", "100001.20"]:
            command = baseline()
            command["payload"]["cash_balance"] = amount
            drafts.append(client.post("/api/account/drafts", json=command).json()["draft_id"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(lambda value: client.post("/api/account/confirm", json={"draft_id": value[1], "idempotency_key": f"page-{value[0]}"}), enumerate(drafts)))
        assert sorted(r.status_code for r in replies) == [200,409]
        conflict = next(r for r in replies if r.status_code == 409).json()["detail"]
        assert conflict["current_account_version"] == 1
        assert conflict["diff"]["cash_balance"]["before"] is None
        assert client.get("/api/account").json()["version"] == 1
        assert len(client.get("/api/account/events").json()) == 3
        assert len(client.get("/api/account/audit").json()) == 1


def test_concurrent_identical_confirmation_publishes_once(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        draft = client.post("/api/account/drafts", json=baseline()).json()
        command = {"draft_id": draft["draft_id"], "idempotency_key": "double-click"}
        with ThreadPoolExecutor(max_workers=4) as pool:
            replies = list(pool.map(lambda _: client.post("/api/account/confirm", json=command), range(4)))
        assert all(r.status_code == 200 for r in replies)
        assert len({r.json()["receipt_id"] for r in replies}) == 1
        assert len(client.get("/api/account/events").json()) == 3


@pytest.mark.parametrize("field,value", [("cash_balance",100000.1),("cash_balance","1.001"),("cash_balance","NaN"),("cash_balance","-1.00"),("broker_available",""),("effective_at","2026-10-07T10:00:00"),("effective_at","2999-01-01T00:00:00+08:00")])
def test_invalid_boundary_input_never_creates_account(tmp_path,field,value):
    with TestClient(create_app(tmp_path)) as client:
        command = baseline()
        command["payload"][field] = value
        assert client.post("/api/account/drafts", json=command).status_code == 422
        assert client.get("/api/account").json()["version"] == 0
        assert client.get("/api/account/events").json() == []


def test_exact_maximum_precision_and_known_zero_are_distinct_from_unknown(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        command = baseline()
        command["payload"]["cash_balance"] = "999999999999999999.99"
        command["payload"]["broker_available"] = "0"
        command["payload"]["positions"][0]["sellable_quantity"] = "0"
        assert submit(client,command,"large").status_code == 200
        account = client.get("/api/account").json()
        assert account["cash_balance"] == "999999999999999999.99"
        assert account["broker_available"] == "0.00"
        assert account["positions"][0]["sellable_quantity"] == "0"
        assert account["withdrawable"] is None


def test_invalid_batch_member_and_baseline_overwrite_are_rejected(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        command = baseline()
        bad = copy.deepcopy(command["payload"]["positions"][0])
        bad.update(instrument="SZSE:000001",sellable_quantity="301")
        command["payload"]["positions"].append(bad)
        assert client.post("/api/account/drafts",json=command).status_code == 422
        assert client.get("/api/account").json()["version"] == 0
        submit(client,baseline(),"baseline")
        command = baseline()
        command["expected_account_version"] = 1
        assert client.post("/api/account/drafts",json=command).status_code == 409


def test_permission_version_conflict_reports_previous_confirmed_change(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        submit(client,baseline(),"baseline")
        stale = client.post("/api/account/drafts",json=permission_change(1,"UNKNOWN")).json()
        submit(client,permission_change(1,"NOT_OPEN"),"revoked")
        response = client.post("/api/account/confirm",json={"draft_id":stale["draft_id"],"idempotency_key":"stale"})
        assert response.status_code == 409
        assert response.json()["detail"]["diff"]["permission_profile"]["after"][0]["status"] == "NOT_OPEN"
        assert client.get("/api/account/versions/1").json()["permission_profile"][0]["status"] == "OPEN"
@pytest.mark.parametrize("malformed",[[],{},True,1])
def test_malformed_permission_state_is_actionable_validation_failure(tmp_path,malformed):
    with TestClient(create_app(tmp_path)) as client:
        command=baseline()
        command["payload"]["permission_profile"][0]["status"]=malformed
        assert client.post("/api/account/drafts",json=command).status_code==422
        assert client.get("/api/account").json()["version"]==0
