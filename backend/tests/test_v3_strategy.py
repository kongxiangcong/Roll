import argparse

from roll.v3.strategy_cli import register


def command(data_dir, *args):
    parser = argparse.ArgumentParser()
    register(parser.add_subparsers(required=True))
    options = parser.parse_args(["strategy", *args])
    return options.handler(options, data_dir)


def test_freeze_registers_a_replayable_strategy_version_without_production_admission(tmp_path):
    frozen = command(tmp_path, "freeze", "--at", "2026-11-26T15:05:00+08:00")
    strategy = frozen["strategy"]
    assert strategy["parameters"] == {"fast": 20, "slow": 60}
    assert frozen["protocol"]["windows"]["acceptance"] == {
        "start": "2024-01-02", "end": "2026-11-25",
    }
    assert frozen["protocol"]["baselines"].keys() == {"buy_and_hold", "no_active_trading"}
    assert frozen["status"] == "frozen"
    assert frozen["production_eligible"] is False
    assert frozen["simulation_eligible"] is True

    version = strategy["version"]
    assert command(tmp_path, "show", version, "--as-of", "2026-11-26T15:04:59+08:00") is None
    visible = command(tmp_path, "show", version, "--as-of", "2026-11-26T15:05:00+08:00")
    assert visible["scope"]["symbols"] == ["600362.SH"]
    assert visible["strategy"] == strategy
    assert command(tmp_path, "registry", "600362.SH", "--as-of", "2026-11-26T15:05:00+08:00") == []

    changed = command(tmp_path, "freeze", "--fast", "15", "--at", "2026-11-26T15:06:00+08:00")
    assert changed["strategy"]["version"] != version
    assert changed["protocol"]["version"] != frozen["protocol"]["version"]
    assert command(tmp_path, "freeze")["strategy"]["version"] == version


def test_replay_uses_visible_dividends_and_reports_warmup_and_gaps(tmp_path):
    from decimal import Decimal
    import json

    from roll.v3.market_cli import register as register_market

    parser = argparse.ArgumentParser()
    actions = parser.add_subparsers(required=True)
    register(actions)
    register_market(actions)

    def run(*args):
        options = parser.parse_args(args)
        return options.handler(options, tmp_path)

    action_day = "2023-07-05"
    rows = []
    for day, close, prior, reference in (
        ("2023-07-03", "10", "10", "10"),
        ("2023-07-04", "11", "10", "10"),
        (action_day, "10", "11", "10"),
        ("2023-07-06", "10", "10", "10"),
    ):
        rows.append({
            "series": "daily_bar", "symbol": "600362.SH", "trade_date": day, "source": "fixture",
            "available_at": day + "T15:05:00+08:00", "received_at": day + "T15:05:00+08:00",
            "payload": {"close": close, "prior_close": prior, "pre_close": reference,
                        "trading_status": "trading"},
        })
    rows.append({
        "series": "adjustment_factor", "symbol": "600362.SH", "trade_date": action_day,
        "source": "fixture", "available_at": action_day + "T09:30:00+08:00",
        "received_at": action_day + "T09:30:00+08:00",
        "payload": {"dividend_per_share": "1", "bonus_per_share": "0", "rights_per_share": "0"},
    })
    rows.append({
        **rows[-1], "available_at": action_day + "T17:00:00+08:00",
        "received_at": action_day + "T17:00:00+08:00",
        "payload": {"dividend_per_share": "0", "bonus_per_share": "0", "rights_per_share": "0"},
    })
    incoming = tmp_path / "market.json"
    incoming.write_text(json.dumps(rows), encoding="utf-8")
    run("market", "import", str(incoming))
    snapshot_id = run(
        "market", "freeze", "600362.SH", "--start", "2023-07-03", "--end", "2023-07-07",
        "--series", "daily_bar", "--series", "adjustment_factor", "--as-of", "2023-07-07T17:00:00+08:00",
    )["snapshot_id"]
    version = run("strategy", "freeze", "--fast", "1", "--slow", "3")["strategy"]["version"]
    replay = run("strategy", "replay", version, snapshot_id, "--start", "2023-07-03",
                 "--end", "2023-07-07")["sessions"]
    assert [row["status"] for row in replay] == ["warmup", "warmup", "ready", "ready", "missing"]
    assert replay[2]["signal"] == "long"
    assert replay[2]["target_fraction"] == "1"
    assert replay[2]["conditions"]["fast_average"] == "110"
    assert Decimal(replay[3]["conditions"]["fast_average"]).quantize(Decimal("0.01")) == Decimal("90.91")
    assert replay[4]["signal"] is None
    assert replay[4]["missing"] == [{"trade_date": "2023-07-07", "reason": "daily_bar"}]


