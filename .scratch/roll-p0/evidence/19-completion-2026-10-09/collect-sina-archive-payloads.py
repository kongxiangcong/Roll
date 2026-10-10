"""Read bounded, already indexed public archive captures without live fallback."""
import base64
import concurrent.futures
import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / '.roll-data' / 'sina-archive-payloads-v3'
OUT.mkdir(exist_ok=True)
index_receipt = json.loads((HERE / 'public-archive-index-receipts.json').read_text(encoding='utf8'))['sources'][0]
index_bytes = Path(index_receipt['path']).read_bytes()
if hashlib.sha256(index_bytes).hexdigest() != index_receipt['sha256']:
    raise ValueError('INDEX_BYTES_CHANGED')
table = json.loads(index_bytes)
indexed = [dict(zip(table[0], row)) for row in table[1:]]
if len(indexed) > 44:
    raise ValueError('44_CAPTURE_CAP')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def collect(item):
    target = item['original']
    if not re.fullmatch(r'https?://hq\.sinajs\.cn(?::80)?/list=sh600362', target):
        raise ValueError('UNEXPECTED_TARGET')
    capture = item['timestamp']
    url = f'https://web.archive.org/web/{capture}id_/{target}'
    row = {'cdx': item, 'url': url, 'requested_at': datetime.now(timezone.utc).isoformat(),
           'capture_time': datetime.strptime(capture, '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc).isoformat(),
           'original_publication_at': None, 'live_fallback': False, 'status': 'FAILED'}
    try:
        opener = urllib.request.build_opener(NoRedirect)
        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            response = opener.open(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('2_MIB_SINGLE_CAPTURE_CAP')
        sha = hashlib.sha256(raw).hexdigest()
        path = OUT / (sha + '.raw')
        path.write_bytes(raw)
        digest = base64.b32encode(hashlib.sha1(raw).digest()).decode().rstrip('=')
        row.update(status='RESPONSE_ARCHIVED', http_status=response.status,
                   received_at=datetime.now(timezone.utc).isoformat(), headers=dict(response.headers),
                   bytes=len(raw), sha256=sha, path=str(path), cdx_digest_matches_body=(digest == item['digest']))
        if response.status != 200:
            row['payload_status'] = 'NON_SUCCESS_RESPONSE_NO_FOLLOW'
            return row
        text = raw.decode('gb18030', errors='strict')
        match = re.search(r'var\s+hq_str_sh600362\s*=\s*"([^"]*)"\s*;', text)
        if not match:
            row['payload_status'] = 'EXPECTED_QUOTE_NOT_PRESENT'
            return row
        fields = match.group(1).split(',')
        row['quote_field_count'] = len(fields)
        if len(fields) < 32:
            row['payload_status'] = 'EMPTY_OR_SHORT_QUOTE'
            return row
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', fields[30]) or not re.fullmatch(r'\d{2}:\d{2}:\d{2}', fields[31]):
            row['payload_status'] = 'UNEXPECTED_BUSINESS_CLOCK_FORMAT'
            return row
        for value in [fields[n] for n in [1,2,3,4,5,8,9]]:
            if not re.fullmatch(r'\d+(?:\.\d+)?', value):
                raise ValueError('NON_NUMERIC_QUOTE_VALUE')
        row['quote'] = {'instrument': 'SSE:600362', 'security_name': fields[0],
                        'open': fields[1], 'previous_close': fields[2], 'last_price': fields[3],
                        'high': fields[4], 'low': fields[5], 'reported_volume': fields[8],
                        'reported_amount': fields[9], 'business_date': fields[30],
                        'business_time': fields[31], 'clock_timezone': 'Asia/Shanghai',
                        'trailing_fields': fields[32:], 'raw_fields': fields,
                        'unit_semantics': 'FIELD_POSITION_CANDIDATE_REQUIRES_PROVIDER_SCHEMA_OR_INDEPENDENT_UNIT_CHECK',
                        'completion_class': 'AFTER_NOMINAL_CLOSE_NOT_CALENDAR_QUALIFIED' if fields[31] >= '15:00:00' else 'INTRADAY_OR_PREOPEN',
                        'state_or_risk_warning': 'NOT_INFERRED_FROM_TRAILING_FIELDS'}
        row['payload_status'] = 'QUOTE_BODY_PARSED'
    except Exception as error:
        row['error'] = type(error).__name__ + ': ' + str(error)
    return row

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    rows = list(pool.map(collect, indexed))
mismatches = []
for row in rows:
    if 'path' in row:
        raw = Path(row['path']).read_bytes()
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            mismatches.append(row['url'])
receipt = {'source_index_sha256': index_receipt['sha256'], 'captures': rows,
           'limits': {'captures':44, 'parallel':4, 'timeout_seconds':30, 'single_bytes':2*1024*1024},
           'verification': {'checked':sum('path' in row for row in rows), 'mismatches':mismatches},
           'labels_computed':False, 'sealed_read':False, 'models_fitted':False, 'qualification':'NONE'}
(HERE/'sina-archive-payload-receipts.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
(OUT/'manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'captures':len(rows),'responses':sum('path' in r for r in rows),
                  'quotes':sum(r.get('payload_status')=='QUOTE_BODY_PARSED' for r in rows),
                  'failures':sum(r['status']=='FAILED' for r in rows),'hash_length_mismatches':len(mismatches)},ensure_ascii=False))
