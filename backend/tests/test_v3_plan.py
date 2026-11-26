from argparse import ArgumentParser

from roll.v3.account import AccountLedger
from roll.v3.plan_cli import register_plan_commands


CUTOFF = "2026-11-27T16:00:00+08:00"
SYMBOL = "600362.SH"


def plan_cli(data_dir, *argv):
    parser = ArgumentParser()
    register_plan_commands(parser.add_subparsers(required=True))
    args = parser.parse_args(("plan", *argv))
    return args.handler(args, data_dir)


def test_offline_plan_is_a_repeatable_watch_with_a_frozen_next_session(tmp_path):
    ledger = AccountLedger(tmp_path)
    ledger.initialize("real", cash="20000", available_cash="20000", effective_at=CUTOFF, known_at=CUTOFF)

    result = plan_cli(tmp_path, "--as-of", CUTOFF, "--symbol", SYMBOL)
    plan, = result["plans"]

    assert plan["action"] == "WATCH"
    assert plan["session"] == "2026-11-30"
    assert plan["execution_window"] == {
        "start": "2026-11-30T01:30:00.000000+00:00",
        "end": "2026-11-30T01:30:00.000000+00:00",
    }
    assert list(plan["reasons"]) == ["P0", "P1", "P2", "P3", "P4"]
    assert plan["market_state"] == plan["industry_state"] == plan["stock_state"] == "unknown"
    assert plan_cli(tmp_path, "--as-of", CUTOFF, "--symbol", SYMBOL) == result
    assert plan_cli(tmp_path, "--plan-id", plan["plan_id"]) == plan


def _seed_trend(data_dir, *books):
    from roll.v3.market import append_observations
    from roll.v3.strategy import StrategyRegistry

    ledger = AccountLedger(data_dir)
    for book in books:
        ledger.initialize(book, cash="2200", available_cash="2200", effective_at=CUTOFF, known_at=CUTOFF)
        ledger.set_risk_budget(
            book, budget_id="fixture-budget", effective_at=CUTOFF, known_at=CUTOFF, cash_reserve="0",
            max_total_exposure="1", max_symbol_exposure="1", max_industry_exposure="1",
        )
    rows = []
    for day, close in (("2026-11-26", "10"), ("2026-11-27", "11")):
        rows.append({
            "series": "daily_bar", "symbol": SYMBOL, "trade_date": day, "source": "fixture",
            "available_at": f"{day}T15:05:00+08:00", "received_at": f"{day}T15:05:00+08:00",
            "payload": {"close": close, "prior_close": "10", "pre_close": "10", "trading_status": "trading"},
        })
    append_observations(data_dir, rows)
    version = StrategyRegistry(data_dir).freeze_default(
        fast=1, slow=2, frozen_at="2026-11-26T15:05:00+08:00",
    )["strategy"]["version"]
    return version


def test_frozen_trend_remains_observation_in_real_book_and_can_buy_in_shadow(tmp_path):
    version = _seed_trend(tmp_path, "real", "shadow-trend")

    formal, = plan_cli(tmp_path, "--as-of", CUTOFF)["plans"]
    simulated, = plan_cli(
        tmp_path, "--as-of", CUTOFF, "--book-id", "shadow-trend", "--simulate",
        "--strategy-version", version, "--price-only",
    )["plans"]

    assert formal["action"] == "WATCH"
    assert formal["candidates"][0]["strategy_version"] == version
    assert "STRATEGY_NOT_ADMITTED" in formal["candidates"][0]["selection_reasons"]
    assert formal["candidates"][0]["target_fraction"] is None
    assert simulated["action"] == "BUY"
    assert simulated["quantity"] == 100
    assert simulated["cash_reserved"] == "1105.01"
    assert simulated["strategy_version"] == version
    assert "PRICE_ONLY_SIMULATION" in simulated["reasons"]["P2"]
