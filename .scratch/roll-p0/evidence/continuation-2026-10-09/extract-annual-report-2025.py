"""Offline alternative extraction; original bytes and initial extraction receipt retained."""
import hashlib
import json
from pathlib import Path

import pdfplumber

directory = Path(__file__).resolve().parent
receipt = json.loads((directory / 'annual-report-2025-followup.json').read_text(encoding='utf-8'))
source = Path(receipt['path'])
assert hashlib.sha256(source.read_bytes()).hexdigest() == receipt['sha256']
pages = []
with pdfplumber.open(source) as pdf:
    for index, page in enumerate(pdf.pages[:140]):
        text = page.extract_text() or ''
        if index < 2 or any(term in text for term in ['股份', '股本', 'Share capital', 'share capital', '600362']):
            extracted = source.parent / f'plumber-page-{index + 1}.txt'
            extracted.write_text(text, encoding='utf-8')
            pages.append({'pdf_page': index + 1, 'extracted_path': str(extracted),
                          'sha256': hashlib.sha256(extracted.read_bytes()).hexdigest(), 'characters': len(text)})
result = {'original_sha256': receipt['sha256'], 'parser': 'pdfplumber', 'checked_pages': 140,
          'reason': 'pypdf initial extraction found no relevant terms and reported missing fontTools',
          'pages': pages, 'equity_completeness': 'REQUIRES_CONTENT_REVIEW',
          'sealed_read': False, 'labels_computed': False, 'models_fitted': False}
(directory / 'annual-report-2025-extraction.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'saved_pages': len(pages), 'pages': [row['pdf_page'] for row in pages]}, ensure_ascii=False))
