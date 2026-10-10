"""Download issuer corporate-action originals from cninfo static host.

Targets the 2016-2023 dividend implementation announcements, the suspension
notices, termination of issuance, and the 2024 buyback set referenced by the
prior rights coverage (kept inside the allowed historical basis scope).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from curl_fetch import fetch  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
RAW.mkdir(exist_ok=True)

TARGETS = [
    # label, pdf URL
    ("2013_annual_equity_2013-07-18", "https://static.cninfo.com.cn/finalpage/2013-07-18/62845175.PDF"),
    ("2014_annual_equity_2014-07-24", "https://static.cninfo.com.cn/finalpage/2014-07-24/1200074589.PDF"),
    ("2015_annual_equity_2015-07-10", "https://static.cninfo.com.cn/finalpage/2015-07-10/1201268396.PDF"),
    ("2016_annual_equity_2016-08-05", "https://static.cninfo.com.cn/finalpage/2016-08-05/1202538463.PDF"),
    ("2016_suspension_2016-02-15", "https://static.cninfo.com.cn/finalpage/2016-02-16/1201981143.PDF"),
    ("2016_resumption_2016-02-25", "https://static.cninfo.com.cn/finalpage/2016-02-26/1202000598.PDF"),
    ("2017_annual_equity_2017-07-05", "https://static.cninfo.com.cn/finalpage/2017-07-06/1203684386.PDF"),
    ("2017_termination_2017-07-07", "https://static.cninfo.com.cn/finalpage/2017-07-08/1203689481.PDF"),
    ("2018_annual_equity_2018-07-18", "https://static.cninfo.com.cn/finalpage/2018-07-19/1205195306.PDF"),
    ("2019_annual_equity_2019-07-21", "https://static.cninfo.com.cn/finalpage/2019-07-22/1206466159.PDF"),
    ("2020_annual_equity_2020-07-08", "https://static.cninfo.com.cn/finalpage/2020-07-09/1208016044.PDF"),
    ("2021_annual_equity_2021-07-12", "https://static.cninfo.com.cn/finalpage/2021-07-13/1210467038.PDF"),
    ("2022_annual_equity_2022-07-15", "https://static.cninfo.com.cn/finalpage/2022-07-15/1214041661.PDF"),
    ("2023_annual_equity_2023-07-14", "https://static.cninfo.com.cn/finalpage/2023-07-14/1217292605.PDF"),
]

if __name__ == "__main__":
    receipts = []
    for name, url in TARGETS:
        r = fetch(url, timeout=60, max_bytes=32 * 1024 * 1024)
        body = r.pop("body")
        path = RAW / (r["sha256"] + ".bin")
        if path.exists() and path.read_bytes() != body:
            raise RuntimeError("SHA_COLLISION " + name)
        path.write_bytes(body)
        rec = {"name": name, "purpose": "issuer corporate-action original", "raw_file": path.name, **r}
        receipts.append(rec)
        print(f"  [{r['http_status']}] {r['bytes']:>8} {r['sha256'][:12]}  {name}")
    (HERE / "cninfo-pdf-receipts.json").write_text(
        json.dumps({"receipts": receipts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote cninfo-pdf-receipts.json", len(receipts))
