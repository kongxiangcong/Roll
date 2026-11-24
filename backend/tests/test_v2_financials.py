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
