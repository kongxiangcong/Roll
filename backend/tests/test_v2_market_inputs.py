from datetime import date
from decimal import Decimal

from roll.market.inputs import read_inputs, sync_inputs


def test_historical_backfill_retries_only_missing_market_input_dates(tmp_path):
    class PartialSource(MarketSource):
        calls = []

        def turnover(self, symbol, days):
            self.calls.append(list(days))
            take = days[::2] if len(self.calls) == 1 else days
            return [(d, {"turnover_yuan": "100"}) for d in take]

    source = PartialSource()
    expected = source.calendar()
    for _ in range(3):
        status = sync_inputs(tmp_path, expected[0], expected[-1], groups=["turnover"],
                             source=source, missing_only=True)
    assert source.calls == [expected, expected[1::2]]
    row = next(r for r in status if r["series"] == "turnover")
    assert row["count"] == 4
    assert row["failed_dates"] == []


def test_expired_budget_is_distinct_from_source_timeout(monkeypatch):
    import requests
    from roll.market import akshare_timeout

    def unexpected_send(*args, **kwargs):
        raise AssertionError("expired budget must not send a request")

    monkeypatch.setattr(requests.Session, "send", unexpected_send)
    with akshare_timeout.bounded_requests(0):
        try:
            requests.get("https://example.invalid/")
        except akshare_timeout.RequestBudgetExpired:
            pass
        else:
            raise AssertionError("missing budget failure")


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


def test_daily_source_failure_is_isolated_and_exchange_calls_are_shared(tmp_path):
    from collections import Counter
    from roll.market.akshare_inputs import AkshareInputs

    class Frame:
        def __init__(self, rows): self.rows = rows
        def to_dict(self, _): return self.rows

    class SDK:
        calls = Counter()

        def fund_etf_scale_sse(self, date):
            self.calls["share",date] += 1
            if date == "20250722": raise TimeoutError()
            days = date[:4]+"-"+date[4:6]+"-"+date[6:]
            return Frame([{"基金代码":c,"统计日期":days,"基金份额":54810487699.99999} for c in ("510300","510500")])

        def fund_scale_daily_szse(self, **params):
            self.calls["sz",params["start_date"]] += 1
            return Frame([{"基金代码":"159915","日期":"2025-07-23","基金份额":100}])

        def stock_sse_deal_daily(self, date):
            if date == "20250722": raise TimeoutError()
            return Frame([{"单日情况":"成交金额","主板A":1,"科创板":1}])

        def stock_szse_summary(self, date):
            return Frame([{"证券类别":"主板A股","成交金额":3},{"证券类别":"创业板A股","成交金额":2}])

    source=AkshareInputs(SDK())
    result=sync_inputs(tmp_path,"2025-07-21","2025-07-23",source=source,
                       funds=["510300.SH","510500.SH","159915.SZ"],groups=["etf_shares","turnover"])
    assert source.sdk.calls["share","20250722"] == 1
    for symbol in ("510300.SH","510500.SH"):
        rows=read_inputs(tmp_path,"etf_shares",symbol)
        assert [r["trade_date"] for r in rows] == ["2025-07-21","2025-07-23"]
        assert all(r["shares"]=="54810487700" for r in rows)
        status=next(r for r in result if r["symbol"]==symbol)
        assert status["failed_dates"]==[{"trade_date":"2025-07-22","error":"TimeoutError"}]
    assert len(read_inputs(tmp_path,"etf_shares","159915.SZ"))==1
    assert [r["trade_date"] for r in read_inputs(tmp_path,"turnover","CN")]==["2025-07-21","2025-07-23"]
