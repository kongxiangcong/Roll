import json
import os
from pathlib import Path
import subprocess
import sys
from decimal import Decimal

import pytest

from roll.v3.storage import sessions
from test_v3_development_inputs import PRESET, command, load_snapshot, observation


def _quotes(start="2020-01-02"):
    days = list(sessions(start, "2023-12-29"))
    rows = []
    for i, day in enumerate(days):
        close = "11" if day == days[-1] else "9" if i < 59 else "10"
        rows.append(observation(day, close=close))
        rows.append(observation(day, symbol="000300.SH", close={60: "99", 61: "101", len(days) - 1: "101"}.get(i, "100")))
        reference = "9" if i <= 59 else "10"
        rows.append(observation(day, series="daily_open", assumed_available_at=f"{day}T09:30:00+08:00",
                                payload={"open": reference, "pre_close": reference, "trading_status": "trading"}))
    return days, rows


def test_development_replays_from_the_first_common_close_and_records_the_market_gate(tmp_path):
    days, rows = _quotes()
    snapshot = load_snapshot(tmp_path, rows)

    attempt = command(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot)
    report = command(tmp_path, "research", "task", "development-receipt", attempt["task_id"])

    assert report["receipt_id"] == attempt["development_receipt_id"]
    first, following = report["sessions"][:2]
    assert first["date"] == days[59]
    assert {path["valuation"]["nav"] for path in first["paths"].values()} == {"100000"}
    assert all(path["account"]["lots"] == [] and path["execution"]["fill"] is None
               for path in first["paths"].values())
    assert first["paths"]["e0"]["decision"]["action"] == "BUY"
    assert first["paths"]["e1"]["decision_before_gate"]["action"] == "BUY"
    assert first["paths"]["e1"]["gate"]["reason"] == "MARKET_AT_OR_BELOW_AVERAGE"
    assert first["paths"]["e1"]["pending_intent"] is None
    assert first["paths"]["buy_and_hold"]["decision"]["action"] == "BUY"
    assert first["paths"]["no_active_trading"]["decision"]["action"] == "HOLD"
    fill = following["paths"]["e0"]["execution"]["fill"]
    assert fill["quantity"] == 9800
    assert Decimal(fill["price"]) == Decimal("10.01")
    assert Decimal(fill["fee"]) == Decimal("31.39")
    assert following["paths"]["e0"]["valuation"]["nav"] == "99870.61"
    assert first["paths"]["e0"]["next_open"]["fill"] == fill
    assert following["paths"]["e1"]["execution"]["fill"] is None
    assert report["opportunities"]["market_filter"]["blocked_buy_count"] >= 2
    assert report["metrics"]["no_active_trading"]["total_return"] == "0"
    assert report["sessions"][-1]["paths"]["e0"]["next_open"] == {
        "date": "2024-01-02", "status": "OUTSIDE_WINDOW", "reason": "AFTER_DEVELOPMENT_WINDOW", "fill": None,
    }


