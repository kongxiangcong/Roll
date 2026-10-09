"""Bounded exact historical index probes; no live quote fallback or labels."""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import httpx

OUT = Path(__file__).resolve().parent
RAW = OUT / '.roll-data' / 'exact-index'
RAW.mkdir(parents=True, exist_ok=True)
TARGETS = [
    'hq.sinajs.cn/list=sh600362',
    'hq.sinajs.cn/?list=sh600362',
    'finance.sina.com.cn/realstock/company/sh600362/hisdata/klc_kl.js',
    'money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh600362&scale=240&ma=no&datalen=1023',
    'vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh600362&scale=240&ma=no&datalen=1023',
    'q.stock.sohu.com/cn/600362/lshq.shtml',
]

def collect(target):
    params = {'url': target, 'matchType': 'exact', 'from': '2013', 'to': '2025',
              'output': 'json', 'filter': 'statuscode:200', 'limit': '5000',
              'fl': 'timestamp,original,mimetype,statuscode,digest,length'}
    row = {'target': target, 'requested_at': datetime.now(timezone.utc).isoformat(),
           'collapse': None, 'index_only': True, 'live_fallback': False}
    request = httpx.Request('GET', 'https://web.archive.org/cdx/search/cdx', params=params)
    row['url'] = str(request.url)
    try:
        with httpx.Client(timeout=25, follow_redirects=False) as client:
            with client.stream('GET', request.url) as response:
                row['http_status'] = response.status_code
                row['headers'] = dict(response.headers)
                body = bytearray()
                for chunk in response.iter_raw():
                    body.extend(chunk)
                    if len(body) > 2 * 1024 * 1024:
                        raise ValueError('INDEX_SIZE_LIMIT')
        content = bytes(body)
        sha = hashlib.sha256(content).hexdigest()
        path = RAW / (sha + '.raw')
        if path.exists() and path.read_bytes() != content:
            raise ValueError('EXISTING_RAW_DIFFERS')
        path.write_bytes(content)
        row.update(path=str(path), sha256=sha, bytes=len(content),
                   received_at=datetime.now(timezone.utc).isoformat())
        decoded = content
        if row['headers'].get('content-encoding') == 'gzip':
            import gzip
            decoded = gzip.decompress(content)
        if response.status_code == 200:
            payload = json.loads(decoded)
            row['records'] = max(0, len(payload)-1)
            row['truncation_possible'] = row['records'] == 5000
            row['captures'] = [dict(zip(payload[0], values)) for values in payload[1:]] if payload else []
        row['status'] = 'RESPONSE_ARCHIVED'
    except Exception as error:
        row.update(status='FAILED', error=type(error).__name__+': '+str(error))
    return row

if __name__ == '__main__':
    target = OUT / 'exact-index-receipts.json'
    if target.exists():
        raise RuntimeError('Keep prior receipts; use a new collection directory for a new stage')
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(collect, TARGETS))
    mismatches = []
    for row in rows:
        if 'path' in row:
            body = Path(row['path']).read_bytes()
            if len(body) != row['bytes'] or hashlib.sha256(body).hexdigest() != row['sha256']:
                mismatches.append(row['target'])
    report = {'requests': rows, 'request_limit': 6, 'labels_computed': False,
              'models_fitted': 0, 'sealed_read': False, 'hash_length_mismatches': mismatches}
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps([{k: row.get(k) for k in ['target', 'status', 'http_status', 'records', 'error']} for row in rows], ensure_ascii=False))
