"""Copy only two named official DOCUMENT_LEAD originals with exact SHA/length."""
import hashlib
import json
from pathlib import Path
folder = Path(__file__).resolve().parent
repo = folder.parents[3]
outside = Path('C:/Users/72449/.codex/visualizations/2026/10/10/01a126a2-cdcc-7d52-b24a-ad47b49bcc56')
target = repo / 'backend/src/roll/market/reference/sse-company-contract'
target.mkdir(parents=True, exist_ok=True)
sources = []
for role, sha, size in [
    ('company_html', '72bdf9f924465e3c848577fa4ec5285c163474a79be9bee4a0500a2ecb53f55b', 39826),
    ('company_js', '478fb2a72fc5a3725088adb208756e88171f79628956a9f5ca67c900d37def2f', 277193),
]:
    stem = 'roll-ticket30-authority-document-' + sha
    receipt = json.loads((outside / (stem + '.json')).read_bytes())
    body = (outside / (stem + '.raw')).read_bytes()
    assert len(body) == size and hashlib.sha256(body).hexdigest() == sha
    assert receipt['sha256'] == sha and receipt['bytes'] == size
    path = target / (sha + '.raw')
    if path.exists():
        assert path.read_bytes() == body
    else:
        path.write_bytes(body)
    sources.append({k: receipt[k] for k in ['url', 'received_at', 'bytes', 'sha256', 'classification']} |
                   {'role': role, 'path': path.name, 'publication_time': None, 'effective_time': None})
(target / 'sources.json').write_text(json.dumps({'sources': sources}, indent=2) + '\n', encoding='utf-8', newline='\n')
(target / '.gitattributes').write_text('*.raw binary\n*.json -text\n', encoding='utf-8', newline='\n')
(folder / 'documents-copy-receipt.json').write_text(json.dumps({'sources': sources, 'network_calls': 0,
    'sqlite_opened': False, 'sha_length_mismatches': 0}, indent=2) + '\n', encoding='utf-8', newline='\n')
print('TWO_NAMED_DOCUMENTS_317019_BYTES_IDENTICAL_NO_NETWORK')
