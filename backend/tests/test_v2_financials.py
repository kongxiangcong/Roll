from roll.market.financials import sync_financials, financial_light


def record(period, notice, **fields):
    return {"SECUCODE": "600362.SH", "REPORT_DATE": period, "NOTICE_DATE": notice,
            "UPDATE_DATE": notice, **fields}


class FinancialFeed:
    def __init__(self, indicators, cash):
        self.indicators = indicators
        self.cash = cash

    def stock_financial_analysis_indicator_em(self, *, symbol, indicator):
        assert symbol == "600362.SH" and indicator == "按报告期"
        return self.indicators

    def stock_cash_flow_sheet_by_report_em(self, *, symbol):
        assert symbol == "SH600362"
        return self.cash


def test_only_disclosed_versions_enter_replay(tmp_path):
    period = "2025-03-31"
    def metrics(notice, revenue, profit):
        return record(period, notice, TOTALOPERATEREVETZ=revenue, KCFJCXSYJLRTZ=profit, ZCFZL=75)
    feed = FinancialFeed([metrics("2025-04-25", -10, -21)], [record(period,"2025-04-25", NETCASH_OPERATE=-20)])
    sync_financials(tmp_path, ["600362.SH"], sdk=feed)
    feed.indicators = [metrics("2025-05-12", -11, -21)]
    sync_financials(tmp_path, ["600362.SH"], sdk=feed)
    sync_financials(tmp_path, ["600362.SH"], sdk=feed)
    assert financial_light(tmp_path,"600362.SH","2025-04-24")["status"] == "unknown"
    first = financial_light(tmp_path,"600362.SH","2025-05-11")
    assert first["report_period"] == period and first["status"] == "green"
    corrected = financial_light(tmp_path,"600362.SH","2025-05-12")
    assert corrected["status"] == "red" and corrected["announce_date"] == "2025-05-12"
    assert first["versions"] != corrected["versions"]


def test_cashflow_uses_adjacent_quarters_and_starts_again_in_january(tmp_path):
    def metrics(period, notice, debt=76):
        return record(period, notice, TOTALOPERATEREVETZ=-11, KCFJCXSYJLRTZ=-20, ZCFZL=debt)
    data = [("2024-09-30","2024-10-30", 100), ("2024-12-31","2025-03-21",90),
            ("2025-03-31","2025-04-25",-2), ("2025-06-30","2025-07-29",-5),
            ("2025-12-31","2026-03-22",-30)]
    feed = FinancialFeed([metrics(p,n,75 if p=="2025-06-30" else 76) for p,n,c in data],
                         [record(p,n,NETCASH_OPERATE=c) for p,n,c in data])
    sync_financials(tmp_path,["600362.SH"],sdk=feed)
    q1 = financial_light(tmp_path,"600362.SH","2025-04-25")
    assert q1["cashflow_quarter_yuan"] == "-2" and q1["prior_cashflow_quarter_yuan"] == "-10"
    assert q1["status"] == "red" and len(q1["reasons"]) == 1
    q2 = financial_light(tmp_path,"600362.SH","2025-07-29")
    assert q2["cashflow_quarter_yuan"] == "-3" and q2["status"] == "green"
    q4 = financial_light(tmp_path,"600362.SH","2026-03-22")
    assert q4["cashflow_quarter_yuan"] is None and q4["prior_cashflow_quarter_yuan"] is None
    assert q4["status"] == "unknown" and "上季经营现金流" in q4["missing"]


def test_latest_update_without_matching_disclosure_cannot_be_backdated(tmp_path):
    row = record("2025-03-31","2025-04-25",TOTALOPERATEREVETZ=-11,KCFJCXSYJLRTZ=-21,ZCFZL=50)
    row["UPDATE_DATE"] = "2025-05-12"
    feed = FinancialFeed([row], [])
    sync_financials(tmp_path,["600362.SH"],sdk=feed)
    replay = financial_light(tmp_path,"600362.SH","2025-05-13")
    assert replay["status"] == "unknown" and replay["report_period"] is None


def test_unverified_revision_cannot_supersede_an_established_disclosure(tmp_path):
    initial = record("2025-03-31","2025-04-25",TOTALOPERATEREVETZ=12,KCFJCXSYJLRTZ=30,ZCFZL=50)
    feed = FinancialFeed([initial], [])
    sync_financials(tmp_path,["600362.SH"],sdk=feed)
    feed.indicators = [{**initial,"TOTALOPERATEREVETZ":-11,"KCFJCXSYJLRTZ":-21,"UPDATE_DATE":"2025-05-12"}]
    sync_financials(tmp_path,["600362.SH"],sdk=feed)
    visible=financial_light(tmp_path,"600362.SH","2025-07-01")
    assert visible["status"]=="green" and visible["announce_date"]=="2025-04-25"
    stale=financial_light(tmp_path,"600362.SH","2025-09-01")
    assert stale["status"]=="unknown" and stale["report_period"] is None
    assert "2025-06-30" in stale["missing"][0]


def test_known_new_disclosure_blocks_old_green_without_backfilling_revision(tmp_path):
    fields = dict(TOTALOPERATEREVETZ=12, KCFJCXSYJLRTZ=30, ZCFZL=50)
    last_year = record("2024-12-31", "2025-04-20", **fields)
    revised = record("2025-03-31", "2025-04-29", **fields)
    revised["UPDATE_DATE"] = "2026-04-29"
    sync_financials(tmp_path, ["600362.SH"], sdk=FinancialFeed([last_year, revised], []))
    assert financial_light(tmp_path, "600362.SH", "2025-04-28")["status"] == "green"
    result = financial_light(tmp_path, "600362.SH", "2025-04-29")
    assert result["status"] == "unknown" and result["report_period"] is None
    assert result["revenue_yoy_pct"] is None
    assert result["missing"] == ["2025-03-31 财报已披露，但当时版本未经核实"]


def test_production_financial_sync_bounds_sdk_http_calls(tmp_path, monkeypatch):
    import sys
    import requests
    from types import SimpleNamespace
    timeouts = []

    def transport(self, request, **kwargs):
        timeouts.append(kwargs["timeout"])
        raise requests.ReadTimeout()

    def sdk_call(**kwargs):
        requests.get("https://example.invalid/")

    monkeypatch.setattr(requests.Session, "send", transport)
    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(
        stock_financial_analysis_indicator_em=sdk_call, stock_cash_flow_sheet_by_report_em=sdk_call))
    result = sync_financials(tmp_path, ["600362.SH"])
    assert len(timeouts) == 2 and all(0 < value <= 22 for value in timeouts)
    assert all(row["error"] for row in result)
