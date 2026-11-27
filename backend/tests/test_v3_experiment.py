import argparse
import json

from roll.v3.market_cli import register as register_market
from roll.v3.storage import sessions
from roll.v3.strategy_cli import register as register_strategy


def command(data_dir, *argv):
    from roll.v3.experiment_cli import register_experiment_commands

    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(required=True)
    register_market(commands)
    register_strategy(commands)
    register_experiment_commands(commands)
    args = parser.parse_args(argv)
    return args.handler(args, data_dir)


def fixture(data_dir):
    start, end = "2020-01-02", "2024-01-08"
    at = "2024-01-09T15:05:00+08:00"
    closes = {
        "2023-12-29": "10.5",
        "2024-01-02": "10.7",
        "2024-01-03": "10.5",
        "2024-01-04": "10.4",
        "2024-01-05": "10.3",
        end: "10.5",
    }
    ex = "2024-01-03"
    rows = []
    prior = "10"
    for day in sessions(start, end):
        close = closes.get(day, "10")
        opening = {start: "9.99", "2024-01-04": "9.45", "2024-01-08": "10.4"}.get(day, prior)
        quote = {"open": opening, "pre_close": "10.5" if day == ex else prior,
                 "prior_close": prior, "trading_status": "trading"}
        for series, time, payload in (
            ("daily_bar", "15:05", {**quote, "close": close}),
            ("daily_open", "09:30", quote),
        ):
            rows.append(row(day, series, time, payload))
        prior = close
    rows.extend([
        row(ex, "adjustment_factor", "09:30", {
            "dividend_per_share": "0.2", "bonus_per_share": "0", "rights_per_share": "0",
        }),
        row(ex, "corporate_action", "09:30", {
            "record_date": "2024-01-02", "ex_date": ex, "cash_per_share": "0.2",
            "payment_date": "2024-01-04",
        }, item_id="dividend-a"),
    ])
    return rows, start, end, at


def row(day, series, time, payload, **extra):
    at = f"{day}T{time}:00+08:00"
    return {"series": series, "symbol": "600362.SH", "trade_date": day,
            "source": "fixture", "available_at": at, "received_at": at,
            "payload": payload, **extra}


def load(data_dir, rows, start, end, at, *, symbols=("600362.SH",)):
    incoming = data_dir / "fixture-market.json"
    incoming.write_text(json.dumps(rows), encoding="utf-8")
    command(data_dir, "market", "import", str(incoming))
    return command(data_dir, "market", "freeze", *symbols, "--start", start, "--end", end,
                   "--series", "daily_bar", "--series", "daily_open",
                   "--series", "corporate_action", "--series", "adjustment_factor",
                   "--as-of", at)["snapshot_id"]


def test_experiment_runs_continuous_paths_and_reconstructs_the_same_result_offline(tmp_path):
    rows, start, end, at = fixture(tmp_path)
    snapshot = load(tmp_path, rows, start, end, at)
    version = command(tmp_path, "strategy", "freeze", "--fast", "1", "--slow", "2",
                      "--acceptance-end", end, "--at", at)["strategy"]["version"]
    result = command(tmp_path, "experiment", "run", version, snapshot, "--at", at)
    assert result["verdict"] == "insufficient"
    assert result["independent"] is True
    assert result["coverage"]["path_gaps"] == []
    assert result["baseline_paths_overlap"] is False

    report = command(tmp_path, "experiment", "show", result["run_id"], "--trace")
    by_day = {item["date"]: item for item in report["sessions"]}
    initial = by_day[start]["paths"]
    assert initial["buy_and_hold"]["execution"]["intent"]["decision_at"].startswith("2019-12-31")
    assert initial["buy_and_hold"]["execution"]["fill"]["quantity"] == 9900
    assert initial["buy_and_hold"]["valuation"]["nav"] == "100067.35"
    assert initial["trend"]["signal"]["status"] == "warmup"
    assert initial["no_active_trading"]["valuation"]["nav"] == "100000"

    dev_close = by_day["2023-12-29"]["paths"]["trend"]
    first_acceptance = by_day["2024-01-02"]["paths"]["trend"]
    assert dev_close["decision"]["action"] == "BUY"
    assert first_acceptance["execution"]["intent"]["intent_id"] == dev_close["pending_intent"]["intent_id"]
    assert result["windows"]["acceptance"]["paths"]["trend"]["start_nav"] == "100000"
    assert result["windows"]["acceptance"]["base_date"] == "2023-12-29"

    ex = by_day["2024-01-03"]["paths"]["trend"]
    assert ex["valuation"]["receivable_value"] == "1880"
    pay = by_day["2024-01-04"]["paths"]["trend"]
    assert pay["execution"]["reason"] == "LIMIT_QUEUE_UNCONFIRMED"
    assert pay["open_account"]["cash"] == ex["account"]["cash"]
    assert pay["valuation"]["receivable_value"] == "0"
    assert pay["account"]["cash"] != pay["open_account"]["cash"]
    assert result["boundary"]["pending_intents"]["trend"]["target_session"] == "2024-01-09"

    strategy = command(tmp_path, "strategy", "show", version, "--as-of", at)
    assert strategy["acceptance"]["independent_run"]["evidence_ref"] == result["report_id"]
    assert strategy["production_eligible"] is False
    assert command(tmp_path, "experiment", "run", version, snapshot, "--at", at) == result
    # A correction appended after the freeze may change a later snapshot only.
    corrected = row(start, "daily_open", "09:30", {"open": "9.5", "pre_close": "10",
                                                     "prior_close": "10", "trading_status": "trading"})
    incoming = tmp_path / "correction.json"
    incoming.write_text(json.dumps([corrected]), encoding="utf-8")
    assert command(tmp_path, "market", "import", str(incoming))["appended"] == 1
    assert command(tmp_path, "experiment", "show", result["report_id"]) == result
    assert command(tmp_path, "experiment", "verify", result["report_id"])["matches"] is True