def test_common_gaps_preserve_an_exit_and_entitlement_and_verify_offline(tmp_path):
    start = list(sessions("2023-01-03", "2023-12-29"))[-100]
    days, rows = _quotes(start)
    for i in range(63, 99):
        rows[3 * i + 1] = None  # The stock remains visible through the index outage.
    rows[3 * 60 + 2]["payload"]["trading_status"] = "suspended"
    ex, pay = days[64], days[66]
    rows[3 * 64]["payload"].update(close="9.8", pre_close_basis="fuyao_adjustment_factor")
    for i in range(70, 99):
        rows[3 * i]["payload"]["close"] = "9"
        rows[3 * i + 2]["payload"].update(open="9", pre_close="9")
    rows += [
        observation(ex, series="adjustment_factor", assumed_available_at=f"{ex}T09:30:00+08:00",
                    payload={"dividend_per_share": "0.2", "bonus_per_share": "0", "rights_per_share": "0"}),
        observation(ex, series="corporate_action", item_id="dividend", assumed_available_at=f"{ex}T09:30:00+08:00",
                    payload={"record_date": days[63], "ex_date": ex, "payment_date": pay, "cash_per_share": "0.2"}),
    ]
    snapshot = load_snapshot(tmp_path, [row for row in rows if row is not None])
    strategy = command(tmp_path, "strategy", "freeze")["strategy"]["version"]
    registry = command(tmp_path, "strategy", "show", strategy)

    attempt = command(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot)
    report = command(tmp_path, "research", "task", "development-receipt", attempt["task_id"])
    by_date = {row["date"]: row for row in report["sessions"]}
    assert by_date[days[59]]["paths"]["e0"]["next_open"]["reason"] == "SUSPENDED"
    assert by_date[days[60]]["paths"]["e1"]["gate"]["reason"] == "MARKET_AT_OR_BELOW_AVERAGE"
    assert by_date[days[61]]["paths"]["e1"]["next_open"]["fill"]["quantity"] == 9800
    assert by_date[days[63]]["paths"]["e0"]["gate"]["reason"] == "COMMON_ENTRY_INPUT_UNAVAILABLE"
    for path in ("e0", "e1", "buy_and_hold"):
        assert by_date[ex]["paths"][path]["valuation"]["receivable_value"] == "1960"
        assert by_date[pay]["paths"][path]["valuation"]["receivable_value"] == "0"
        assert Decimal(by_date[pay]["paths"][path]["account"]["cash"]) - Decimal(
            by_date[pay]["paths"][path]["open_account"]["cash"]) == Decimal("1960")
    for path in ("e0", "e1"):
        exit_signal, = [row for row in report["sessions"] if row["paths"][path]["decision"]["action"] == "SELL"]
        assert exit_signal["common_evaluable"] is False
        fill = exit_signal["paths"][path]["next_open"]["fill"]
        assert fill["quantity"] == 9800 and fill["price"] == "9.00"
        assert Decimal(fill["fee"]) == Decimal("71.44")
        assert report["metrics"][path]["path_complete"]
    assert report["coverage"]["path_gaps"] == []
    assert report["self_check"]["passed"] and report["self_check"]["e0"] == report["self_check"]["e1"]

    cutoff = days[60] + "T09:35:00+08:00"
    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    cli = [sys.executable, "-m", "roll.v3.cli", "--data-dir", str(tmp_path)]
    subprocess.run([*cli, "account", "init"], check=True, capture_output=True, text=True, env=environment, input=json.dumps({
        "cash": "1234", "available_cash": "1234", "effective_at": cutoff, "known_at": cutoff,
    }))
    load_snapshot(tmp_path, [observation(days[60], close="1"), observation("2024-01-02", close="88888")])
    verified = subprocess.run([*cli, "research", "task", "development-verify", attempt["task_id"]],
                              check=True, capture_output=True, text=True, env=environment, timeout=60)
    verification = json.loads(verified.stdout)
    assert verification["verified"] is True
    assert all(verification["checks"][name] for name in ("metrics", "opportunities", "coverage", "sessions", "self_check"))
    assert command(tmp_path, "strategy", "show", strategy) == registry


@pytest.mark.parametrize(("factor", "expected_loss"), [
    (None, "MISSING_ADJUSTMENT_FACTOR"), ("0.3", "ENTITLEMENT_TERMS_UNVERIFIED"),
])
def test_unverified_dividend_economics_interrupt_the_common_sample(tmp_path, factor, expected_loss):
    start = list(sessions("2023-01-03", "2023-12-29"))[-75]
    days, rows = _quotes(start)
    for index in range(len(days)):
        rows[3 * index + 1]["payload"]["close"] = str(100 + index)
    ex = days[59]
    rows.append(observation(ex, series="corporate_action", item_id="dividend",
                            payload={"record_date": days[58], "ex_date": ex, "cash_per_share": "0.2",
                                     "payment_date": days[63]}))
    if factor is not None:
        rows.append(observation(ex, series="adjustment_factor",
                                payload={"dividend_per_share": factor, "bonus_per_share": "0"}))

    snapshot = load_snapshot(tmp_path, rows)
    attempt = command(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot)
    receipt = command(tmp_path, "research", "task", "development-receipt", attempt["task_id"])

    assert attempt["status"] == "blocked"
    assert receipt["sample"]["losses"][ex] == [{"feature": "adjustment_factor", "reason": expected_loss}]
    assert receipt["sample"]["losses"][days[60]] == [{"feature": "e0", "reason": "warmup"}]
    assert receipt["sample"]["common_evaluable_dates"] == []


