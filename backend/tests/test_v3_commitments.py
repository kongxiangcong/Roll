from argparse import ArgumentParser
from decimal import Decimal
from io import StringIO
import json

from roll.v3.account_cli import register_account_commands
from roll.v3.commitment_cli import register_commitment_commands
from roll.v3.market import append_observations
from roll.v3.plan_cli import register_plan_commands
from roll.v3.strategy import StrategyRegistry


BOOK = "shadow-commitments"
SYMBOL = "600362.SH"
CUTOFF = "2026-11-27T16:00:00+08:00"
FILL_AT = "2026-11-30T09:31:00+08:00"
BEFORE_CLOSE = "2026-11-30T14:59:59+08:00"
CLOSE = "2026-11-30T15:00:00+08:00"


def _cli(data_dir, monkeypatch, *argv, payload=None):
    parser = ArgumentParser()
    commands = parser.add_subparsers(required=True)
    register_account_commands(commands)
    register_plan_commands(commands)
    register_commitment_commands(commands)
    args = parser.parse_args(argv)
    if payload is not None:
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps(payload)))
    return args.handler(args, data_dir)


def _plan(data_dir, monkeypatch):
    from roll.v3 import plan

    utc_timestamp = plan.utc_timestamp
    monkeypatch.setattr(plan, "utc_timestamp", lambda value=None: utc_timestamp(value or CUTOFF))
    _cli(data_dir, monkeypatch, "account", "init", "--book-id", BOOK, payload={
        "cash": "1800", "available_cash": "1800", "effective_at": CUTOFF, "known_at": CUTOFF,
    })
    _cli(data_dir, monkeypatch, "account", "budget", "--book-id", BOOK, payload={
        "budget_id": "full", "effective_at": CUTOFF, "known_at": CUTOFF, "cash_reserve": "0",
        "max_total_exposure": "1", "max_symbol_exposure": "1", "max_industry_exposure": "1",
    })
    append_observations(data_dir, [
        {"series": "daily_bar", "symbol": SYMBOL, "trade_date": day, "source": "fixture",
         "available_at": f"{day}T15:05:00+08:00", "received_at": f"{day}T15:05:00+08:00",
         "payload": {"close": close, "prior_close": "9", "pre_close": "9", "trading_status": "trading"}}
        for day, close in (("2026-11-26", "9"), ("2026-11-27", "9.9499"))
    ])
    version = StrategyRegistry(data_dir).freeze_default(
        fast=1, slow=2, frozen_at="2026-11-26T15:05:00+08:00",
    )["strategy"]["version"]
    plan, = _cli(data_dir, monkeypatch, "plan", "--book-id", BOOK, "--as-of", CUTOFF, "--simulate",
                 "--strategy-version", version, "--price-only")["plans"]
    return plan


def _show(data_dir, monkeypatch, cutoff, *flags):
    return _cli(data_dir, monkeypatch, "commitments", "show", "--book-id", BOOK, "--as-of", cutoff, *flags)


def _fill(data_dir, monkeypatch, plan_id, *, known_at=FILL_AT, **fields):
    return _cli(data_dir, monkeypatch, "account", "fill", "--book-id", BOOK, payload={
        "plan_id": plan_id, "event_id": "broker-fill", "symbol": SYMBOL, "side": "BUY", "quantity": 40,
        "price": "9.875", "fee": "5", "effective_at": FILL_AT, "known_at": known_at, **fields,
    })


def test_partial_fill_releases_unused_cash_at_close_after_reopening_the_cli(tmp_path, monkeypatch):
    original = _plan(tmp_path, monkeypatch)
    assert Decimal(original["cash_reserved"]) == 1000

    initial = _show(tmp_path, monkeypatch, CUTOFF)
    assert initial["remaining_commitment"] == "1000"
    assert initial["cash_available_to_allocate"] == "800"

    _fill(tmp_path, monkeypatch, original["plan_id"])
    before_close = _show(tmp_path, monkeypatch, BEFORE_CLOSE)
    assert before_close["remaining_commitment"] == "600"
    assert before_close["cash_available_to_allocate"] == "800"

    after_close = _show(tmp_path, monkeypatch, CLOSE)
    assert after_close["remaining_commitment"] == "0"
    assert after_close["cash_available_to_allocate"] == "1400"
    assert _cli(tmp_path, monkeypatch, "plan", "--plan-id", original["plan_id"]) == original


def test_first_read_after_close_releases_an_entire_unfilled_plan(tmp_path, monkeypatch):
    plan_id = _plan(tmp_path, monkeypatch)["plan_id"]
    after_close = _show(tmp_path, monkeypatch, CLOSE, "--plan-id", plan_id)
    details, = after_close["plans"]
    assert details["confirmed_fill_amount"] == details["remaining_amount"] == "0"
    assert after_close["cash_available_to_allocate"] == "1800"