def test_experiment_distinguishes_opening_gaps_from_suspension_and_counts_matching_controls_once(tmp_path):
    rows, start, end, at = fixture(tmp_path)
    rows = [
        item for item in rows
        if (item["trade_date"], item["series"]) != ("2024-01-02", "daily_open")
    ]
    for item in rows:
        if item["trade_date"] == "2024-01-04" and item["series"] in ("daily_open", "daily_bar"):
            item["payload"]["trading_status"] = "suspended"
    snapshot = load(tmp_path, rows, start, end, at)
    version = command(tmp_path, "strategy", "freeze", "--fast", "1", "--slow", "2",
                      "--acceptance-end", end, "--at", at)["strategy"]["version"]
    opening = tmp_path / "initial.json"
    opening.write_text(json.dumps({
        "cash": "0",
        "lots": [{"lot_id": "confirmed-position", "symbol": "600362.SH", "quantity": 10000,
                  "sellable_on": "2019-12-31"}],
    }))
    result = command(tmp_path, "experiment", "run", version, snapshot, "--initial", str(opening),
                     "--research-ref", "dossier-fixture", "--at", at, "--replay")
    assert result["baseline_paths_overlap"] is True
    assert result["independent_baselines"] == 1
    assert result["independent"] is False
    assert result["configuration"]["research_ref"] == "dossier-fixture"
    assert result["verdict"] == "insufficient"
    assert result["coverage"]["path_gaps"] == [
        {"date": "2024-01-02", "paths": ["trend"], "reason": "MISSING_OPENING"},
    ]
    report = command(tmp_path, "experiment", "show", result["run_id"], "--trace")
    by_day = {item["date"]: item for item in report["sessions"]}
    assert by_day["2024-01-04"]["paths"]["trend"]["execution"]["reason"] == "SUSPENDED"
    assert by_day["2024-01-04"]["paths"]["no_active_trading"]["account"]["cash"] == "2000"
    assert result["windows"]["acceptance"]["paths"]["trend"]["total_return"] is None
    assert result["windows"]["acceptance"]["paths"]["buy_and_hold"]["total_return"] is not None


def test_development_robustness_preserves_the_frozen_run_and_reads_no_acceptance_sessions(tmp_path):
    rows, start, end, at = fixture(tmp_path)
    rows = [item for item in rows if (item["trade_date"], item["series"]) != ("2024-01-02", "daily_open")]
    benchmark_days = list(sessions(start, "2020-02-15"))[:21]
    rows.extend(row(day, "daily_bar", "15:05", {"close": index + 100}, symbol="000300.SH")
                for index, day in enumerate(benchmark_days))
    snapshot = load(tmp_path, rows, start, end, at, symbols=("600362.SH", "000300.SH"))
    version = command(tmp_path, "strategy", "freeze", "--fast", "1", "--slow", "2",
                      "--acceptance-end", end, "--at", at)["strategy"]["version"]
    result = command(tmp_path, "experiment", "run", version, snapshot, "--at", at)
    original = command(tmp_path, "strategy", "show", version, "--as-of", at)
    assert any(gap["date"] == "2024-01-02" for gap in result["coverage"]["path_gaps"])

    report = command(tmp_path, "experiment", "robustness", result["run_id"], "--parameters", "1", "3")
    assert report["scope"] == {"start": "2020-01-02", "end": "2023-12-29"}
    assert report["source_experiment"] == result["report_id"]
    assert report["use"] == "development_descriptive_stress"
    assert report["scenarios"]["baseline"]["paths"] == result["windows"]["development"]["paths"]
    assert report["scenarios"]["higher-costs"]["cost_multiplier"] == "2"
    assert report["scenarios"]["sma-1-3"]["parameters"] == {"fast": 1, "slow": 3}
    assert all(scenario["path_gaps"] == [] for scenario in report["scenarios"].values())
    assert report["market_regimes"]["above_ma20"]["trend"]["days"] == 2
    assert report["market_regimes"]["unknown"]["trend"]["days"] == 967
    assert command(tmp_path, "strategy", "show", version, "--as-of", at) == original
    assert command(tmp_path, "experiment", "show", result["report_id"]) == result