def test_missing_dividend_payment_date_preserves_verified_signal_economics(tmp_path):
    days, rows = _quotes(list(sessions("2023-01-03", "2023-12-29"))[-75])
    ex = days[64]
    rows[3 * 64]["payload"].update(close="9.8", pre_close_basis="fuyao_adjustment_factor")
    rows += [
        observation(ex, series="adjustment_factor", payload={"dividend_per_share": "0.2", "bonus_per_share": "0"}),
        observation(ex, series="corporate_action", item_id="dividend",
                    payload={"record_date": days[63], "ex_date": ex, "cash_per_share": "0.2"}),
    ]
    snapshot = load_snapshot(tmp_path, rows)
    attempt = command(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot)
    receipt = command(tmp_path, "research", "task", "development-receipt", attempt["task_id"])

    assert ex in receipt["sample"]["common_evaluable_dates"]
    assert receipt["sample"]["by_date"][ex]["e0"]["status"] == "ready"
    gap, = [gap for gap in receipt["coverage"]["path_gaps"] if gap["reason"] == "ENTITLEMENT_SETTLEMENT_DATE_MISSING"]
    assert gap["date"] == ex and gap["paths"] == ["buy_and_hold", "e0", "e1"]


def test_later_unusable_marks_flag_only_the_affected_paths_and_preserve_prior_fills(tmp_path):
    start = list(sessions("2023-01-03", "2023-12-29"))[-75]
    days, rows = _quotes(start)
    snapshot = load_snapshot(tmp_path, rows)
    original = command(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot)
    original = command(tmp_path, "research", "task", "development-receipt", original["task_id"])

    revised = load_snapshot(tmp_path, [observation(days[65], quality="unusable", close="555.55")])
    attempt = command(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", revised)
    receipt = command(tmp_path, "research", "task", "development-receipt", attempt["task_id"])

    for before, after in zip(original["sessions"][:6], receipt["sessions"][:6]):
        assert before["date"] == after["date"]
        assert all(before["paths"][path]["execution"]["fill"] == after["paths"][path]["execution"]["fill"]
                   for path in before["paths"])
    gap, = receipt["coverage"]["path_gaps"]
    assert gap["date"] == days[65]
    assert gap["reason"] == "MISSING_VALUATION_MARK" and gap["observation_quality"] == "unusable"
    assert gap["paths"] == ["buy_and_hold", "e0", "e1"]
    assert {"total_return", "max_drawdown"}.issubset(gap["affected_metrics"])
    assert receipt["metrics"]["e0"]["total_return"] is None
    assert receipt["metrics"]["e0"]["metric_scope"]["trade_totals"] == "complete_path"
    assert receipt["metrics"]["no_active_trading"]["total_return"] == "0"


def test_development_records_a_retrievable_failure_at_the_freeze_stage(tmp_path):
    snapshot_id = "unknown-frozen-snapshot"
    attempt = command(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot_id)

    report = command(tmp_path, "research", "task", "development-receipt", attempt["task_id"])
    assert attempt["status"] == report["status"] == "failed"
    assert attempt["development_receipt_id"] == report["receipt_id"]
    assert report["preset"]["id"] == PRESET
    assert report["snapshot_id"] == snapshot_id
    assert report["failure_stage"] == "freeze_inputs"
    assert snapshot_id in report["error"]


def test_development_applies_minimum_commission_to_an_add_on_and_compares_both_baselines(tmp_path):
    start = list(sessions("2023-01-03", "2023-12-29"))[-64]
    days, rows = _quotes(start)
    rows[3 * 61 + 2]["payload"]["open"] = "9.99"
    snapshot = load_snapshot(tmp_path, rows)

    attempt = command(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot)
    report = command(tmp_path, "research", "task", "development-receipt", attempt["task_id"])

    add_on = report["sessions"][2]["paths"]["e0"]["execution"]["fill"]
    assert report["sessions"][2]["date"] == days[61]
    assert add_on["quantity"] == 100 and Decimal(add_on["fee"]) == Decimal("5.01")
    metrics = report["metrics"]["e0"]
    assert metrics["total_return"] == "0.0976758"
    assert metrics["costs"] == "35.42" and metrics["slippage_cost"] == "98"
    assert metrics["excess_return_vs_buy_and_hold"] == "0.0009599"
    assert metrics["excess_return_vs_no_active_trading"] == metrics["total_return"]
