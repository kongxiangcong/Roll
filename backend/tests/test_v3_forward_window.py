from argparse import ArgumentParser
import io
import json

import pytest

from roll.v3 import research, review
from roll.v3.cli import run
from roll.v3.storage import instant


TWENTY_SESSIONS = (
    "2026-10-08", "2026-10-09", "2026-10-12", "2026-10-13", "2026-10-14",
    "2026-10-15", "2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21",
    "2026-10-22", "2026-10-23", "2026-10-26", "2026-10-27", "2026-10-28",
    "2026-10-29", "2026-10-30", "2026-11-02", "2026-11-03", "2026-11-04",
)


def window(data_dir, *argv):
    from roll.v3.forward_window_cli import register_forward_window_commands

    cli = ArgumentParser()
    register_forward_window_commands(cli.add_subparsers(required=True))
    args = cli.parse_args(("forward-window", *argv))
    return args.handler(args, data_dir)


@pytest.fixture
def trading_clock(tmp_path, monkeypatch):
    from roll.v3 import forward_window

    current = None

    def clock(value=None):
        return instant(value or current)

    def set_time(day, time="16:00"):
        nonlocal current
        current = f"{day}T{time}:00+08:00"

    monkeypatch.setattr(review, "instant", clock)
    monkeypatch.setattr(research, "instant", clock)
    monkeypatch.setattr(forward_window, "instant", clock)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({
        "cash": "2200", "available_cash": "2200",
        "effective_at": "2026-08-31T15:00:00+08:00", "known_at": "2026-08-31T15:00:00+08:00",
    })))
    run(("account", "init"), data_dir=tmp_path)
    return set_time


def test_audit_counts_live_observations_and_keeps_gaps_across_exchange_holidays(tmp_path, trading_clock):
    trading_clock("2026-09-24")
    first = run(("review", "register"), data_dir=tmp_path)
    trading_clock("2026-09-28")
    run(("review", "register"), data_dir=tmp_path)
    before_gap = window(tmp_path, "audit")
    assert before_gap["consecutive_live_sessions"] == 2
    assert [day["decision_date"] for day in before_gap["sessions"]] == ["2026-09-24", "2026-09-28"]
    observation, = before_gap["sessions"][0]["plans"]
    assert before_gap["sessions"][0]["registered_at"] == "2026-09-24T08:00:00.000000+00:00"
    assert observation["real_plan"]["plan_id"] == first["plans"][0]["real_plan"]["plan_id"]
    assert observation["real_plan"]["revision"] == 1
    assert observation["real_plan"]["action"] == "WATCH"
    assert observation["actual"]["status"] == "OBSERVED"
    assert observation["shadow"]["status"] == "OBSERVED"

    run(("review", "register", "--mode", "rehearsal", "--now", "2026-09-29T16:00:00+08:00"),
        data_dir=tmp_path)
    trading_clock("2026-09-30")
    run(("review", "register", "--mode", "reconstructed", "--as-of", "2026-09-29T16:00:00+08:00"),
        data_dir=tmp_path)
    run(("review", "register"), data_dir=tmp_path)
    after_gap = window(tmp_path, "audit")
    assert after_gap["status"] == "pending"
    assert after_gap["consecutive_live_sessions"] == 1
    assert after_gap["missing_live_dates"] == ["2026-09-29"]
    missed = after_gap["sessions"][2]
    assert missed["registration_id"] is None
    assert {record["mode"] for record in missed["excluded_registrations"]} == {"reconstructed", "rehearsal"}
    with pytest.raises(ValueError, match="连续 20"):
        window(tmp_path, "signoff")