def test_revealed_acceptance_window_cannot_independently_accept_a_changed_strategy(tmp_path):
    from roll.v3.market_cli import register as register_market

    parser = argparse.ArgumentParser()
    actions = parser.add_subparsers(required=True)
    register(actions)
    register_market(actions)

    def run(*args):
        options = parser.parse_args(args)
        return options.handler(options, tmp_path)

    versions = [
        run("strategy", "freeze", "--fast", str(fast), "--at", "2026-11-26T09:00:00+08:00")
        ["strategy"]["version"]
        for fast in (20, 15)
    ]
    snapshot_id = run(
        "market", "freeze", "600362.SH", "--start", "2020-01-02", "--end", "2026-11-25",
        "--series", "daily_bar", "--series", "adjustment_factor",
        "--as-of", "2026-11-26T10:00:00+08:00",
    )["snapshot_id"]

    visible_before = run("strategy", "show", versions[1], "--as-of", "2026-11-26T11:00:00+08:00")
    assert visible_before["acceptance"]["new_independent_run_allowed"] is True
    first = run("strategy", "open-acceptance", versions[0], snapshot_id, "run-1",
                "--at", "2026-11-26T12:00:00+08:00")
    assert first["independent"] is True
    assert run("strategy", "open-acceptance", versions[0], snapshot_id, "run-1") == first

    changed = run("strategy", "show", versions[1], "--as-of", "2026-11-26T13:00:00+08:00")
    assert changed["acceptance"]["new_independent_run_allowed"] is False
    assert changed["acceptance"]["exposures"][0]["run_id"] == "run-1"
    second = run("strategy", "open-acceptance", versions[1], snapshot_id, "run-2",
                 "--at", "2026-11-26T13:00:00+08:00")
    assert second["independent"] is False
    assert second["use"] == "comparison_only"
    assert run("strategy", "registry", "600362.SH", "--as-of", "2026-11-26T13:00:00+08:00") == []


def test_production_admission_requires_independent_history_and_consecutive_forward_evidence(tmp_path):
    import pytest

    from roll.v3.market import RECONSTRUCTED_RESEARCH, freeze_snapshot
    from roll.v3.storage import sessions
    from roll.v3.strategy import StrategyRegistry

    registry = StrategyRegistry(tmp_path)
    at = "2026-11-26T09:00:00+08:00"
    version = command(tmp_path, "freeze", "--at", at)["strategy"]["version"]
    snapshot_id = freeze_snapshot(
        tmp_path, as_of=at, use_mode=RECONSTRUCTED_RESEARCH,
        scope=[
            {"symbol": "600362.SH", "series": series, "start": "2020-01-02", "end": "2026-11-25"}
            for series in ("daily_bar", "adjustment_factor")
        ],
    )["snapshot_id"]
    command(tmp_path, "open-acceptance", version, snapshot_id, "run-1", "--at", at)
    registry.record_historical_result(
        version, run_id="run-1", verdict="pass", evidence_ref="experiment-result-1",
        recorded_at="2026-11-26T10:00:00+08:00",
    )
    before = "2026-11-26T11:00:00+08:00"
    assert command(tmp_path, "show", version, "--as-of", before)["status"] == "accepted"
    assert command(tmp_path, "registry", "600362.SH", "--as-of", before) == []
    with pytest.raises(ValueError, match="前向"):
        command(tmp_path, "admit", version, "--at", before)

    forward_sessions = list(sessions("2026-11-27", "2026-12-24"))
    review_at = "2026-12-24T15:10:00+08:00"
    with pytest.raises(ValueError, match="连续"):
        registry.record_forward_result(
            version, session_dates=forward_sessions[:-1], verdict="pass",
            evidence_ref="short-shadow-window", recorded_at=review_at,
        )
    registry.record_forward_result(
        version, session_dates=forward_sessions, verdict="pass",
        evidence_ref="shadow-window-1", recorded_at=review_at,
    )
    assert command(tmp_path, "registry", "600362.SH", "--as-of", review_at) == []
    admitted_at = "2026-12-24T17:00:00+08:00"
    assert command(tmp_path, "admit", version, "--at", admitted_at)["status"] == "admitted"
    visible = command(tmp_path, "registry", "600362.SH", "--as-of", admitted_at)
    assert [item["strategy"]["version"] for item in visible] == [version]
    assert command(tmp_path, "show", version, "--as-of", review_at)["status"] == "accepted"