def test_expiring_condition_leaves_only_the_pending_order_and_cancellation_releases_it(tmp_path, monkeypatch):
    plan = _plan(tmp_path, monkeypatch)
    plan_id = plan["plan_id"]
    order_at = "2026-11-30T09:30:00+08:00"
    condition_expiry = "2026-12-01T15:00:00+08:00"
    _cli(tmp_path, monkeypatch, "commitments", "condition", "--book-id", BOOK, payload={
        "plan_id": plan_id, "event_id": "carry", "status": "active", "description": "价格低于限价时保留",
        "effective_at": CUTOFF, "known_at": CUTOFF, "expires_at": condition_expiry,
    })
    pending = {"plan_id": plan_id, "event_id": "submitted", "order_id": "broker-order-01", "status": "pending",
               "effective_at": order_at, "known_at": order_at, "max_amount": "700", "order_quantity": 70,
               "broker_frozen": "500", "broker_available_cash": "1300"}
    _cli(tmp_path, monkeypatch, "commitments", "order", "--book-id", BOOK, payload=pending)
    _cli(tmp_path, monkeypatch, "commitments", "order", "--book-id", BOOK, payload=pending)
    _fill(tmp_path, monkeypatch, plan_id, broker_order_id="broker-order-01", broker_available_after="1300")

    carried = _show(tmp_path, monkeypatch, CLOSE)
    assert carried["remaining_commitment"] == "600"
    assert carried["broker_frozen_offset"] == "100"
    assert carried["cash_available_to_allocate"] == "800"

    after_condition = _show(tmp_path, monkeypatch, condition_expiry)
    assert after_condition["remaining_commitment"] == "300"
    assert after_condition["broker_frozen_offset"] == "100"
    assert after_condition["cash_available_to_allocate"] == "1100"

    cancelled_at = "2026-12-02T09:45:00+08:00"
    _cli(tmp_path, monkeypatch, "commitments", "order", "--book-id", BOOK, payload={
        "plan_id": plan_id, "event_id": "cancelled", "order_id": "broker-order-01", "status": "cancelled",
        "effective_at": cancelled_at, "known_at": cancelled_at, "broker_available_cash": "1400",
    })
    cancelled = _show(tmp_path, monkeypatch, cancelled_at)
    assert cancelled["remaining_commitment"] == "0"
    assert cancelled["cash_available_to_allocate"] == "1400"
    assert _cli(tmp_path, monkeypatch, "plan", "--plan-id", plan_id) == plan


def test_late_fill_and_its_correction_enter_the_cash_projection_at_their_knowledge_times(tmp_path, monkeypatch):
    plan_id = _plan(tmp_path, monkeypatch)["plan_id"]
    order_at = "2026-11-30T09:30:00+08:00"
    reported_at = "2026-11-30T16:10:00+08:00"
    corrected_at = "2026-12-01T10:00:00+08:00"
    voided_at = "2026-12-02T10:00:00+08:00"
    _cli(tmp_path, monkeypatch, "commitments", "order", "--book-id", BOOK, payload={
        "plan_id": plan_id, "event_id": "submitted", "order_id": "broker-order-01", "status": "pending",
        "effective_at": order_at, "known_at": order_at,
    })
    _fill(tmp_path, monkeypatch, plan_id, known_at=reported_at)
    _fill(tmp_path, monkeypatch, plan_id, known_at=reported_at)
    for event_id, knowledge, replacement in (
        ("broker-correction", corrected_at, {"quantity": 20}),
        ("broker-void", voided_at, None),
    ):
        _cli(tmp_path, monkeypatch, "account", "correct", "--book-id", BOOK, payload={
            "event_id": event_id, "target_event_id": "broker-fill", "replacement": replacement, "known_at": knowledge,
        })

    before_report = _show(tmp_path, monkeypatch, CLOSE)
    assert before_report["cash"] == "1800"
    assert before_report["remaining_commitment"] == "1000"
    retroactive = _show(tmp_path, monkeypatch, CLOSE, "--known-at", reported_at)
    assert retroactive["cash"] == "1400"
    assert retroactive["remaining_commitment"] == "600"

    assert _show(tmp_path, monkeypatch, "2026-11-30T09:30:30+08:00", "--known-at", corrected_at)[
        "remaining_commitment"] == "1000"
    corrected = _show(tmp_path, monkeypatch, corrected_at)
    assert corrected["cash"] == "1597.5"
    assert corrected["remaining_commitment"] == "797.5"
    assert _show(tmp_path, monkeypatch, voided_at)["remaining_commitment"] == "1000"


def test_a_new_decision_uses_the_cash_committed_by_the_order_on_the_previous_revision(tmp_path, monkeypatch):
    original = _plan(tmp_path, monkeypatch)
    plan_id = original["plan_id"]
    submitted_at = "2026-11-27T16:03:00+08:00"
    rerun_at = "2026-11-27T16:05:00+08:00"
    order = {"plan_id": plan_id, "event_id": "submitted", "order_id": "broker-order-01", "status": "pending",
             "effective_at": submitted_at, "known_at": submitted_at, "max_amount": "1000", "broker_frozen": "300",
             "broker_available_cash": "1500"}
    _cli(tmp_path, monkeypatch, "commitments", "order", "--book-id", BOOK, payload=order)

    args = ("plan", "--book-id", BOOK, "--as-of", rerun_at, "--simulate", "--price-only",
            "--strategy-version", original["strategy_version"])
    revised, = _cli(tmp_path, monkeypatch, *args)["plans"]
    constraints = revised["account_constraints"]
    assert revised["action"] == "WATCH"
    assert revised["replaces_plan_id"] == plan_id
    assert constraints["existing_reservations_net_of_broker"] == "700"
    assert constraints["cash_available_to_allocate"] == "800"

    after_replacement = _show(tmp_path, monkeypatch, rerun_at)
    assert after_replacement["plans"][0]["plan_id"] == plan_id
    assert after_replacement["cash_available_to_allocate"] == "800"
    assert _cli(tmp_path, monkeypatch, "plan", "--plan-id", plan_id) == original
    account = _cli(tmp_path, monkeypatch, "account", "show", "--snapshot-id", original["account_snapshot_id"])
    assert account["available_cash"] == "1800"
