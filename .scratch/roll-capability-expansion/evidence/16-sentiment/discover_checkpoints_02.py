"""One bounded public metadata capture; refuses to overwrite a prior receipt."""
import hashlib
import json
import time
import sys
from datetime import datetime, timezone
from pathlib import Path
import requests

root = Path(__file__).resolve().parent
plan_path = root / (sys.argv[1] if len(sys.argv) > 1 else "checkpoint-discovery-02-plan.json")
plan = json.loads(plan_path.read_text(encoding="utf-8"))
out = root / plan_path.name.removesuffix("-plan.json")
out.mkdir(exist_ok=False)
started = time.monotonic()
total = 0
receipts = []
session = requests.Session()
session.headers["User-Agent"] = "Roll-checkpoint-discovery/1.0"
try:
    for index, url in enumerate(plan["requests"], 1):
        remaining = plan["limits"]["maximum_seconds"] - (time.monotonic() - started)
        if remaining <= 0:
            break
        item = {"request": index, "url": url, "received_at": datetime.now(timezone.utc).isoformat()}
        receipts.append(item)
        try:
            with session.get(url, timeout=(min(5, remaining), min(8, remaining)), stream=True, allow_redirects=False) as response:
                item["status_code"] = response.status_code
                item["link"] = response.headers.get("Link")
                body = bytearray()
                for chunk in response.iter_content(16384):
                    total += len(chunk)
                    if total > plan["limits"]["maximum_bytes"] or time.monotonic() - started > plan["limits"]["maximum_seconds"]:
                        raise RuntimeError("capture budget exceeded")
                    body.extend(chunk)
                path = out / f"{index:02}.raw"
                path.write_bytes(body)
                item.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), file=path.name)
        except Exception as exc:
            item["error_type"] = type(exc).__name__
            # No proxy values, credentials, or environment details in evidence.
            if isinstance(exc, RuntimeError):
                break
finally:
    session.close()
    result = {"attempt_id": plan["attempt_id"], "status": "CLOSED_NO_RETRY", "elapsed_seconds": round(time.monotonic()-started, 3), "bytes": total, "requests": receipts}
    (out / "receipt.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
