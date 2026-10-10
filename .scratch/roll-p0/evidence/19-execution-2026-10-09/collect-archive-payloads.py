"""Acquire only newly indexed, pre-2026 public historical captures."""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import base64
import gzip
import hashlib
import json
import re
import httpx
from urllib.parse import urlparse

OUT = Path(__file__).resolve().parent
OLD = OUT.parent / '19-completion-2026-10-09'
RAW = OUT / '.roll-data' / 'exact-payloads'
RAW.mkdir(parents=True, exist_ok=True)

def digest(body):
    return base64.b32encode(hashlib.sha1(body).digest()).decode().rstrip('=')

def collect(capture):
    original = capture['original']
    url = 'https://web.archive.org/web/' + capture['timestamp'] + 'id_/' + original
    row = {'capture': capture, 'url': url, 'requested_at': datetime.now(timezone.utc).isoformat(),
           'original_publication_at': None, 'live_fallback': False}
    try:
        parsed = urlparse(original)
        if parsed.hostname not in {'hq.sinajs.cn', 'q.stock.sohu.com'} or parsed.port not in {None, 80, 443}:
            raise ValueError('UNEXPECTED_ORIGINAL_HOST')
        with httpx.Client(timeout=25, follow_redirects=False) as client:
            with client.stream('GET', url) as response:
                row.update(http_status=response.status_code, headers=dict(response.headers))
                body = bytearray()
                for chunk in response.iter_raw():
                    body.extend(chunk)
                    if len(body) > 2 * 1024 * 1024:
                        raise ValueError('PAYLOAD_SIZE_LIMIT')
        wire = bytes(body)
        sha = hashlib.sha256(wire).hexdigest()
        path = RAW / (sha + '.raw')
        if path.exists() and path.read_bytes() != wire:
            raise ValueError('EXISTING_RAW_DIFFERS')
        path.write_bytes(wire)
        row.update(path=str(path), sha256=sha, bytes=len(wire),
                   received_at=datetime.now(timezone.utc).isoformat())
        decoded = gzip.decompress(wire) if row['headers'].get('content-encoding') == 'gzip' else wire
        row.update(wire_digest_matches=digest(wire)==capture['digest'],
                   decoded_digest_matches=digest(decoded)==capture['digest'],
                   decoded_sha256=hashlib.sha256(decoded).hexdigest())
        if response.status_code == 200 and (row['wire_digest_matches'] or row['decoded_digest_matches']):
            text = decoded.decode('gb18030')
            if 'hq.sinajs.cn' in original:
                match = re.search(r'var hq_str_sh600362="([^"]*)"', text)
                if not match:
                    raise ValueError('QUOTE_SCHEMA_MISSING')
                fields = match[1].split(',')
                if len(fields) < 32:
                    raise ValueError('QUOTE_FIELDS_MISSING')
                business = datetime.fromisoformat(fields[30]+'T'+fields[31]+'+08:00')
                captured = datetime.strptime(capture['timestamp'], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
                row['quote'] = {'business_date': fields[30], 'business_time': fields[31],
                                'open': fields[1], 'last_price': fields[3], 'high': fields[4], 'low': fields[5],
                                'raw_volume': fields[8], 'raw_amount': fields[9],
                                'capture_lag_seconds': (captured-business).total_seconds(),
                                'nominal_after_close': fields[31]>='15:00:00',
                                'complete_bar_proven': False}
            else:
                row['page'] = {'dates_found': sorted(set(re.findall(r'20\d\d[-/]\d\d[-/]\d\d', text))),
                               'has_history_endpoint': 'hisHq' in text,
                               'historical_rows_present': bool(re.search(r'<td[^>]*>\s*20\d\d[-/]\d\d[-/]\d\d', text)),
                               'content_is_not_training_qualification': True}
        row['status'] = 'RESPONSE_ARCHIVED'
    except Exception as error:
        row.update(status='FAILED', error=type(error).__name__+': '+str(error))
    key = hashlib.sha256((capture['timestamp']+' '+original).encode()).hexdigest()
    (RAW / (key+'.receipt.json')).write_text(json.dumps(row, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return row

if __name__ == '__main__':
    receipt = OUT / 'exact-payload-receipts.json'
    if receipt.exists():
        raise RuntimeError('Do not overwrite prior collection')
    old = json.loads((OLD/'sina-archive-quote-analysis.json').read_bytes())['quotes']
    old_keys = {(q['capture_time'].replace('-','').replace(':','').replace('T','')[:14], q['original']) for q in old}
    indexed = json.loads((OUT/'exact-index-receipts.json').read_bytes())['requests']
    captures = [c for r in indexed for c in r.get('captures', [])
                if (c['timestamp'], c['original']) not in old_keys]
    if len(captures)>40:
        raise ValueError('BOUNDED_STAGE_EXCEEDS40_CAPTURES')
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(collect, captures))
    report = {'requests': rows, 'reused_old_quotes': len(old), 'request_count': len(rows),
              'sealed_read': False, 'models_fitted': 0, 'labels_computed': False}
    receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'requests': len(rows), 'verified_quotes': sum('quote' in r for r in rows),
                      'verified_pages': sum('page' in r for r in rows),
                      'failed': sum(r['status']=='FAILED' for r in rows)}))
