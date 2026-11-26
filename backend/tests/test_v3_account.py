import argparse
import io
import json
from pathlib import Path

from roll.v3.account_cli import register_account_commands


BASELINE_AT = "2025-07-21T15:00:00+08:00"
FILL_AT = "2025-07-22T10:00:00+08:00"
AFTER_FILL = "2025-07-22T16:00:00+08:00"
CORRECTION_AT = "2025-07-23T16:00:00+08:00"

BASELINE = {
    "cash": "3000",
    "available_cash": "2500",
    "effective_at": BASELINE_AT,
    "known_at": BASELINE_AT,
    "lots": [
        {"lot_id": "opening-1", "symbol": "600362.SH", "quantity": 300, "known_sellable": 200, "cost": "6000"}
    ],
}


def account(tmp_path: Path, monkeypatch, *args, payload=None):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    parser = argparse.ArgumentParser()
    register_account_commands(parser.add_subparsers(required=True))
    params = parser.parse_args(["account", *args])
    return params.handler(params, tmp_path)


def test_account_baseline_distinguishes_total_cash_available_cash_and_unknown_buy_date(tmp_path, monkeypatch):
    account(tmp_path, monkeypatch, "init", payload=BASELINE)
    snapshot = account(tmp_path, monkeypatch, "show", "--as-of", BASELINE_AT)
    assert snapshot["cash"] == "3000"
    assert snapshot["available_cash"] == "2500"
    assert snapshot["known_sellable"] == {"600362.SH": 200}
    assert snapshot["lots"][0]["acquired_on"] is None
    assert snapshot["lots"][0]["cost"] == "6000"


FILL = {
    "event_id": "broker-22",
    "symbol": "600362.SH",
    "side": "BUY",
    "quantity": 100,
    "price": "9.10",
    "fee": "1",
    "effective_at": FILL_AT,
    "known_at": FILL_AT,
}


def test_recording_the_same_actual_fill_twice_preserves_cash_and_lots(tmp_path, monkeypatch):
    account(tmp_path, monkeypatch, "init", payload=BASELINE)
    first = account(tmp_path, monkeypatch, "fill", payload=FILL)
    duplicate = account(tmp_path, monkeypatch, "fill", payload=FILL)
    snapshot = account(tmp_path, monkeypatch, "show", "--as-of", AFTER_FILL)

    assert first == duplicate
    assert snapshot["cash"] == "2089"
    assert snapshot["available_cash"] == "1589"
    assert snapshot["known_sellable"] == {"600362.SH": 200}
    assert [(lot["lot_id"], lot["quantity"], lot["cost"]) for lot in snapshot["lots"]] == [
        ("opening-1", 300, "6000"),
        ("broker-22", 100, "911"),
    ]


def test_late_fill_correction_reprojects_the_past_without_changing_the_frozen_snapshot(tmp_path, monkeypatch):
    account(tmp_path, monkeypatch, "init", payload=BASELINE)
    account(tmp_path, monkeypatch, "fill", payload=FILL)
    old = account(tmp_path, monkeypatch, "show", "--as-of", AFTER_FILL)
    account(tmp_path, monkeypatch, "correct", payload={
        "event_id": "broker-22-amended",
        "target_event_id": "broker-22",
        "known_at": CORRECTION_AT,
        "replacement": {"quantity": 200},
    })

    assert account(tmp_path, monkeypatch, "show", "--snapshot-id", old["snapshot_id"]) == old
    assert account(tmp_path, monkeypatch, "show", "--as-of", AFTER_FILL) == old

    corrected = account(tmp_path, monkeypatch, "show", "--as-of", AFTER_FILL, "--known-at", CORRECTION_AT)
    assert corrected["snapshot_id"] != old["snapshot_id"]
    assert corrected["through_event_id"] == "broker-22-amended"
    assert corrected["cash"] == "1179"
    assert corrected["available_cash"] == "679"
    assert [lot["quantity"] for lot in corrected["lots"]] == [300, 200]
    assert corrected["known_sellable"] == {"600362.SH": 200}


