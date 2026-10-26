import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx

root = Path(__file__).resolve().parent
plan = json.loads((root / 'plan.json').read_text(encoding='utf-8'))
assert not (root / 'capture-manifest.json').exists(), 'Closed run must never be retried'
started = time.monotonic()
records = []
total = 0
with httpx.Client(follow_redirects=False, timeout=httpx.Timeout(9.0), headers={'User-Agent': 'Roll bounded official-document research', 'Referer': 'https://www.sseinfo.com/'}) as client:
    for ordinal, url in enumerate(plan['urls'], 1):
        if time.monotonic() - started >= plan['max_seconds']:
            break
        record = {'ordinal': ordinal, 'url': url, 'started_at': datetime.now(timezone.utc).isoformat()}
        chunks = []
        try:
            with client.stream('GET', url) as response:
                record.update(status=response.status_code, headers=dict(response.headers))
                for chunk in response.iter_bytes():
                    if total + len(chunk) > plan['max_bytes'] or time.monotonic() - started > plan['max_seconds']:
                        raise RuntimeError('Budget boundary reached; response incomplete')
                    chunks.append(chunk)
                    total += len(chunk)
                record['complete'] = True
        except Exception as exc:
            record.update(complete=False, error=type(exc).__name__ + ': ' + str(exc))
        body = b''.join(chunks)
        path = f'{ordinal:02d}.raw'
        (root / path).write_bytes(body)
        record.update(path=path, bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), received_at=datetime.now(timezone.utc).isoformat())
        records.append(record)
        (root / 'progress.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
result = {'state': 'CLOSED_NO_RETRY', 'requests': len(records), 'bytes': total, 'elapsed_seconds': time.monotonic() - started, 'market_requests': 0, 'records': records}
(root / 'capture-manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k,v in result.items() if k != 'records'}))
