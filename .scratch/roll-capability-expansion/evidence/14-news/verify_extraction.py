import hashlib, json, time
from pathlib import Path
from trafilatura import bare_extraction

base = Path(r"D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\14-news\actual-source")
manifest = json.loads((base / "capture.json").read_text(encoding="utf-8"))
results = []
for captured in manifest["captures"]:
    if captured["role"] != "BODY":
        continue
    raw = (base / f"{captured['sha256']}.raw").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == captured["sha256"]
    started = time.monotonic()
    result = bare_extraction(raw, url=captured["url"], with_metadata=True, include_comments=False, include_tables=True, fast=False)
    elapsed = round(time.monotonic() - started, 3)
    text = None if result is None else result.text
    results.append({
        "ordinal": captured["ordinal"],
        "url": captured["url"],
        "source_bytes": len(raw),
        "parsed": result is not None,
        "text_chars": len(text or ""),
        "title": None if result is None else getattr(result, "title", None),
        "date": None if result is None else getattr(result, "date", None),
        "sitename": None if result is None else getattr(result, "sitename", None),
        "elapsed_seconds": elapsed,
    })
summary = {
    "component": "trafilatura 2.3.1",
    "offline": True,
    "network_denied": True,
    "documents": results,
    "all_extracted": all(r["parsed"] and r["text_chars"] > 0 for r in results),
    "total_seconds": round(sum(r["elapsed_seconds"] for r in results), 3),
}
out = Path(r"D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\14-news\extraction-summary.json")
out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
