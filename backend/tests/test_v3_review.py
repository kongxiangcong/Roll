from argparse import ArgumentParser
from decimal import Decimal
import io
import json
import sys

import pytest

from roll.v3.account_cli import register_account_commands
from roll.v3.market_cli import register as register_market
from roll.v3.plan_cli import register_plan_commands
from roll.v3.review_cli import register_review_commands
from roll.v3.strategy_cli import register as register_strategy


SYMBOL = "600362.SH"
DECISION = "2026-11-27T16:00:00+08:00"
NEXT_OPEN = "2026-11-30T09:30:00+08:00"
NEXT_CLOSE = "2026-11-30T16:00:00+08:00"


def cli(data_dir, *argv, payload=None):
    root = ArgumentParser()
    commands = root.add_subparsers(required=True)
    for register in (register_account_commands, register_market, register_plan_commands,
                     register_review_commands, register_strategy):
        register(commands)
    args = root.parse_args(argv)
    if payload is None:
        return args.handler(args, data_dir)
    original = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        return args.handler(args, data_dir)
    finally:
        sys.stdin = original


def seed_trend(tmp_path, *, opening=None):
    cli(tmp_path, "account", "init", payload={
        "cash": "2200", "available_cash": "2200", "effective_at": DECISION, "known_at": DECISION,
    })
    cli(tmp_path, "account", "budget", payload={
        "budget_id": "fixture-budget", "effective_at": DECISION, "known_at": DECISION,
        "cash_reserve": "0", "max_total_exposure": "1", "max_symbol_exposure": "1", "max_industry_exposure": "1",
    })
    strategy = cli(tmp_path, "strategy", "freeze", "--fast", "1", "--slow", "2", "--at",
                   "2026-11-26T15:05:00+08:00")["strategy"]["version"]
    rows = [
        {"series": "daily_bar", "symbol": SYMBOL, "trade_date": day, "source": "fixture",
         "available_at": f"{day}T15:05:00+08:00", "received_at": f"{day}T15:05:00+08:00",
         "payload": {"close": close, "prior_close": "10", "pre_close": "10", "trading_status": "trading"}}
        for day, close in (("2026-11-26", "10"), ("2026-11-27", "11"))
    ]
    if opening is not None:
        rows.append({
            "series": "daily_open", "symbol": SYMBOL, "trade_date": "2026-11-30", "source": "fixture",
            "available_at": NEXT_OPEN, "received_at": NEXT_OPEN, "payload": {
                "open": opening, "prior_close": "11", "pre_close": "11", "trading_status": "trading",
            },
        })
    path = tmp_path / "quotes.json"
    path.write_text(json.dumps(rows))
    cli(tmp_path, "market", "import", str(path))
    return strategy


def test_rehearsal_keeps_rejection_and_settles_the_frozen_shadow_once(tmp_path):
    strategy = seed_trend(tmp_path, opening="10.90")

    registration = cli(tmp_path, "review", "register", "--mode", "rehearsal", "--now", DECISION,
                       "--strategy-version", strategy, "--price-only")
    registration_id = registration["registration_id"]
    planned, = registration["plans"]
    assert planned["real_plan"]["action"] == "WATCH"
    assert planned["shadow_plan"]["action"] == "BUY"
    assert planned["shadow"] is None

    cli(tmp_path, "review", "outcome", registration_id, SYMBOL, "rejected",
        "--now", DECISION, "--reason", "暂缓交易")
    settled = cli(tmp_path, "review", "settle", registration_id, "--now", NEXT_OPEN)
    reviewed, = settled["plans"]
    assert reviewed["real_plan"] == planned["real_plan"]
    assert reviewed["actual"]["status"] == "REJECTED"
    assert reviewed["actual"]["events"][0]["reason"] == "暂缓交易"
    assert reviewed["shadow"]["status"] == "FILLED"
    assert reviewed["shadow"]["fill"]["quantity"] == 100
    assert reviewed["shadow"]["fill"]["price"] == "10.91"
    assert Decimal(reviewed["shadow"]["account"]["cash"]) == Decimal("1103.99")
    assert cli(tmp_path, "review", "settle", registration_id, "--now", NEXT_OPEN) == settled
    assert cli(tmp_path, "review", "show", registration_id, "--as-of", NEXT_OPEN) == settled
    assert [event["kind"] for event in cli(tmp_path, "account", "log", "--as-of", NEXT_CLOSE)] == ["BASELINE"]
