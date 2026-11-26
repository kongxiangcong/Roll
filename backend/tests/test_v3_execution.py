import argparse
import io
import json
import sys

import pytest

from roll.v3.account_cli import register_account_commands
from roll.v3.execution_cli import register_execution_commands
from roll.v3.market_cli import register as register_market_commands


SYMBOL = "600362.SH"
CLOSE = "2025-09-30T16:00:00+08:00"
SESSION = "2025-10-09"
OPEN = f"{SESSION}T09:30:00+08:00"


def command(data_dir, monkeypatch, *args, payload=None):
    if payload is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(required=True)
    register_account_commands(commands)
    register_market_commands(commands)
    register_execution_commands(commands)
    options = parser.parse_args(args)
    result = options.handler(options, data_dir)
    return json.loads(json.dumps(result, default=str))


def initialize(data_dir, monkeypatch, **changes):
    command(data_dir, monkeypatch, "account", "init", payload={
        "cash": "5010", "available_cash": "2070", "effective_at": CLOSE, "known_at": CLOSE, **changes,
    })
    return command(data_dir, monkeypatch, "account", "show", "--as-of", CLOSE)["snapshot_id"]


def market(data_dir, monkeypatch, trade_date=SESSION, opening=None, daily_bar=None, symbol=SYMBOL):
    trade_date = str(trade_date)
    quote = {
        "open": "10.28", "prior_close": "10.60", "pre_close": "10.20",
        "trading_status": "trading", **(opening or {}),
    }
    start = {
        "symbol": symbol, "trade_date": trade_date, "source": "exchange",
        "source_ref": "frozen-exchange-opening",
        "unit": {"price": "CNY/share"},
    }

    def observation(series, clock, payload):
        time = f"{trade_date}T{clock}:00+08:00"
        return {**start, "series": series, "payload": payload, "available_at": time,
                "available_evidence": "timestamped-exchange-file", "received_at": time}

    incoming = data_dir / "opening.json"
    incoming.write_text(json.dumps([
        observation("daily_open", "09:30", quote),
        observation("daily_bar", "15:05", {**quote, "high": "10.90", "low": "9.88",
                                           "close": "10.61", **(daily_bar or {})}),
    ]), encoding="utf-8")
    command(data_dir, monkeypatch, "market", "import", str(incoming))
    return command(data_dir, monkeypatch, "market", "freeze", symbol, "--start", trade_date, "--end", trade_date,
                   "--as-of", f"{trade_date}T16:00:00+08:00")["snapshot_id"]


def simulate(data_dir, monkeypatch, account, snapshot, **intent):
    return command(data_dir, monkeypatch, "execution", "simulate",
                   "--account-snapshot", account, "--market-snapshot", snapshot, payload={
                       "intent_id": "plan-a", "symbol": SYMBOL, "decision_at": CLOSE,
                       "side": "BUY", "quantity": 350, **intent,
                   })


def test_next_open_after_exchange_holiday_sizes_the_fill_and_reconciles_cash(tmp_path, monkeypatch):
    account = initialize(tmp_path, monkeypatch)
    snapshot = market(tmp_path, monkeypatch)

    result = simulate(tmp_path, monkeypatch, account, snapshot)

    assert result["session"] == SESSION
    assert (result["status"], result["reason"]) == ("PARTIAL", "INSUFFICIENT_CASH")
    assert result["fill"]["quantity"] == 200
    assert result["fill"]["price"] == "10.29"
    assert result["fill"]["gross"] == "2058.00"
    assert result["fill"]["fee"] == "5.02"
    assert result["account"]["cash"] == "2946.98"
    assert result["account"]["available_cash"] == "6.98"
    lot, = result["account"]["lots"]
    assert (lot["cost"], lot["acquired_on"], lot["sellable_on"]) == ("2063.02", SESSION, "2025-10-10")
    assert result["account"]["known_sellable"] == {SYMBOL: 0}


def test_opening_reference_close_drives_directional_limits_without_post_open_prices(tmp_path, monkeypatch):
    account = initialize(tmp_path, monkeypatch, lots=[
        {"lot_id": "existing", "symbol": SYMBOL, "quantity": 200, "known_sellable": 200, "cost": "3000"},
    ])
    opening = {"open": "26.07", "prior_close": "24.40", "pre_close": "23.70"}
    first = market(tmp_path, monkeypatch, opening=opening)
    revised = market(tmp_path, monkeypatch, opening=opening,
                     daily_bar={"high": "26.07", "low": "25.00", "close": "25.90"})

    for snapshot in (first, revised):
        buy = simulate(tmp_path, monkeypatch, account, snapshot, quantity=100)
        assert (buy["status"], buy["reason"], buy["fill"]) == ("UNFILLED", "LIMIT_QUEUE_UNCONFIRMED", None)
        assert buy["opening"]["prior_close"] == "24.40"
        assert buy["opening"]["pre_close"] == "23.70"

    sales = [simulate(tmp_path, monkeypatch, account, snapshot, side="SELL", quantity=100)
             for snapshot in (first, revised)]
    assert sales[0]["fill"] == sales[1]["fill"]
    assert sales[0]["fill"]["price"] == "26.06"
    assert sales[0]["fill"]["quantity"] == 100
    assert sales[0]["fill"]["fee"] == "6.33"
    assert sales[0]["account"]["cash"] == "7609.67"
    assert sales[0]["account"]["lots"][0]["cost"] == "1500"


