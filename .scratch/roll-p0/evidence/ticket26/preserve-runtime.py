"""Bounded checksum/copy receipts; never opens a database or rewrites evidence."""
from pathlib import Path
import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

own = Path('D:/dsh-proj/Roll/.scratch/worktrees/ticket26')
root = Path('D:/dsh-proj/Roll')
evidence = own / '.scratch/roll-p0/evidence/ticket26'
destination = root / '.roll-data/implementation-evidence/ticket26/2026-10-11-ca9e3b0'
assert destination.resolve().is_relative_to((root / '.roll-data/implementation-evidence/ticket26').resolve())

def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): value.update(block)
    return value.hexdigest()

before = json.loads((evidence / 'protected-source-before.json').read_text(encoding='utf-8'))
guards = []
for entry in before['protected_source_files']:
    relative = entry['path']
    a, b = root / relative, own / relative
    row = {'path': relative, 'root_sha256': digest(a), 'own_sha256': digest(b),
           'expected_original_sha256': entry['expected_original_sha256'], 'root_bytes': a.stat().st_size, 'own_bytes': b.stat().st_size}
    row['unchanged'] = row['root_sha256'] == row['own_sha256'] == row['expected_original_sha256']
    assert row['unchanged'], relative
    guards.append(row)
database = root / '.roll-data/reconstructed19-v1/roll.sqlite3'
db_guard = {'path': str(database), 'bytes': database.stat().st_size, 'sha256': digest(database), 'access': 'CHECKSUM_ONLY_NO_SQLITE_OPEN'}
assert db_guard['bytes'] == 165814272 and db_guard['sha256'] == 'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'
source = own / 'backend/src/roll'
inventory = {str(p.relative_to(source)).replace('\\', '/'): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in sorted(source.rglob('*.py'))}
inventory_fingerprint = hashlib.sha256(json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
mapping = json.loads((evidence / 'final-source/method-500-policy-bindings.json').read_text(encoding='utf-8'))
assert mapping['grant']['system_usable'] is False
assert any(p.get('source_fingerprint') == inventory_fingerprint and p['status'] == 'VERIFIED' for p in mapping['host_proofs'])
guard = {'registered_at': datetime.now(timezone.utc).isoformat(), 'implementation_oid': 'ca9e3b04aae27392ad2a566ae12057b2f4deffe3',
         'accepted_integration_oid': 'd2cb60cb15f73b8574274be69c89db774b94b98d', 'protected_source_files': guards,
         'all_15_unchanged': True, 'actual19_database': db_guard, 'host_source_inventory': inventory,
         'host_source_inventory_fingerprint': inventory_fingerprint, 'source_scope': 'all backend/src/roll/**/*.py normalized CRLF to LF; guards are raw byte SHA256'}
(evidence / 'protected-source-final.json').write_text(json.dumps(guard, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

sources = sorted(p for p in own.glob('t26-*') if p.is_dir()) + [evidence, own / 'frontend/test-results']
files, excluded = [], []
for directory in sources:
    for path in sorted(directory.rglob('*')):
        if not path.is_file(): continue
        assert path.resolve().is_relative_to(own.resolve()), str(path)
        if path.name.lower() in {'auth.json', 'secrets.json', '.env'}:
            excluded.append({'path': str(path.relative_to(own)), 'reason': 'credential/sentinel excluded without reading'})
            continue
        files.append(path)

def preserve(path):
    relative = path.relative_to(own)
    target = destination / relative
    assert target.resolve().is_relative_to(destination.resolve())
    size, sha = path.stat().st_size, digest(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert target.stat().st_size == size and digest(target) == sha, 'existing evidence differs: ' + str(target)
    else: shutil.copyfile(path, target)
    assert target.stat().st_size == size and digest(target) == sha
    return {'source': str(path), 'destination': str(target), 'bytes': size, 'sha256': sha, 'verified': True}

with ThreadPoolExecutor(max_workers=4) as pool: rows = list(pool.map(preserve, files))
manifest = {'registered_at': datetime.now(timezone.utc).isoformat(), 'destination': str(destination),
            'mode': 'APPEND_PRESERVE_NO_OVERWRITE_NO_SQLITE_OPEN', 'files': rows, 'excluded': excluded,
            'file_count': len(rows), 'bytes': sum(r['bytes'] for r in rows), 'all_verified': True,
            'protected_source_final': guard}
local = evidence / 'runtime-preservation-manifest.json'
local.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
target = destination / 'runtime-preservation-manifest.json'
assert not target.exists(), 'manifest already exists; do not overwrite'
shutil.copyfile(local, target)
assert digest(local) == digest(target)
print(json.dumps({'files': len(rows), 'bytes': manifest['bytes'], 'excluded': len(excluded), 'destination': str(destination), 'all_15_unchanged': True, 'actual19_checksum_unchanged': True, 'final_host_inventory_matches_method_proof': True}))
