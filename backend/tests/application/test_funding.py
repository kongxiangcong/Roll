from fastapi.testclient import TestClient
from roll.app import create_app
from test_account import baseline, submit
import pytest
import copy


def loss_facts(**changes):
    return {"scope_kind": "ACCOUNT", "scope_id": "account-1", "baseline_account_version": 1,
            "origin_at": "2026-10-07T10:00:00+08:00", "as_of": "2026-10-07T11:00:00+08:00",
            "facts_version": "sample-1", "valuation_status": "COMPLETE", "baseline_assets": "100000.00",
            "net_assets": "97000.00", "external_in": "2000.00", "external_out": "1000.00",
            "realized_pnl": "-2000.00", "unrealized_pnl": "-2100.00", "income": "200.00", "fees": "100.00",
            "pending_income_delta": "0.00", "pending_expense_delta": "0.00", **changes}


def funding(version=0, **changes):
    return {"expected_version": version, "idempotency_key": f"funding-{version}",
            "authorization": {"scope_kind": "ACCOUNT", "scope_id": "account-1", "purpose": "本人普通账户",
                              "capital_amount": "100000.00", "total_exposure": "60000.00",
                              "single_exposure": "20000.00", "cash_reserve": "40000.00",
                              "loss_threshold": "5000.00", "effective_at": "2026-10-07T10:00:00+08:00",
                              "basis": "本人确认", "enabled": True, **changes}}