def test_sell_uses_confirmed_lots_and_enforces_odd_lot_quantity(tmp_path, monkeypatch):
    initialize(tmp_path, monkeypatch, lots=[
        {"lot_id": "existing", "symbol": SYMBOL, "quantity": 150, "known_sellable": 150, "cost": "1500"},
    ])
    command(tmp_path, monkeypatch, "account", "fill", payload={
        "event_id": "morning-buy", "symbol": SYMBOL, "side": "BUY", "quantity": 100,
        "price": "10.28", "fee": "5.01", "effective_at": OPEN, "known_at": OPEN,
    })
    account = command(tmp_path, monkeypatch, "account", "show", "--as-of", OPEN)
    snapshot = market(tmp_path, monkeypatch)

    assert account["known_sellable"] == {SYMBOL: 150}
    blocked = simulate(tmp_path, monkeypatch, account["snapshot_id"], snapshot, side="SELL", quantity=30)
    assert (blocked["status"], blocked["reason"]) == ("UNFILLED", "ORDER_QUANTITY")

    sold = simulate(tmp_path, monkeypatch, account["snapshot_id"], snapshot, side="SELL", quantity=250)
    assert (sold["status"], sold["reason"]) == ("PARTIAL", "INSUFFICIENT_SELLABLE_SHARES")
    assert sold["fill"]["quantity"] == 150
    assert sold["account"]["known_sellable"] == {SYMBOL: 0}
    remaining, = sold["account"]["lots"]
    assert (remaining["source_event_id"], remaining["cost"]) == ("morning-buy", "1033.01")


def test_star_market_uses_twenty_percent_limit_and_one_share_increments(tmp_path, monkeypatch):
    symbol = "688001.SH"
    account = initialize(tmp_path, monkeypatch, cash="10000", available_cash="10000")
    snapshot = market(tmp_path, monkeypatch, opening={"open": "11.50", "pre_close": "10.00"}, symbol=symbol)

    result = simulate(tmp_path, monkeypatch, account, snapshot, symbol=symbol, quantity=203)

    assert result["status"] == "FILLED"
    assert result["fill"]["quantity"] == 203
    assert result["fill"]["price"] == "11.51"


@pytest.mark.parametrize(("opening", "intent", "reason"), [
    ({"trading_status": "suspended", "open": None}, {}, "SUSPENDED"),
    ({}, {"side": "SELL"}, "NO_SELLABLE_SHARES"),
    ({}, {"limit_price": "10.28"}, "ORDER_LIMIT_NOT_MET"),
    ({"open": "9.18"}, {"side": "SELL"}, "LIMIT_QUEUE_UNCONFIRMED"),
])
def test_unfilled_open_keeps_frozen_intent_and_account(tmp_path, monkeypatch, opening, intent, reason):
    account = initialize(tmp_path, monkeypatch)
    snapshot = market(tmp_path, monkeypatch, opening=opening)

    result = simulate(tmp_path, monkeypatch, account, snapshot, **intent)

    assert (result["status"], result["reason"], result["fill"]) == ("UNFILLED", reason, None)
    assert result["intent"]["intent_id"] == "plan-a"
    assert result["intent"]["quantity"] == 350
    assert result["account"]["snapshot_id"] == account


@pytest.mark.parametrize(("decision_day", "day", "status"), [
    ("2026-07-02", "2026-07-03", "UNFILLED"),
    ("2026-07-03", "2026-07-06", "FILLED"),
])
def test_main_board_warning_uses_limit_effective_on_execution_date(tmp_path, monkeypatch,
                                                                   decision_day, day, status):
    account = initialize(tmp_path, monkeypatch)
    snapshot = market(tmp_path, monkeypatch, trade_date=day,
                      opening={"open": "10.50", "pre_close": "10.00", "risk_warning": True})

    result = simulate(tmp_path, monkeypatch, account, snapshot, quantity=100,
                      decision_at=f"{decision_day}T16:00:00+08:00")

    assert result["status"] == status
