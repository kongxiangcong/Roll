"""Local hash/SQLite metadata checks only; never constructs an app/provider run."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

root = Path(__file__).resolve().parents[4]
parser = argparse.ArgumentParser()
parser.add_argument('--checkout', type=Path, default=root)
args = parser.parse_args()
checkout = args.checkout.resolve()
evidence = checkout / '.scratch/roll-p0/evidence/23'
preservation = json.loads((evidence / 'preservation-manifest.json').read_text(encoding='utf-8-sig'))
profiles = []
for name, group in preservation.items():
    for entry in group['files']:
        for base in [group['source'], group['destination']]:
            path = (Path(base) / entry['path']).resolve()
            assert root in path.parents, path
            raw = path.read_bytes()
            assert len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256'], path
    profiles.append({'kind': name, 'files': len(group['files']), 'bytes': sum(f['bytes'] for f in group['files']), 'source_and_root_SHA_length_match': True})
snapshot = json.loads((evidence / 'source-after-final.json').read_text(encoding='utf-8-sig'))
for relative, expected in snapshot['sources'].items():
    raw = (checkout / relative).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected['sha256'], relative
upstream = json.loads((root / '.scratch/roll-p0/evidence/continuation-2026-10-11/upstream19-before20.json').read_text(encoding='utf-8-sig'))
for row in upstream:
    raw = (checkout / row['path']).read_bytes()
    assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest().upper() == row['sha256'].upper(), row['path']
permanent = root / '.roll-data/implementation-evidence/23/provider-approval/provider-material-manifest.json'
raw = permanent.read_bytes()
assert raw == (evidence / 'provider-material-manifest.json').read_bytes()
manifest = json.loads(raw)
assert manifest['external_transmissions'] == 0
code_hashes = {}
for name in ['models', 'execution', 'shadow', 'statistics', 'validation']:
    envelope = json.loads((permanent.parent / 'provider-materials' / ('code-' + name + '.json')).read_text(encoding='utf-8-sig'))
    content = envelope['content'].encode()
    assert hashlib.sha256(content).hexdigest() == envelope['sha256']
    assert content == (checkout / 'backend/src/roll/research' / (name + '.py')).read_bytes().replace(b'\r\n', b'\n')
    code_hashes[name] = envelope['sha256']
database = root / '.roll-data/implementation-evidence/23/actual-current-copy/roll.sqlite3'
with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
    exists = connection.execute("SELECT name FROM sqlite_master WHERE name='technical_review_runs'").fetchone()
    actual_runs = connection.execute('SELECT COUNT(*) FROM technical_review_runs').fetchone()[0] if exists else 0
assert actual_runs == 0
print(json.dumps({'status': 'PASS', 'checkout': str(checkout), 'preserved': profiles,
    'source_snapshot_matches': True, 'upstream19_files_unchanged': len(upstream),
    'permanent_manifest_sha256': hashlib.sha256(raw).hexdigest(),
    'approval_material_fingerprint': manifest['material_fingerprint'], 'five_approved_code_hashes': code_hashes,
    'actual_review_runs': actual_runs, 'external_transmissions_per_manifest': 0,
    'app_started': False, 'provider_invoked': False, 'production19_opened': False}, indent=2))
