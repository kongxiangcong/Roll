"""Collect a bounded dated-publication sample; never infer old availability from today's receipt."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

import httpx

directory = Path(__file__).resolve().parent
raw = directory / '.roll-data/dated-paper-sample'
raw.mkdir(parents=True, exist_ok=False)
urls = [
    'https://epaper.cs.com.cn/zgzqb/images/2013-01/23/A19/CGG0080123C.pdf',
    'https://epaper.cs.com.cn/zgzqb/html/2013-01/23/nbs.D110000zgzqb_19.htm',
    'https://epaper.cs.com.cn/zgzqb/html/2013-01/23/nbs.D110000zgzqb_01.htm',
]


def collect(url):
    record = {'url': url, 'requested_at': datetime.now(timezone.utc).isoformat(),
              'max_file_bytes': 8 * 1024 * 1024, 'purpose': 'DATED_PUBLICATION_FEASIBILITY_ONLY'}
    try:
        with httpx.Client(timeout=25, follow_redirects=False) as client:
            with client.stream('GET', url) as response:
                record['http_status'] = response.status_code
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > record['max_file_bytes']:
                        raise ValueError('EXPLICIT_SIZE_LIMIT')
        body = bytes(content)
        digest = hashlib.sha256(body).hexdigest()
        path = raw / (digest + ('.pdf' if body.startswith(b'%PDF') else '.html'))
        path.write_bytes(body)
        record.update(received_at=datetime.now(timezone.utc).isoformat(), sha256=digest,
                      bytes=len(body), path=str(path), status='RESPONSE_ARCHIVED')
        if path.suffix == '.pdf' and record['http_status'] == 200:
            from pypdf import PdfReader
            pdf = PdfReader(path)
            record['pdf_pages'] = len(pdf.pages)
            pages = []
            for index, page in enumerate(pdf.pages[:2]):
                text = page.extract_text() or ''
                extracted = raw / f'{digest}-page-{index+1}.txt'
                extracted.write_text(text, encoding='utf-8')
                pages.append({'page': index + 1, 'path': str(extracted),
                              'sha256': hashlib.sha256(extracted.read_bytes()).hexdigest()})
            record['extracted_pages'] = pages
    except Exception as exc:
        record.update(status='FAILED', error=str(exc))
    return record


with ThreadPoolExecutor(max_workers=3) as pool:
    records = list(pool.map(collect, urls))
result = {'sources': records, 'model_fits': 0, 'labels_computed': False, 'sealed_read': False,
          'qualification': 'NONE; content, fields and publication-date evidence require review'}
(raw / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(directory / 'dated-paper-sample-receipts.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps([{key: row.get(key) for key in ['url', 'http_status', 'bytes', 'status', 'error']} for row in records], ensure_ascii=False))
