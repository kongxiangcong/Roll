"""Paginate the full cninfo announcement index for 600362 across the candidate scope."""
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
RAW.mkdir(exist_ok=True)
URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
HEADERS = {
    "Referer": "http://www.cninfo.com.cn/new/disclosure/stock?stockCode=600362",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Mozilla/5.0",
}
BASE = ("pageNum={p}&pageSize=30&column=sse&tabName=fulltext&stock=600362%2Cgssh0600362"
        "&seDate=2015-10-01~2023-12-31&category=&searchkey=&secid=&plate=&trade=")


def post(page):
    with tempfile.TemporaryDirectory() as td:
        bp = Path(td) / "b.bin"
        cmd = ["curl", "-sS", "--max-time", "40", "-o", str(bp), "-X", "POST"]
        for k, v in HEADERS.items():
            cmd += ["-H", f"{k}: {v}"]
        cmd += ["--data", BASE.format(p=page), URL]
        req = datetime.now(timezone.utc).isoformat()
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        body = bp.read_bytes() if bp.exists() else b""
    return body, req


rows = []
receipts = []
page = 1
total = None
while True:
    body, req = post(page)
    sha = hashlib.sha256(body).hexdigest()
    (RAW / (sha + ".bin")).write_bytes(body)
    receipts.append({"page": page, "raw_file": sha + ".bin", "sha256": sha, "bytes": len(body),
                     "requested_at": req, "received_at": datetime.now(timezone.utc).isoformat()})
    j = json.loads(body.decode("utf-8"))
    total = int(j.get("totalRecordNum") or 0)
    anns = j.get("announcements") or []
    for a in anns:
        rows.append({"announcementId": a.get("announcementId"), "secCode": a.get("secCode"),
                     "secName": a.get("secName"), "title": a.get("announcementTitle"),
                     "time_ms": a.get("announcementTime"), "adjunctUrl": a.get("adjunctUrl"),
                     "adjunctSize": a.get("adjunctSize"), "announcementType": a.get("announcementType"),
                     "pageColumn": a.get("pageColumn")})
    print("page", page, "rows", len(anns), "total", total)
    if not anns or page * 30 >= total:
        break
    page += 1
seen = {}
for r in rows:
    key = r["adjunctUrl"] or f"{r['title']}|{r['time_ms']}"
    seen[key] = r
out = sorted(seen.values(), key=lambda x: x["time_ms"] or 0)
(HERE / "cninfo-index.json").write_text(
    json.dumps({"receipts": receipts, "announcements": out, "total": len(out),
                "declared_total": total}, ensure_ascii=False, indent=1), encoding="utf-8")
print("TOTAL UNIQUE", len(out), "declared", total)
