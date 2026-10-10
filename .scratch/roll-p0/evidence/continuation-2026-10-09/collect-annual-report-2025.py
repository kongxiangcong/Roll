"""Bounded issuer-original acquisition for 2025 equity audit; no training input."""
import hashlib
import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import httpx
from pypdf import PdfReader

directory = Path(__file__).resolve().parent
archive = directory / '.roll-data/gap-research-v3-2025'
archive.mkdir(parents=True, exist_ok=False)
url = 'https://www.jxcc.com/upload/file/2026/04/30/0963b674-6620-4332-b33f-85143918a01b.pdf'
row = {'url': url,
       'source_index': 'https://www.jxcc.com/periodicReports/details_512_6694.html',
       'source_index_display_date': '2026-04-29',
       'source_date_precision': 'DATE; issuer page display, not exact first release time',
       'purpose': 'Retrospective issuer equity audit; not available to any 2025 predictor',
       'started_at': datetime.now(timezone.utc).isoformat(), 'max_file_bytes': 64 * 1024 * 1024,
       'sealed_read': False, 'models_fitted': False, 'labels_computed': False}
try:
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        with client.stream('GET', url) as response:
            row['http_status'] = response.status_code
            response.raise_for_status()
            body = bytearray()
            for part in response.iter_bytes():
                body.extend(part)
                if len(body) > row['max_file_bytes']:
                    raise ValueError('REPORT_EXCEEDS_EXPLICIT_LIMIT')
    content = bytes(body)
    if not content.startswith(b'%PDF'):
        raise ValueError('RESPONSE_NOT_PDF')
    digest = hashlib.sha256(content).hexdigest()
    path = archive / (digest + '.pdf')
    path.write_bytes(content)
    row.update(received_at=datetime.now(timezone.utc).isoformat(),
               sha256=digest, bytes=len(content), path=str(path), status='PDF_ARCHIVED')
    pdf = PdfReader(BytesIO(content))
    row.update(pdf_pages=len(pdf.pages), checked_pages=min(140, len(pdf.pages)), relevant_pages=[])
    for index, page in enumerate(pdf.pages[:140]):
        text = page.extract_text() or ''
        if any(term in text for term in ['股份总数及股本结构', '股份總數及股本結構',
                                          '股份变动情况表', '股份變動情況表', '股票简况', '股票簡況',
                                          '退市风险', '退市風險', 'share capital', 'Share capital']):
            extracted = archive / f'page-{index + 1}.txt'
            extracted.write_text(text, encoding='utf-8')
            row['relevant_pages'].append({'pdf_page': index + 1, 'extracted_path': str(extracted),
                                          'sha256': hashlib.sha256(extracted.read_bytes()).hexdigest()})
except Exception as exc:
    row.update(status='FAILED', error=str(exc))
(archive / 'manifest.json').write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(directory / 'annual-report-2025-followup.json').write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: row.get(key) for key in ['status', 'bytes', 'sha256', 'pdf_pages', 'error']}, ensure_ascii=False))
if row['status'] != 'PDF_ARCHIVED':
    raise SystemExit(1)
