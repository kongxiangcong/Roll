from datetime import date
from decimal import Decimal

from roll.market.inputs import read_inputs, sync_inputs


class MarketSource:
    def calendar(self):
        return ["2025-07-21", "2025-07-22", "2025-07-23", "2025-07-24"]

    def shares(self, symbol, days):
        history = {"2025-07-21": "92404387700", "2025-07-22": "92306287700",
                   "2025-07-24": "92300000000"}
        return [(day, {"shares": history[day]}) for day in days if day in history]

    def nav(self, symbol, days):
        return [(day, {"nav": "4.1929"}) for day in days]


def test_flow_uses_previous_trading_day_and_same_day_unit_nav(tmp_path):
    sync_inputs(tmp_path, "2025-07-21", "2025-07-24", groups=["etf_shares", "etf_nav"],
                source=MarketSource(), funds=["510300.SH"])
    rows = read_inputs(tmp_path, "etf_flow", "510300.SH")
    assert [(r["trade_date"], r["net_flow_yuan"]) for r in rows] == [
        ("2025-07-22", "-411323490.0000")]

def test_both_exchanges_money_units_and_retries_preserve_history(tmp_path):
    from roll.market.akshare_inputs import AkshareInputs

    class Frame:
        def __init__(self, rows):
            self.rows = rows

        def to_dict(self, orient):
            return self.rows

    class SDK:
        def tool_trade_date_hist_sina(self):
            return Frame([{"trade_date": date(2025, 7, 22)}])

        def stock_margin_sse(self, **params):
            return Frame([{"信用交易日期": "20250722", "融资融券余额": 979109268322}])

        def stock_margin_szse(self, **params):
            return Frame([{"融资融券余额": 9479.89}])

    source = AkshareInputs(SDK())
    run = lambda: sync_inputs(tmp_path, "2025-07-22", "2025-07-22", groups=["margin"], source=source)
    run()
    source.sdk.stock_margin_szse = lambda **params: Frame([])
    status = next(r for r in run() if r["series"] == "margin")
    assert status["last_error"] and status["last_success_at"] and status["last_date"] == "2025-07-22"
    assert Decimal(read_inputs(tmp_path, "margin", "CN")[0]["balance_yuan"]) == 1927098268322


def test_cli_syncs_raw_etf_bars_and_exports_the_same_observation(tmp_path, monkeypatch, capsys):
    import json
    import sys
    from types import SimpleNamespace

    from roll.cli import main

    class Frame:
        def __init__(self, rows):
            self.rows = rows

        def to_dict(self, orient):
            return self.rows

    sdk = SimpleNamespace(
        tool_trade_date_hist_sina=lambda: Frame([{"trade_date": date(2025, 7, 22)}]),
        fund_etf_hist_sina=lambda symbol: Frame([{
            "date": date(2025, 7, 22), "open": 4.158, "high": 4.2, "low": 4.111, "close": 4.19}]))
    monkeypatch.setitem(sys.modules, "akshare", sdk)
    prefix = ["--data-dir", str(tmp_path)]
    main(prefix + ["sync", "--market-inputs", "--group", "etf_bars", "--start", "2025-07-22",
                   "--end", "2025-07-22"])
    assert "etf_bars" in capsys.readouterr().out
    main(prefix + ["inputs", "etf_bars", "510300.SH"])
    assert json.loads(capsys.readouterr().out)["rows"] == [{
        "trade_date": "2025-07-22", "open": "4.158", "high": "4.2", "low": "4.111", "close": "4.19"}]