def test_snapshot_uses_the_budget_effective_and_known_at_the_decision(tmp_path, monkeypatch):
    account(tmp_path, monkeypatch, "init", payload=BASELINE)
    budget = {
        "budget_id": "july",
        "effective_at": BASELINE_AT,
        "known_at": BASELINE_AT,
        "cash_reserve": "600",
        "funds_needed_at": "2025-07-28T09:00:00+08:00",
        "max_total_exposure": "0.8",
        "max_symbol_exposure": "0.2",
        "max_industry_exposure": "0.4",
        "pause_conditions": ["new_funding_required"],
    }
    original = account(tmp_path, monkeypatch, "budget", payload=budget)
    newer_budget = {
        **budget,
        "budget_id": "july-2",
        "effective_at": AFTER_FILL,
        "known_at": CORRECTION_AT,
        "cash_reserve": "800",
        "expires_at": "2025-07-24T16:00:00+08:00",
    }
    account(tmp_path, monkeypatch, "budget", payload=newer_budget)
    assert original == {"book_id": "real", "budget_id": "july"}

    old = account(tmp_path, monkeypatch, "show", "--as-of", AFTER_FILL)
    new = account(tmp_path, monkeypatch, "show", "--as-of", CORRECTION_AT)
    assert old["risk_budget"] == {
        **budget,
        "effective_at": "2025-07-21T07:00:00.000000+00:00",
        "known_at": "2025-07-21T07:00:00.000000+00:00",
        "funds_needed_at": "2025-07-28T01:00:00.000000+00:00",
        "expires_at": None,
    }
    assert new["risk_budget"]["cash_reserve"] == "800"
    expired = account(tmp_path, monkeypatch, "show", "--as-of", newer_budget["expires_at"])
    assert expired["risk_budget"] is None


def test_account_books_from_the_same_lots_evolve_independently(tmp_path, monkeypatch):
    for book_id in ("real", "backtest", "shadow"):
        account(tmp_path, monkeypatch, "init", "--book-id", book_id, payload=BASELINE)

    account(tmp_path, monkeypatch, "cash", "--book-id", "backtest", payload={
        "event_id": "cash-dividend",
        "delta": "300",
        "effective_at": FILL_AT,
        "known_at": FILL_AT,
    })
    account(tmp_path, monkeypatch, "shares", "--book-id", "backtest", payload={
        "event_id": "bonus-listing",
        "lot": {"lot_id": "bonus-1", "symbol": "600362.SH", "quantity": 300, "sellable_on": "2025-07-22"},
        "effective_at": FILL_AT,
        "known_at": FILL_AT,
    })
    sale = {**FILL, "side": "SELL", "broker_available_after": "3300", "plan_id": "plan-22"}
    account(tmp_path, monkeypatch, "fill", "--book-id", "shadow", payload=sale)

    real = account(tmp_path, monkeypatch, "show", "--as-of", AFTER_FILL)
    backtest = account(tmp_path, monkeypatch, "show", "--book-id", "backtest", "--as-of", AFTER_FILL)
    shadow = account(tmp_path, monkeypatch, "show", "--book-id", "shadow", "--as-of", AFTER_FILL)
    assert (real["cash"], real["available_cash"], real["lots"][0]["quantity"]) == ("3000", "2500", 300)
    assert (backtest["cash"], backtest["available_cash"]) == ("3300", "2800")
    assert [lot["quantity"] for lot in backtest["lots"]] == [300, 300]
    assert backtest["lots"][1]["source_event_id"] == "bonus-listing"
    assert (shadow["cash"], shadow["available_cash"], shadow["lots"][0]["quantity"]) == ("3909", "3300", 200)
    assert shadow["known_sellable"] == {"600362.SH": 100}
    assert shadow["lots"][0]["cost"] == "4000"
    log = account(tmp_path, monkeypatch, "log", "--book-id", "shadow", "--as-of", AFTER_FILL,
                  "--plan-id", "plan-22")
    assert [event["event_id"] for event in log] == ["broker-22"]
