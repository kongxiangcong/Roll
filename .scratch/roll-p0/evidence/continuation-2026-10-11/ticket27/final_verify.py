"""Verify frozen test-source and preservation receipts without SQLite access."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[4]
before = json.loads((evidence / 'source-final-before-integration.json').read_text())
final = json.loads((evidence / 'source-final.json').read_text())
changed = []
old = {item['path']: item for item in before['sources']}
for item in final['sources']:
    raw = (root / item['path']).read_bytes()
    assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'], item['path']
    if old.get(item['path']) != item:
        changed.append(item['path'])
assert final['protected'] == before['protected']
assert len(changed) == 7
assert not any(p.startswith('frontend/') for p in changed)
receipt = json.loads((evidence / 'runtime-preservation-receipt.json').read_text())
manifest_raw = Path(receipt['manifest']).read_bytes()
assert len(manifest_raw) == receipt['bytes']
assert hashlib.sha256(manifest_raw).hexdigest() == receipt['sha256']
manifest = json.loads(manifest_raw)
assert manifest['files'] == len(manifest['entries']) == receipt['files']
assert (evidence / 'runtime-preservation-manifest.json').read_bytes() == manifest_raw
def verify_entry(entry):
    preserved = Path('D:/dsh-proj/Roll') / entry['preserved']
    source = root / entry['source']
    for file in [source, preserved]:
        raw = Path('\\\\?\\' + str(file)).read_bytes()
        assert len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256'], file
with ThreadPoolExecutor(max_workers=8) as executor:
    list(executor.map(verify_entry, manifest['entries']))
boundary = (evidence / 'loss-recovery-boundary.md').read_bytes()
result = {'protected_unchanged': len(final['protected']), 'current_product_files': len(final['sources']),
          'tested_source_mismatches': 0, 'accepted_continuation_changed_sources': changed,
          'preserved_files': manifest['files'], 'preserved_bytes': manifest['bytes'],
          'preservation_mismatches': 0, 'credential_content_reads': 0, 'sqlite_connections': 0,
          'loss_boundary_provenance': {'source_root_oid': 'b432976', 'bytes': len(boundary),
                                     'sha256': hashlib.sha256(boundary).hexdigest()},
          'runtime_manifest_receipt': receipt}
(evidence / 'final-verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result))