def test_user_confirmation_persists_funding_without_granting_technical_capability(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        submit(client, baseline(), "account")
        before = client.get("/api/funding").json()
        assert before["version"] == 0 and before["state"] == "UNCONFIRMED"
        response = client.post("/api/funding/confirm", json=funding())
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["version"] == 1 and result["capital_amount"] == "100000.00"
        assert result["loss_status"] == "PENDING_FACTS" and result["remaining_loss_allowance"] is None
        assert client.get("/api/capabilities").json()["state"] == "UNGRANTED"
        assert client.get("/api/account").json()["version"] == 1
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/funding").json() == result
        assert client.get("/api/funding/versions/1").json() == result


@pytest.mark.parametrize("action", ["BUY", "ADD", "HOLD", "REDUCE", "EXIT", "WAIT"])
def test_no_formal_judgment_or_probability_from_model_confidence_or_mode(action, tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        submit(client, baseline(), "account")
        client.post("/api/funding/confirm", json=funding())
        before = client.get("/api/account/events").json()
        response = client.post("/api/formal/evaluate", json={"action": action, "mode": "FORMAL", "llm_confidence": "0.99"})
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "TECHNICAL_CAPABILITY_UNGRANTED"
        response = client.post("/api/formal/probability", json={"probability": "0.90", "origin": "LLM"})
        assert response.status_code == 403
        assert client.get("/api/account/events").json() == before


def test_loss_formula_cashflow_and_components_are_manually_reconcilable_without_actual_mutation(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLL_ENV", "test")
    with TestClient(create_app(tmp_path)) as client:
        submit(client, baseline(), "account")
        client.post("/api/funding/confirm", json=funding())
        account = client.get("/api/account").json()
        result = client.post("/api/testing/funding-loss-samples", json={"series_id": "cashflow", "facts": loss_facts()})
        assert result.status_code == 200, result.text
        result = result.json()
        assert result["namespace"] == "ACCOUNT_CONDITIONAL" and result["input_authority"] == "UNTRUSTED_SAMPLE"
        assert result["pnl"] == "-4000.00" and result["loss"] == "4000.00"
        assert result["remaining_loss_allowance"] == "1000.00" and result["triggered"] is False
        assert client.get("/api/account").json() == account
        assert client.get("/api/funding").json()["loss_status"] == "PENDING_FACTS"


def test_funding_versions_conflicts_pause_and_expansion_do_not_reset_origin(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        submit(client, baseline(), "account")
        first = client.post("/api/funding/confirm", json=funding()).json()
        paused = client.post("/api/funding/confirm", json=funding(1, pause=True)).json()
        assert paused["state"] == "PAUSED"
        assert client.post("/api/funding/confirm", json=funding()).json() == first
        changed = copy.deepcopy(funding()); changed["authorization"]["purpose"] = "不同内容"
        assert client.post("/api/funding/confirm", json=changed).status_code == 409
        stale = funding(0); stale["idempotency_key"] = "new-old"
        assert client.post("/api/funding/confirm", json=stale).json()["detail"]["code"] == "FUNDING_VERSION_CONFLICT"
    with TestClient(create_app(tmp_path)) as client:
        expanded = client.post("/api/funding/confirm", json=funding(2, capital_amount="200000.00", loss_threshold="10000.00")).json()
        assert expanded["state"] == "PAUSED" and expanded["loss_origin_at"] == first["loss_origin_at"]
        assert expanded["baseline_account_version"] == 1
        assert client.get("/api/funding/versions/1").json() == first
        assert client.post("/api/funding/confirm", json=funding(3, scope_id="erase-history")).status_code == 409
        revoked = client.post("/api/funding/confirm", json=funding(3, enabled=False)).json()
        assert revoked["state"] == "REVOKED"


def test_threshold_equality_stays_paused_across_day_restart_rebound_and_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLL_ENV", "test")
    with TestClient(create_app(tmp_path)) as client:
        initial = baseline(); initial["payload"]["effective_at"] = "2026-10-05T10:00:00+08:00"
        submit(client, initial, "account")
        client.post("/api/funding/confirm", json=funding(effective_at="2026-10-05T10:00:00+08:00"))
        first = client.post("/api/testing/funding-loss-samples", json={"series_id": "sticky", "facts": loss_facts(
            net_assets="96000.00", unrealized_pnl="-3100.00", origin_at="2026-10-05T10:00:00+08:00", as_of="2026-10-06T12:00:00+08:00")}).json()
        assert first["triggered"] is True and first["remaining_loss_allowance"] == "0.00"
    with TestClient(create_app(tmp_path)) as client:
        client.post("/api/funding/confirm", json=funding(1, capital_amount="200000.00", loss_threshold="10000.00"))
        rebound = loss_facts(net_assets="102000.00", unrealized_pnl="2900.00", facts_version="sample-2", origin_at="2026-10-05T10:00:00+08:00", as_of="2026-10-07T12:00:00+08:00")
        result = client.post("/api/testing/funding-loss-samples", json={"series_id": "sticky", "facts": rebound}).json()
        assert result["pnl"] == "1000.00" and result["loss"] == "0.00"
        assert result["peak_loss"] == "5000.00" and result["triggered"] is True and result["status"] == "PAUSED"
        assert len(client.get("/api/testing/funding-loss-samples/sticky").json()) == 2
        assert client.get("/api/funding").json()["loss_status"] == "PENDING_FACTS"


@pytest.mark.parametrize("changes,expected", [
    ({"net_assets": "95999.99", "unrealized_pnl": "-3100.01"}, {"pnl": "-5000.01", "remaining_loss_allowance": "0.00", "triggered": True}),
    ({"net_assets": "96000.01", "unrealized_pnl": "-3099.99"}, {"pnl": "-4999.99", "remaining_loss_allowance": "0.01", "triggered": False}),
    ({"pending_income_delta": "100.00", "pending_expense_delta": "50.00", "net_assets": "97050.00"}, {"pnl": "-3950.00", "remaining_loss_allowance": "1050.00"}),
    ({"income": "300.00", "pending_income_delta": "-100.00", "net_assets": "97000.00"}, {"pnl": "-4000.00"}),
    ({"valuation_status": "STALE"}, {"status": "RESTRICTED", "pnl": None, "remaining_loss_allowance": None}),
    ({"fees": None}, {"status": "RESTRICTED", "pnl": None, "remaining_loss_allowance": None}),
    ({"net_assets": "100000.00"}, {"status": "RESTRICTED", "remaining_loss_allowance": None}),
    ({"net_assets": "99995.00", "external_in": "0.00", "external_out": "0.00", "realized_pnl": "0.00", "unrealized_pnl": "0.00", "income": "0.00", "fees": "5.00"}, {"pnl": "-5.00", "loss": "5.00", "remaining_loss_allowance": "4995.00"}),
])
def test_frozen_formula_threshold_pending_settlement_and_missing_inputs(changes, expected, tmp_path, monkeypatch):
    monkeypatch.setenv("ROLL_ENV", "test")
    with TestClient(create_app(tmp_path)) as client:
        submit(client, baseline(), "account")
        client.post("/api/funding/confirm", json=funding())
        result = client.post("/api/testing/funding-loss-samples", json={"series_id": "fixed", "facts": loss_facts(**changes)}).json()
        for key, value in expected.items():
            assert result[key] == value


def test_sample_route_is_not_a_production_fact_writer(tmp_path, monkeypatch):
    monkeypatch.delenv("ROLL_ENV", raising=False)
    with TestClient(create_app(tmp_path)) as client:
        assert client.post("/api/testing/funding-loss-samples", json={"series_id": "spoof", "facts": loss_facts()}).status_code == 404


@pytest.mark.parametrize("changes", [
    {"capital_amount": "0"}, {"capital_amount": 100000.0}, {"capital_amount": "NaN"},
    {"capital_amount": "100000.001"}, {"single_exposure": "60000.01"},
    {"cash_reserve": "40000.01"}, {"loss_threshold": "0"}, {"basis": "   "},
    {"scope_kind": "SHADOW"}, {"effective_at": "2026-10-07T10:00:00"},
])
def test_invalid_funding_boundaries_never_publish(changes, tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        submit(client, baseline(), "account")
        assert client.post("/api/funding/confirm", json=funding(**changes)).status_code == 422
        assert client.get("/api/funding").json()["version"] == 0


def test_parallel_same_confirmation_and_stale_versions_are_atomic(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    with TestClient(create_app(tmp_path)) as client:
        submit(client, baseline(), "account")
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: client.post("/api/funding/confirm", json=funding()), range(4)))
        assert all(result.status_code == 200 for result in results)
        assert len({result.json()["receipt_id"] for result in results}) == 1
        left, right = funding(1, purpose="左页面"), funding(1, purpose="右页面")
        right["idempotency_key"] = "right"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda value: client.post("/api/funding/confirm", json=value), [left, right]))
        assert sorted(result.status_code for result in results) == [200, 409]
        assert client.get("/api/funding").json()["version"] == 2


@pytest.mark.parametrize("change", [{"scope_kind":"TRIAL_ACTUAL"}, {"scope_id":"other"}, {"baseline_account_version":2}, {"origin_at":"2026-10-06T10:00:00+08:00"}, {"namespace":"SHADOW"}, {"fees":10.5}])
def test_scope_shadow_and_precision_cannot_replace_authorized_loss_facts(change, tmp_path, monkeypatch):
    monkeypatch.setenv("ROLL_ENV", "test")
    with TestClient(create_app(tmp_path)) as client:
        submit(client, baseline(), "account")
        client.post("/api/funding/confirm", json=funding())
        response = client.post("/api/testing/funding-loss-samples", json={"series_id":"wrong", "facts":loss_facts(**change)})
        assert response.status_code == 422
        assert client.get("/api/testing/funding-loss-samples/wrong").json() == []


def test_shrinking_threshold_uses_old_peak_and_decimal_cent_is_exact(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLL_ENV", "test")
    with TestClient(create_app(tmp_path)) as client:
        submit(client, baseline(), "account")
        client.post("/api/funding/confirm", json=funding())
        client.post("/api/testing/funding-loss-samples", json={"series_id":"shrink", "facts":loss_facts()})
        client.post("/api/funding/confirm", json=funding(1, loss_threshold="3000.00", total_exposure="30000.00", single_exposure="10000.00"))
        result = client.post("/api/testing/funding-loss-samples", json={"series_id":"shrink", "facts":loss_facts(facts_version="rebound", net_assets="102000.00", unrealized_pnl="2900.00")}).json()
        assert result["triggered"] is True and result["peak_loss"] == "4000.00"
        assert result["remaining_loss_allowance"] == "0.00"
        assert client.get("/api/funding").json()["total_exposure"] == "30000.00"
        result = client.post("/api/testing/funding-loss-samples", json={"series_id":"large", "facts":loss_facts(
            baseline_assets="999999999999999999.99", net_assets="999999999999999999.98", external_in="0.00", external_out="0.00",
            realized_pnl="-0.01", unrealized_pnl="0.00", income="0.00", fees="0.00")}).json()
        assert result["pnl"] == "-0.01" and result["remaining_loss_allowance"] == "2999.99"


def test_missing_baseline_does_not_reset_known_sample_baseline_or_pause(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLL_ENV", "test")
    with TestClient(create_app(tmp_path)) as client:
        submit(client, baseline(), "account")
        client.post("/api/funding/confirm", json=funding())
        client.post("/api/testing/funding-loss-samples", json={"series_id":"missing", "facts":loss_facts(net_assets="96000.00",unrealized_pnl="-3100.00")})
        result = client.post("/api/testing/funding-loss-samples", json={"series_id":"missing", "facts":loss_facts(facts_version="missing-2",baseline_assets=None)})
        assert result.status_code == 200, result.text
        assert result.json()["status"] == "RESTRICTED" and result.json()["triggered"] is True
        assert result.json()["remaining_loss_allowance"] is None
        assert result.json()["baseline_assets"] == "100000.00"
