"""Primary collection for ticket 19 external evidence request (2026-10-09).

Fixed instrument SSE:600362. Candidate collection scope 2016-01-01..2023-12-31,
context 2015-10-01..2015-12-31. No post-2024 market observations.

Every response is written verbatim to work/raw/<sha256>.bin and receipted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from curl_fetch import fetch  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
RAW.mkdir(exist_ok=True)
RECEIPTS: list[dict] = []


def grab(name: str, url: str, purpose: str, headers: dict | None = None,
         timeout: int = 60, follow: bool = False, max_bytes: int = 32 * 1024 * 1024) -> dict:
    r = fetch(url, headers=headers, timeout=timeout, follow=follow, max_bytes=max_bytes)
    body = r.pop("body")
    path = RAW / (r["sha256"] + ".bin")
    if path.exists() and path.read_bytes() != body:
        raise RuntimeError("SHA_COLLISION_" + r["sha256"])
    path.write_bytes(body)
    rec = {"name": name, "purpose": purpose, "raw_file": path.name, **r}
    RECEIPTS.append(rec)
    print(f"  [{r['http_status']}] {r['bytes']:>9} {r['sha256'][:12]}  {name}")
    return rec


SOUHU_HEADERS = {"Referer": "https://q.stock.sohu.com/cn/600362/lshq.shtml"}
SSE_HEADERS = {"Referer": "https://www.sse.com.cn/"}

if __name__ == "__main__":
    print("== Sohu RAW daily (candidate scope + context) ==")
    grab("sohu_daily_20151001_20151231",
         "https://q.stock.sohu.com/hisHq?code=cn_600362&start=20151001&end=20151231&stat=1&order=D&period=d",
         "RAW daily OHLCV, context window", SOUHU_HEADERS)
    grab("sohu_daily_20160101_20231231",
         "https://q.stock.sohu.com/hisHq?code=cn_600362&start=20160101&end=20231231&stat=1&order=D&period=d",
         "RAW daily OHLCV, candidate scope", SOUHU_HEADERS, timeout=120)
    # per-year split so a single truncation cannot hide rows
    for y in range(2016, 2024):
        grab(f"sohu_daily_{y}",
             f"https://q.stock.sohu.com/hisHq?code=cn_600362&start={y}0101&end={y}1231&stat=1&order=D&period=d",
             f"RAW daily OHLCV year {y} (cross-check split)", SOUHU_HEADERS)

    print("== Sohu historical page (declares units/labels) ==")
    grab("sohu_history_page_600362",
         "https://q.stock.sohu.com/cn/600362/lshq.shtml",
         "Sohu history page labels/units evidence", SOUHU_HEADERS)

    print("== SSE official daily stock statistics ==")
    for d in ["2023-01-03", "2023-06-30", "2023-12-29", "2016-03-01", "2015-12-31"]:
        grab(f"sse_dailystat_{d}",
             f"https://query.sse.com.cn/commonQuery.do?sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_CJGK_MRGK_C&SEC_CODE=600362&TX_DATE={d}&TX_DATE_MON=&TX_DATE_YEAR=",
             f"SSE official daily statistics probe {d}", SSE_HEADERS)

    print("== SSE suspension (old + new endpoints) ==")
    grab("sse_suspension_20160216",
         "https://query.sse.com.cn/sseQuery/commonQuery.do?sqlId=COMMON_SSE_XXPL_JYTS_TFPXX_L&SEARCH_DATE=2016-02-16&isPagination=true&pageHelp.pageSize=100&pageHelp.pageNo=1&pageHelp.beginPage=1&pageHelp.endPage=1&pageHelp.cacheSize=1",
         "SSE suspension list 2016-02-16", SSE_HEADERS)
    grab("sse_suspension_range_2013_2025",
         "https://query.sse.com.cn/commonSoaQuery.do?sqlId=GW_PL_JYTS_TFPXX&productCode=600362&startStopDate=20130101&endStopDate=20251231&isPagination=true&pageHelp.pageSize=100&pageHelp.pageNo=1&pageHelp.beginPage=1&pageHelp.endPage=1&pageHelp.cacheSize=1",
         "SSE new suspension query 600362", SSE_HEADERS)

    print("== SSE company page (identity) ==")
    grab("sse_company_page_600362",
         "https://www.sse.com.cn/assortment/stock/list/info/company/index.shtml?COMPANY_CODE=600362",
         "SSE company identity page", SSE_HEADERS)

    out = HERE / "collection-receipts.json"
    out.write_text(json.dumps({"receipts": RECEIPTS}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out}  ({len(RECEIPTS)} receipts)")
