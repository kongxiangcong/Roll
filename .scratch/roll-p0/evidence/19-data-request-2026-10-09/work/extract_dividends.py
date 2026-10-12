"""Extract dividend implementation parameters from the cninfo PDF originals (robust)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
recs = json.loads((HERE / "cninfo-pdf-receipts.json").read_text(encoding="utf-8"))["receipts"]

DIV = [r for r in recs if "annual_equity" in r["name"]]


def norm(m):
    if not m:
        return None
    return f"{m[0]}-{int(m[1]):02d}-{int(m[2]):02d}"


out = []
for r in DIV:
    p = HERE / "raw" / r["raw_file"]
    rd = PdfReader(str(p))
    pages = [pg.extract_text() or "" for pg in rd.pages]
    txt = "\n".join(pages)
    rec = {"name": r["name"], "sha256": r["sha256"], "bytes": r["bytes"], "pages": len(pages),
           "raw_file": r["raw_file"]}
    # cash per share (both formats)
    m = re.search(r"每股(?:现金红利|派发现金红利|分配比例)[^\d]{0,20}?([\d.]+)\s*元", txt) \
        or re.search(r"每股现金红利人民[币]*\s*([\d.]+)\s*元", txt) \
        or re.search(r"A\s*股每股现金红利\s*([\d.]+)\s*元", txt)
    rec["cash_per_share_yuan"] = m.group(1) if m else None
    # dates - try inline forms
    dates = re.findall(r"(\d{4})\s*[/年]\s*(\d{1,2})\s*[/月]\s*(\d{1,2})\s*日?", txt)
    di = [f"{a}-{int(b):02d}-{int(c):02d}" for a, b, c in dates]
    # explicit labelled
    def labelled(*pats):
        for pat in pats:
            m = re.search(pat, txt)
            if m:
                return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        return None
    rec["record_date"] = labelled(r"股权登记日[（(]?[^）)]*[）)]?[：:]?\s*(\d{4})\s*[/年]\s*(\d{1,2})\s*[/月]\s*(\d{1,2})")
    rec["ex_date"] = labelled(r"除权（息）日\s*(\d{4})\s*[/年]\s*(\d{1,2})\s*[/月]\s*(\d{1,2})",
                              r"除息日[：:]?\s*(\d{4})\s*[/年]\s*(\d{1,2})\s*[/月]\s*(\d{1,2})")
    rec["payment_date"] = labelled(r"现金红利发放日\s*(\d{4})\s*[/年]\s*(\d{1,2})\s*[/月]\s*(\d{1,2})",
                                   r"现金红利发放日[：:]?\s*(\d{4})\s*[/年]\s*(\d{1,2})\s*[/月]\s*(\d{1,2})")
    # fallback: Ｙ股 rows "Ａ股 2019/7/25 － 2019/7/26 2019/7/26"
    if not rec["record_date"]:
        m = re.search(r"[ＡA]\s*股\s*(\d{4})/(\d{1,2})/(\d{1,2})\s*[－\-—]+\s*(\d{4})/(\d{1,2})/(\d{1,2})\s*(\d{4})/(\d{1,2})/(\d{1,2})", txt)
        if m:
            rec["record_date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            rec["ex_date"] = f"{m.group(4)}-{int(m.group(5)):02d}-{int(m.group(6)):02d}"
            rec["payment_date"] = f"{m.group(7)}-{int(m.group(8)):02d}-{int(m.group(9)):02d}"
    m = re.search(r"以[^。]*?总股本\s*([\d,]+)\s*股为基数", txt)
    rec["base_shares"] = m.group(1).replace(",", "") if m else None
    rec["mentions_bonus_or_capitalization"] = bool(re.search(r"送股|资本公积(金)?转增", txt))
    rec["differential"] = ("差异化分红送转" in txt)
    out.append(rec)

(HERE / "dividend-extract.json").write_text(
    json.dumps({"dividends": out}, ensure_ascii=False, indent=1), encoding="utf-8")
for r in out:
    print(r["name"], r["cash_per_share_yuan"], r["record_date"], r["ex_date"], r["payment_date"],
          r["base_shares"], "diff?", r["differential"])