def test_m0b_signoff_freezes_twenty_sessions_and_keeps_the_last_pending_target(tmp_path, trading_clock):
    version = run(("strategy", "freeze", "--at", "2026-10-08T15:00:00+08:00"), data_dir=tmp_path)["strategy"]["version"]
    for day in TWENTY_SESSIONS:
        trading_clock(day)
        last = run(("review", "register", "--strategy-version", version), data_dir=tmp_path)

    audit = window(tmp_path, "audit")
    assert audit["status"] == "ready"
    assert audit["consecutive_live_sessions"] == 20
    assert audit["window"]["start"] == "2026-10-08"
    assert audit["window"]["end"] == "2026-11-04"
    assert audit["window"]["pending_target_session"] == "2026-11-05"
    assert audit["sessions"][-1]["plans"][0]["shadow"]["status"] == "PENDING"

    signed = window(tmp_path, "signoff")
    assert signed["status"] == "signed_off"
    assert signed["sessions"] == audit["sessions"]
    assert [entry["decision_date"] for entry in signed["sessions"]] == list(TWENTY_SESSIONS)
    assert not run(("strategy", "show", version), data_dir=tmp_path)["production_eligible"]

    trading_clock("2026-11-05", "09:30")
    overdue = window(tmp_path, "audit", "--end", "2026-11-04")
    assert overdue["status"] == "pending"
    assert overdue["window"]["blocking_issues"] == [{
        "decision_date": "2026-11-04", "reason": "SHADOW_OPENING_MISSING", "symbol": "600362.SH",
    }]

    trading_clock("2026-11-05")
    run(("review", "settle", last["registration_id"]), data_dir=tmp_path)
    updated = window(tmp_path, "audit", "--end", "2026-11-04")
    assert updated["status"] == "ready"
    assert updated["window"]["pending_target_session"] is None
    assert updated["sessions"][-1]["plans"][0]["shadow"]["status"] == "OBSERVED"
    assert updated["sessions"][-1]["shadow_closing"]["status"] == "SETTLED"
    assert window(tmp_path, "show", signed["signoff_id"]) == signed
    assert window(tmp_path, "signoff", "--end", "2026-11-04") == signed


def test_audit_reports_unconfirmed_real_execution_and_unverified_shadow_opening(
    tmp_path, trading_clock, monkeypatch,
):
    symbol = "600362.SH"
    decision_day = "2026-11-02"
    target = "2026-11-03"
    trading_clock(decision_day)
    shares = {
        "event_id": "confirmed-existing-shares", "effective_at": "2026-10-30T15:00:00+08:00",
        "known_at": "2026-10-30T15:00:00+08:00",
        "lot": {"lot_id": "current", "symbol": symbol, "quantity": 100, "known_sellable": 100},
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(shares)))
    run(("account", "shares"), data_dir=tmp_path)

    dossier = tmp_path / "broken.md"
    dossier.write_text('---\nvalid_until: "2026-11-10T00:00:00+08:00"\n'
                       'fundamental_gate: fail\nthesis_status: broken\n---\n# 原假设已失效\n', encoding="utf-8")
    run(("research", "draft", symbol, str(dossier)), data_dir=tmp_path)
    run(("research", "publish", symbol, "broken", "--reviewer", "测试"), data_dir=tmp_path)
    quotes = tmp_path / "closing-quotes.json"
    quotes.write_text(json.dumps([{
        "series": "daily_bar", "symbol": symbol, "trade_date": day, "source": "fixture",
        "available_at": f"{day}T15:05:00+08:00", "received_at": f"{day}T15:05:00+08:00",
        "payload": {"close": "10", "prior_close": "10", "pre_close": "10", "trading_status": "trading"},
    } for day in (decision_day, target)]), encoding="utf-8")
    run(("market", "import", str(quotes)), data_dir=tmp_path)

    result = run(("review", "register"), data_dir=tmp_path)
    key = result["registration_id"]
    run(("review", "outcome", key, symbol, "confirmed"), data_dir=tmp_path)
    trading_clock(target)
    run(("review", "settle", key), data_dir=tmp_path)
    day, = window(tmp_path, "audit", "--end", decision_day)["sessions"]
    plan, = day["plans"]
    assert plan["real_plan"]["action"] == "SELL"
    assert plan["actual"]["status"] == "UNREPORTED"
    assert plan["actual"]["reason"] == "RESULT_NOT_REPORTED"
    assert plan["shadow"]["status"] == "UNFILLED"
    assert {issue["reason"] for issue in day["blocking_issues"]} == {"ACTUAL_OUTCOME_MISSING", "MISSING_OPENING"}

    run(("review", "outcome", key, symbol, "not_executed", "--reason", "未提交券商委托"), data_dir=tmp_path)
    settled, = window(tmp_path, "audit", "--end", decision_day)["sessions"]
    assert settled["plans"][0]["actual"]["reason"] == "未提交券商委托"
    assert [issue["reason"] for issue in settled["blocking_issues"]] == ["MISSING_OPENING"]


def test_audit_reports_missing_exchange_calendar_without_guessing_weekdays(tmp_path, trading_clock):
    trading_clock("2027-01-05")
    audit = window(tmp_path, "audit", "--start", "2026-12-31")
    assert audit["calendar_known_through"] == "2026-12-31"
    assert audit["calendar_coverage_complete"] is False
    assert audit["missing_live_dates"] == ["2026-12-31"]
    with pytest.raises(ValueError, match="交易所日历"):
        window(tmp_path, "signoff", "--start", "2026-12-31")
