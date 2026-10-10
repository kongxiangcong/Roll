"""Archive a fixed set of public historical dividend-tax sources, without credentials."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path

import httpx

DIRECTORY = Path(__file__).resolve().parent / '.roll-data/dividend-tax-research-v1'
SOURCES = [
    ('tax-2012-85', 'https://fgk.chinatax.gov.cn/zcfgk/c102416/c5204415/content.html', '85'),
    ('tax-2015-101', 'https://m.mof.gov.cn/czxw/201509/t20150907_1452683.htm', '101'),
    ('tax-2015-explanation', 'https://szs.mof.gov.cn/zhengcejiedu/201509/t20150909_1455696.htm', '股息红利'),
    ('tax-2013-announcement', 'https://www.mof.gov.cn/zhengwuxinxi/caizhengxinwen/201211/t20121116_697327.htm', '2013'),
]
DIRECTORY.mkdir(parents=True, exist_ok=False)


def collect(source):
    name, url, marker = source
    record = {'id': name, 'url': url, 'requested_at': datetime.now(timezone.utc).isoformat(),
              'purpose': 'Historical research source; not personal account tax advice'}
    try:
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            with client.stream('GET', url) as response:
                record['http_status'] = response.status_code
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 2 * 1024 * 1024:
                        raise ValueError('Public source exceeds 2 MiB bound')
                received = datetime.now(timezone.utc).isoformat()
                declared = re.search(rb'charset\s*=\s*["\x27]?([\w-]+)', bytes(body), re.I)
                encoding = declared[1].decode('ascii') if declared else response.charset_encoding or 'utf-8'
        sha = hashlib.sha256(body).hexdigest()
        path = DIRECTORY / (name + '-' + sha + '.html')
        path.write_bytes(body)
        text = bytes(body).decode(encoding, errors='replace')
        verified = response.status_code == 200 and marker in text and '股息' in text
        record.update(received_at=received, sha256=sha, bytes=len(body), path=str(path), encoding=encoding,
                      status='POLICY_TEXT_ARCHIVED' if verified else 'UNVERIFIED_RESPONSE_ARCHIVED')
    except (httpx.HTTPError, ValueError, LookupError) as error:
        record.update(status='FETCH_FAILED', error_type=type(error).__name__)
    return record


with ThreadPoolExecutor(max_workers=4) as pool:
    records = list(pool.map(collect, SOURCES))
manifest = {'sources': records, 'credentials_used': False, 'provider_interfaces_used': [],
            'labels_computed': False, 'models_fitted': False}
(DIRECTORY / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
Path(__file__).with_name('dividend-tax-research-receipts.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps([{'id': row['id'], 'status': row['status'], 'bytes': row.get('bytes')} for row in records]))
