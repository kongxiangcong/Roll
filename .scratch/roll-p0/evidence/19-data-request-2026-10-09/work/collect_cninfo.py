"""Collect machine-readable issuer announcement evidence from cninfo for 600362.

Records every announcement index response verbatim; downloads the dividend
implementation PDFs referenced by the rights research where not already local.
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
RECEIPTS = []

CNINFO_POST = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
HEADERS = {
    "Referer": "http://www.cninfo.com.cn/new/disclosure/stock?stockCode=600362",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}


def grab(name, url, purpose, headers=None, timeout=60, max_bytes=32 * 1024 * 1024, post=None):
    if post is None:
        r = fetch(url, headers=headers, timeout=timeout, max_bytes=max_bytes)
    else:
        # POST via curl
        import subprocess, tempfile, hashlib
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "b.bin"; hp = Path(td) / "h.txt"
            cmd = ["curl", "-sS", "--max-time", str(timeout), "--max-filesize", str(max_bytes),
                   "-D", str(hp), "-o", str(bp), "-X", "POST"]
            for k, v in (headers or {}).items():
                cmd += ["-H", f"{k}: {v}"]
            for k, v in post.items():
                cmd += ["--data-urlencode", f"{k}={v}"]
            cmd.append(url)
            req = datetime.now(timezone.utc).isoformat()
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 15)
            body = bp.read_bytes() if bp.exists() else b""
            hdrs = hp.read_bytes() if hp.exists() else b""
            recv = datetime.now(timezone.utc).isoformat()
        status = None; hm = {}
        for line in hdrs.decode("latin-1", "replace").splitlines():
            if line.startswith("HTTP/"):
                try: status = int(line.split()[1])
                except Exception: pass
            elif ":" in line:
                k, _, v = line.partition(":"); hm[k.strip().lower()] = v.strip()
        r = {"url": url, "requested_at": req, "received_at": recv, "curl_exit": p.returncode,
             "curl_stderr": p.stderr.strip()[:300], "http_status": status, "headers": hm,
             "body": body, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    body = r.pop("body")
    path = RAW / (r["sha256"] + ".bin")
    if path.exists() and path.read_bytes() != body:
        raise RuntimeError("SHA_COLLISION")
    path.write_bytes(body)
    rec = {"name": name, "purpose": purpose, "raw_file": path.name, **r}
    RECEIPTS.append(rec)
    print(f"  [{r['http_status']}] {r['bytes']:>8} {r['sha256'][:12]}  {name}")
    return rec


if __name__ == "__main__":
    # announcement index queries - per category and window
    queries = [
        ("cninfo_idx_all_2016_2023",
         {"pageNum": "1", "pageSize": "100", "column": "sse", "tabName": "fulltext",
          "stock": "600362,gssh0600362", "seDate": "2016-01-01~2023-12-31", "category": "", "searchkey": ""},
         "full announcement index 2016-2023"),
        ("cninfo_idx_dividend_2016_2023",
         {"pageNum": "1", "pageSize": "100", "column": "sse", "tabName": "fulltext",
          "stock": "600362,gssh0600362", "seDate": "2016-01-01~2023-12-31",
          "category": "category_fxgg_szsh", "searchkey": ""},
         "dividend/distribution category index 2016-2023"),
    ]
    for name, post, purpose in queries:
        grab(name, CNINFO_POST, purpose, headers=HEADERS, post=post)

    (HERE / "cninfo-receipts.json").write_text(
        json.dumps({"receipts": RECEIPTS}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote cninfo-receipts.json ({len(RECEIPTS)})")
