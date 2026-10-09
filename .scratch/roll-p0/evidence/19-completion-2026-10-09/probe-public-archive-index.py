"""Bounded archive metadata probe; no live-market fallback or historical claims."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

import httpx

directory = Path(__file__).resolve().parent
raw = directory / '.roll-data/public-archive-index'
raw.mkdir(parents=True, exist_ok=False)
targets = [
    'hq.sinajs.cn/list=sh600362',
    'q.stock.sohu.com/hisHq*cn_600362*',
    'web.ifzq.gtimg.cn/appstock/app/fqkline/get*sh600362*',
]


def probe(target):
    row = {'target': target, 'requested_at': datetime.now(timezone.utc).isoformat(),
           'max_file_bytes': 2 * 1024 * 1024, 'purpose': 'ARCHIVED_VERSION_INDEX_FEASIBILITY'}
    try:
        with httpx.Client(timeout=25, follow_redirects=False) as client:
            params = {'url': target, 'output': 'json', 'from': '2013', 'to': '2025',
                      'filter': 'statuscode:200', 'collapse': 'timestamp:6', 'limit': '160',
                      'fl': 'timestamp,original,mimetype,statuscode,digest,length'}
            with client.stream('GET', 'https://web.archive.org/cdx/search/cdx', params=params) as response:
                row.update(url=str(response.request.url), http_status=response.status_code)
                content = bytearray()
                for part in response.iter_bytes():
                    content.extend(part)
                    if len(content) > row['max_file_bytes']:
                        raise ValueError('EXPLICIT_SIZE_LIMIT')
        body = bytes(content)
        digest = hashlib.sha256(body).hexdigest()
        path = raw / (digest + '.raw')
        path.write_bytes(body)
        row.update(received_at=datetime.now(timezone.utc).isoformat(), sha256=digest,
                   bytes=len(body), path=str(path), status='RESPONSE_ARCHIVED')
        if row['http_status'] == 200:
            payload = json.loads(body)
            row['metadata_records'] = max(0, len(payload) - 1) if isinstance(payload, list) else None
            row['is_index_only'] = True
        else:
            row['assessment'] = 'NON200_NOT_ARCHIVE_AVAILABILITY_PROOF'
    except Exception as exc:
        row.update(status='FAILED', error=str(exc))
    return row


with ThreadPoolExecutor(max_workers=3) as pool:
    sources = list(pool.map(probe, targets))
result = {'sources': sources, 'requests': len(sources), 'labels_computed': False, 'sealed_read': False,
          'models_fitted': False, 'live_source_fallback': False, 'qualification': 'NONE'}
(raw / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(directory / 'public-archive-index-receipts.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps([{key: row.get(key) for key in ['target', 'http_status', 'metadata_records', 'bytes', 'status', 'error']} for row in sources], ensure_ascii=False))
