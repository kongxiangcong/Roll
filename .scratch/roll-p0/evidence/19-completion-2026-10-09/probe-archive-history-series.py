"""Check actual archive captures, preserving capture/publication/receipt clocks separately."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

import httpx

directory = Path(__file__).resolve().parent
archive = directory / '.roll-data/archive-series-v2'
archive.mkdir(parents=True, exist_ok=False)
targets = [
    'hq.sinajs.cn/list=sh600362',
    'vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData*',
    'q.stock.sohu.com/cn/600362/lshq.shtml',
]


def request(url, params=None, kind='INDEX'):
    row = {'requested_at': datetime.now(timezone.utc).isoformat(), 'kind': kind, 'max_bytes': 2 * 1024 * 1024}
    try:
        with httpx.Client(timeout=25, follow_redirects=False) as client:
            with client.stream('GET', url, params=params) as response:
                row.update(url=str(response.request.url), http_status=response.status_code,
                           headers={key: value for key, value in response.headers.items()
                                    if key.lower().startswith(('memento-', 'x-archive-', 'content-', 'location'))})
                body = bytearray()
                for part in response.iter_bytes():
                    body.extend(part)
                    if len(body) > row['max_bytes']:
                        raise ValueError('EXPLICIT_SIZE_LIMIT')
        content = bytes(body)
        digest = hashlib.sha256(content).hexdigest()
        path = archive / (digest + '.raw')
        path.write_bytes(content)
        row.update(received_at=datetime.now(timezone.utc).isoformat(), bytes=len(content),
                   sha256=digest, path=str(path), status='RESPONSE_ARCHIVED')
        if row['http_status'] == 200 and kind == 'INDEX':
            payload = json.loads(content)
            row['index_rows'] = max(0, len(payload) - 1) if isinstance(payload, list) else None
    except Exception as exc:
        row.update(status='FAILED', error=str(exc))
    return row


def index(target):
    params = {'url': target, 'output': 'json', 'from': '2013', 'to': '2025', 'filter': 'statuscode:200',
              'limit': '2000', 'fl': 'timestamp,original,mimetype,statuscode,digest,length'}
    if 'getKLineData' in target:
        params['filter'] = ['statuscode:200', 'original:.*sh600362.*']
    return request('https://web.archive.org/cdx/search/cdx', params)


with ThreadPoolExecutor(max_workers=3) as pool:
    indexes = list(pool.map(index, targets))
captures = []
for row in indexes:
    if row.get('index_rows'):
        data = json.loads(Path(row['path']).read_bytes())
        # Only two actual payloads in this phase; no live source follow-up.
        for captured in [data[1], data[-1]]:
            if len(captures) >= 2:
                break
            captured_at, original = captured[:2]
            result = request(f'https://web.archive.org/web/{captured_at}id_/{original}', kind='ARCHIVED_PAYLOAD')
            result.update(index_capture_timestamp=captured_at, index_original_url=original,
                          assessment='CONTENT_COMPLETION_AND_SERIES_COVERAGE_NOT_YET_VERIFIED')
            captures.append(result)
result = {'indexes': indexes, 'captures': captures, 'maximum_http_requests': 5,
          'sealed_read': False, 'models_fitted': False, 'labels_computed': False,
          'live_source_fallback': False, 'qualification': 'NONE'}
(archive / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(directory / 'archive-series-v2-receipts.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'index_rows': [row.get('index_rows') for row in indexes],
                  'captures': [{key: row.get(key) for key in ['http_status', 'bytes', 'status', 'error']} for row in captures]}, ensure_ascii=False))
