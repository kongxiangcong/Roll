"""Collect historical trading-rule / tax / fee policy originals applicable to 2016-2023.

Re-fetch official policy pages so the delivery package is self-contained. Each is
recorded with its own SHA; publication vs effective dates come from the text.
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

TARGETS = [
    ("fee_2015_sse_csdc_joint",
     "https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988866.shtml"),
    ("transfer_fee_2022_chinaclear_official",
     "http://www.chinaclear.cn/zdjs/gszb/202204/f89e788c65a241e88e7f0d0348de586f.shtml"),
    ("stamp_tax_2008_mof",
     "https://www.mof.gov.cn/zhengwuxinxi/caizhengxinwen/200809/t20080919_76432.htm"),
    ("stamp_tax_2023_mof_announcement",
     "https://szs.mof.gov.cn/zhengcefabu/202308/t20230827_3904226.htm"),
    ("closing_auction_2018_sse_rule",
     "https://www.sse.com.cn/lawandrules/sselawsrules/repeal/rules/c/c_20210531_5478087.shtml"),
    ("handling_fee_2023_sse",
     "https://www.sse.com.cn/home/component/news/c/c_20230818_5725376.shtml"),
    ("dividend_tax_2012_mof_explainer",
     "https://www.mof.gov.cn/zhengwuxinxi/caizhengxinwen/201211/t20121116_697327.htm"),
    ("dividend_tax_2015_mof_101",
     "https://m.mof.gov.cn/czxw/201509/t20150907_1452683.htm"),
    ("dividend_tax_2015_mof_interpretation",
     "https://szs.mof.gov.cn/zhengcejiedu/201509/t20150909_1455696.htm"),
]

if __name__ == "__main__":
    receipts = []
    for name, url in TARGETS:
        r = fetch(url, timeout=60, follow=True, max_bytes=32 * 1024 * 1024)
        body = r.pop("body")
        path = RAW / (r["sha256"] + ".bin")
        if path.exists() and path.read_bytes() != body:
            raise RuntimeError("SHA_COLLISION " + name)
        path.write_bytes(body)
        rec = {"name": name, "purpose": "historical rule/tax/fee policy original", "raw_file": path.name, **r}
        receipts.append(rec)
        print(f"  [{r['http_status']}] {r['bytes']:>8} {r['sha256'][:12]}  {name}")
    (HERE / "rules-receipts.json").write_text(
        json.dumps({"receipts": receipts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote rules-receipts.json", len(receipts))
