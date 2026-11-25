from decimal import Decimal

from roll.backtest import compare_sessions


DAYS = ["2025-07-21", "2025-07-22", "2025-07-23", "2025-07-24", "2025-07-25", "2025-07-28"]


def history():
    regimes = [("均衡", .6), ("均衡", .6), (None, None), ("均衡", .6), ("谨慎", .35), ("谨慎", .35)]
    return [{"trade_date": day, "regime": band, "position_cap": cap}
            for day, (band, cap) in zip(DAYS, regimes)]


def prices():
    return [{"trade_date": day, "open": "10", "close": close, "high": "10.1", "low": "8.5"}
            for day, close in zip(DAYS, ("10", "9.82", "8.7", "10", "10", "10"))]


def test_only_changed_valid_regime_trades_next_open_and_every_holding_day_counts():
    result = compare_sessions(history(), prices(), Decimal("100000"))
    strategy = result["strategy"]
    assert [(t["signal_date"], t["trade_date"], t["side"]) for t in strategy["trades"]] == [
        (DAYS[0], DAYS[1], "BUY"), (DAYS[4], DAYS[5], "SELL")]
    assert round(strategy["curve"][1]["exposure"], 3) == .596
    assert strategy["curve"][2]["shares"] == 6000
    assert strategy["metrics"]["maximum_drawdown"] > .078
    assert strategy["trades"][0]["price"] == "10.005"
    assert Decimal(strategy["trades"][0]["fee_yuan"]) == Decimal("18.61")
    sell = strategy["trades"][1]
    assert Decimal(sell["gross_yuan"]) == Decimal("25987.000")
    # 7.80 commission + 0.26 simulated transfer fee; no 12.99 stamp duty.
    assert Decimal(sell["fee_yuan"]) == Decimal("8.06")
    assert len(result["buy_hold"]["trades"]) == 1
    assert result["buy_hold"]["trades"][0]["trade_date"] == DAYS[0]

def test_unpriced_next_open_leaves_the_strategy_path_unknown_without_deferring_trade():
    bars = prices()
    bars[1] = {**bars[1], "open": None}
    result = compare_sessions(history(), bars)
    assert result["missing_prices"] == [{"trade_date": DAYS[1], "fields": ["open"]}]
    assert result["strategy"]["metrics"]["net_value"] is None
    assert all(row["nav_yuan"] is None for row in result["strategy"]["curve"][1:])
    assert result["strategy"]["trades"] == []
    assert result["buy_hold"]["metrics"]["net_value"] is not None


def test_missing_close_does_not_flatten_equity_or_hide_drawdown():
    bars = prices()
    bars[2] = {**bars[2], "close": None}
    result = compare_sessions(history(), bars)
    assert result["strategy"]["curve"][2]["nav_yuan"] is None
    assert result["strategy"]["curve"][3]["nav_yuan"] is not None
    assert result["strategy"]["metrics"]["maximum_drawdown"] is None

def test_cli_shows_independent_fit_and_test_windows_and_signal_coverage(tmp_path, capsys):
    import json
    from roll.cli import main
    from roll.market.inputs import sync_inputs

    class Source:
        def calendar(self):
            return ["2023-12-29", "2024-01-02", "2024-01-03"]

        def bars(self, symbol, days):
            return [(d, {"open": "10", "high": "11", "low": "9", "close": "10"}) for d in days]

    sync_inputs(tmp_path, "2023-12-29", "2024-01-03", groups=["etf_bars"], funds=["510300.SH"], source=Source())
    main(["--data-dir", str(tmp_path), "backtest", "--start", "2023-12-29", "--end", "2024-01-03"])
    report = json.loads(capsys.readouterr().out)
    assert report["symbol"] == "510300.SH"
    fit, test = report["periods"]
    assert (fit["period"], fit["sessions"], test["period"], test["sessions"]) == ("定权期", 1, "样本外", 2)
    assert test["valid_signals"] == 0 and test["missing_prices"] == []
    assert report["status"] == "无有效档位，当前历史数据不足以评价控仓效果"
    assert report["fees"]["sell_tax_rate"] == "0"
    assert test["dimension_coverage"]["funding"] == {"available_days": 0, "longest_gap_days": 2}
    assert test["strategy"]["status"] == "无有效档位，保持现金"
    assert test["buy_hold"]["trades"][0]["trade_date"] == "2024-01-02"


def test_one_price_up_limit_skips_the_buy_and_does_not_chase_it_the_next_day():
    bars = prices()
    bars[1] = {"trade_date": DAYS[1], "open": "11", "high": "11", "low": "11", "close": "11"}
    result = compare_sessions(history(), bars)
    assert result["strategy"]["skipped"][0]["trade_date"] == DAYS[1]
    assert [(t["signal_date"], t["trade_date"]) for t in result["strategy"]["trades"]] == [
        (DAYS[4], DAYS[5])]


def test_single_price_with_unverified_previous_close_is_not_assumed_executable():
    bars = prices()
    bars[0] = {"trade_date": DAYS[0], "open": "10", "high": "10", "low": "10", "close": "10"}
    result = compare_sessions(history(), bars)
    assert result["buy_hold"]["curve"][0]["nav_yuan"] is None
    assert result["buy_hold"]["trades"] == []
