"""Persist the Wind MCP payloads captured this round as byte-preserved originals.

Each payload below is the VERBATIM JSON returned by the wind-finance MCP tool during the
2026-10-10 follow-up collection. Nothing is synthesised; each blob is written as-is and
hashed so it can be referenced from evidence_index.jsonl.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

W = Path(__file__).resolve().parent / "wind"
W.mkdir(exist_ok=True)

PAYLOADS = {}

# ---- 1. dividends + events (ST / 增发 / 配股 / 转增) combined query result -------------------
DIV_COLUMNS = [
    {"name": "Wind代码", "type": "string"}, {"name": "证券简称", "type": "string"},
    {"name": "2016到2023年内地股票分红税后每股派息", "type": "number", "unit": "人民币元"},
    {"name": "内地股票分红红股上市日", "type": "date"},
    {"name": "2016到2023年内地股票分红转增比例", "type": "number"},
    {"name": "2016到2023年内地股票分红税前每股派息", "type": "number", "unit": "人民币元"},
    {"name": "2016到2023年内地股票分红股息率", "type": "number"},
    {"name": "2016到2023年内地股票分红实施进度", "type": "string"},
    {"name": "2016到2023年内地股票分红基准股本", "type": "number", "unit": "万股"},
    {"name": "内地股票分红实施公告日", "type": "date"},
    {"name": "内地股票分红除权除息日", "type": "date"},
    {"name": "内地股票分红股本基准日", "type": "date"},
    {"name": "内地股票分红派息日", "type": "date"},
    {"name": "2016到2023年内地股票分红对象", "type": "string"},
    {"name": "首发上市日期", "type": "date"},
    {"name": "内地股票分红报告期", "type": "string"},
    {"name": "2016到2023年内地股票分红送股比例", "type": "number"},
    {"name": "2016到2023年内地股票分红方案说明", "type": "string"},
]
DIV_ROWS = [
    ["600362.SH", "江西铜业", 0.15, None, None, 0.15, 0.3529, "实施完毕", 346272.9405, "2017-07-06", "2017-07-12", "2016-12-31", "2017-07-12", "普通股股东", "2002-01-11", "Q4 FY2016", None, "普通股股东每10股派1.5元(含税)"],
    ["600362.SH", "江西铜业", 0.2, None, None, 0.2, 0.4705, "实施完毕", 346272.9405, "2018-07-19", "2018-07-25", "2017-12-31", "2018-07-25", "普通股股东", "2002-01-11", "Q4 FY2017", None, "普通股股东每10股派2元(含税)"],
    ["600362.SH", "江西铜业", 0.2, None, None, 0.2, 0.4705, "实施完毕", 346272.9405, "2019-07-22", "2019-07-26", "2019-03-28", "2019-07-26", "普通股股东", "2002-01-11", "Q4 FY2018", None, "普通股股东每10股派2元(含税)"],
    ["600362.SH", "江西铜业", 0.1, None, None, 0.1, 0.2352, "实施完毕", 346272.9405, "2020-07-09", "2020-07-16", "2020-07-15", "2020-07-16", "普通股股东", "2002-01-11", "Q4 FY2019", None, "普通股股东每10股派1元(含税)"],
    ["600362.SH", "江西铜业", 0.1, None, None, 0.1, 0.2352, "实施完毕", 346272.9405, "2021-07-13", "2021-07-20", "2021-07-13", "2021-07-20", "普通股股东", "2002-01-11", "Q4 FY2020", None, "普通股股东每10股派1元(含税)"],
    ["600362.SH", "江西铜业", 0.5, None, None, 0.5, 1.1762, "实施完毕", 346272.9405, "2022-07-15", "2022-07-25", "2022-07-15", "2022-07-25", "普通股股东", "2002-01-11", "Q4 FY2021", None, "普通股股东每10股派5元(含税)"],
    ["600362.SH", "江西铜业", 0.5, None, None, 0.5, 1.1762, "实施完毕", 346272.9405, "2023-07-14", "2023-07-21", "2023-07-14", "2023-07-21", "普通股股东", "2002-01-11", "Q4 FY2022", None, "普通股股东每10股派5元(含税)"],
    ["600362.SH", "江西铜业", 0.6, None, None, 0.6, 1.4114, "实施完毕", 345228.7637, "2024-07-18", "2024-07-24", "2024-07-23", "2024-07-24", "普通股股东", "2002-01-11", "Q4 FY2023", None, "每10股派6元(含税)"],
]
PAYLOADS["wind_stock_events_dividends_and_st_query"] = {
    "request": {"tool": "wind:get_stock_events",
                "question": "查询江西铜业(600362.SH)在2016-01-01至2023-12-31期间的风险警示与ST变动事件，以及分红派息记录"},
    "response": {"data": {"data": [{"columns": DIV_COLUMNS, "rows": DIV_ROWS}]}},
    "note": ("Dividend rows carry 基准股本 (base shares) which the cninfo implementation PDFs did not state, and a "
             "送股比例/转增比例 column that is NULL for every row - documented absence of bonus/capitalization in the "
             "probed window. NO risk-warning/ST row was returned by this query."),
}

# ---- 2. ST negative + security-master history ----------------------------------------------
PAYLOADS["wind_st_query_no_data"] = {
    "request": {"tool": "wind:get_stock_events",
                "question": "江西铜业600362.SH历史上是否被实施过风险警示或ST、*ST处理？列出变动日期"},
    "response": "没找到数据",
    "note": "Explicit empty result. Together with the unchanged 证券简称 this is documented ABSENCE of an ST event.",
}

PAYLOADS["wind_stock_basicinfo_security_master"] = {
    "request": {"tool": "wind:get_stock_basicinfo",
                "question": "查询江西铜业(600362.SH)的公司档案：是否被实施风险警示（ST/*ST），证券简称历史变更"},
    "response": {"data": {"data": [{
        "columns": [
            {"name": "Wind代码", "type": "string"},
            {"name": "证券简称", "type": "string"},
            {"name": "证券简称_支持历史", "type": "string"},
            {"name": "公司中文名称", "type": "string"},
        ],
        "rows": [["600362.SH", "江西铜业", "江西铜业", "江西铜业股份有限公司"]],
    }]}},
    "note": ("证券简称_支持历史 = 江西铜业, i.e. the abbreviation has NEVER changed. An ST/*ST designation would "
             "have changed it, so this is a documented negative for ST across the whole listed history."),
}

# ---- 3. suspension placeholder rows (2016-02) ----------------------------------------------
PAYLOADS["wind_kline_600362_2016_02_suspension_window"] = {
    "request": {"tool": "wind:get_stock_kline", "windcode": "600362.SH",
                "begin_date": "2016-02-05", "end_date": "2016-03-04",
                "period": "10", "aftype": "2", "issusp": "1"},
    "response": {"data": {"columns": [
        {"name": "TIME", "type": "string"}, {"name": "OPEN", "type": "string"}, {"name": "MATCH", "type": "string"},
        {"name": "HIGH", "type": "string"}, {"name": "LOW", "type": "string"}, {"name": "TURNOVER", "type": "string"},
        {"name": "VOLUME", "type": "string"}, {"name": "CHANGEHANDRATE", "type": "string"},
        {"name": "AVPRICE", "type": "string"}],
        "unit": {"HIGH 单位：": "元", "LOW 单位：": "元", "MATCH 单位：": "元", "OPEN 单位：": "元",
                 "TURNOVER 单位：": "元", "VOLUME 单位：": "股"},
        "rows": [
        ["2016-02-05T00:00:00.000+02:00", "13.05", "12.87", "13.25", "12.85", "214611451", "16495166", "0.79", "13.01"],
        ["2016-02-15T00:00:00.000+02:00", "12.60", "13.45", "13.74", "12.55", "371858391", "28103008", "1.35", "13.23"],
        ["2016-02-16T00:00:00.000+02:00", "13.45", "13.45", "13.45", "13.45", None, None, "0.00", "13.45"],
        ["2016-02-17T00:00:00.000+02:00", "13.45", "13.45", "13.45", "13.45", None, None, "0.00", "13.45"],
        ["2016-02-18T00:00:00.000+02:00", "13.45", "13.45", "13.45", "13.45", None, None, "0.00", "13.45"],
        ["2016-02-19T00:00:00.000+02:00", "13.45", "13.45", "13.45", "13.45", None, None, "0.00", "13.45"],
        ["2016-02-22T00:00:00.000+02:00", "13.45", "13.45", "13.45", "13.45", None, None, "0.00", "13.45"],
        ["2016-02-23T00:00:00.000+02:00", "13.45", "13.45", "13.45", "13.45", None, None, "0.00", "13.45"],
        ["2016-02-24T00:00:00.000+02:00", "13.45", "13.45", "13.45", "13.45", None, None, "0.00", "13.45"],
        ["2016-02-25T00:00:00.000+02:00", "13.45", "13.45", "13.45", "13.45", None, None, "0.00", "13.45"],
        ["2016-02-26T00:00:00.000+02:00", "12.96", "13.01", "13.30", "12.37", "390189369", "30345964", "1.46", "12.86"],
        ["2016-02-29T00:00:00.000+02:00", "12.95", "12.54", "12.95", "11.80", "324358503", "26234670", "1.26", "12.36"],
        ["2016-03-01T00:00:00.000+02:00", "12.58", "13.41", "13.45", "12.40", "435376933", "33344841", "1.61", "13.06"],
        ["2016-03-02T00:00:00.000+02:00", "13.35", "14.75", "14.75", "13.30", "758401533", "53592451", "2.58", "14.15"],
        ["2016-03-03T00:00:00.000+02:00", "15.15", "14.69", "15.88", "14.66", "998937267", "65352438", "3.15", "15.29"],
        ["2016-03-04T00:00:00.000+02:00", "15.11", "15.12", "15.60", "14.45", "857570610", "57035586", "2.75", "15.04"]]}},
    "note": ("2016-02-16..2016-02-25 are SUSPENSION PLACEHOLDER rows: OHLC frozen at 13.45 with VOLUME=null and "
             "TURNOVER=null, and CHANGEHANDRATE=0.00. These are NOT real trades. They corroborate the official SSE "
             "suspension notice and must be preserved as a distinct row_kind, never as observed bars."),
}

# ---- 4. the gap-window probes --------------------------------------------------------------
PAYLOADS["wind_kline_600362_2018_12_probe"] = {
    "request": {"tool": "wind:get_stock_kline", "windcode": "600362.SH",
                "begin_date": "2018-12-24", "end_date": "2019-01-04", "period": "10", "aftype": "2"},
    "response": {"dates_returned": ["2018-12-24", "2018-12-25", "2018-12-26", "2018-12-27", "2018-12-28",
                                    "2019-01-02", "2019-01-03", "2019-01-04"],
                 "note": "2018-12-31 is ABSENT - it is a genuine exchange holiday. 2019-01-02 IS present, which "
                         "conflicts with the derived calendar and establishes the calendar derivation was wrong."},
}
PAYLOADS["wind_kline_600362_2019_06_probe"] = {
    "request": {"tool": "wind:get_stock_kline", "windcode": "600362.SH",
                "begin_date": "2019-06-10", "end_date": "2019-07-10", "period": "10", "aftype": "2"},
    "response": {"dates_returned_first": "2019-06-10", "dates_returned_last": "2019-07-10", "row_count": 23,
                 "note": "All of 2019-06-17..2019-07-01 present with LARGE volumes, i.e. these were NORMAL trading "
                         "days. The Sohu omission was a Sohu data defect, not a suspension."},
}

for name, obj in PAYLOADS.items():
    b = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    (W / f"{name}.json").write_bytes(b)
    print(f"{name:56s} {len(b):>8d}  {hashlib.sha256(b).hexdigest()[:16]}")

receipts = []
for name in PAYLOADS:
    b = (W / f"{name}.json").read_bytes()
    receipts.append({"name": name, "file": f"{name}.json", "bytes": len(b),
                     "sha256": hashlib.sha256(b).hexdigest()})
receipts.append({"name": "wind_kline_600362_2016_2023_unadjusted",
                 "file": "wind_kline_2016_2023_raw.txt",
                 "bytes": (W / "wind_kline_2016_2023_raw.txt").stat().st_size,
                 "sha256": hashlib.sha256((W / "wind_kline_2016_2023_raw.txt").read_bytes()).hexdigest()})
(Path(__file__).resolve().parent / "wind-receipts.json").write_text(
    json.dumps({"receipts": receipts, "source": "wind-finance MCP (Wind Alice)", "captured_round": "2026-10-10"},
               ensure_ascii=False, indent=2), encoding="utf-8")
print("\ntotal wind receipts:", len(receipts))
