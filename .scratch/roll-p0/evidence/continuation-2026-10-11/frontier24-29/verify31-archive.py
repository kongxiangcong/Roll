"""Byte-only destination verification after managed worktree archive."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
BASE = ROOT / '.roll-data/implementation-evidence/31/worker-delivery'
TARGET = Path(r'C:\Users\72449\.codex\worktrees\ticket31-delivery\Roll')


def long_path(path):
    return Path('\\\\?\\' + str(path.resolve()))


def digest(path):
    path = long_path(path)
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return {'bytes': path.stat().st_size, 'sha256': value.hexdigest()}


def verify(item):
    base, row = item
    actual = digest(base / row['archived'])
    expected = {key: row[key] for key in ('bytes', 'sha256')}
    return None if actual == expected else {'path': row['archived'], 'actual': actual, 'expected': expected}


jobs, manifests = [], []
for base in (BASE, BASE / 'composition30'):
    path = base / 'archive-manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    manifests.append({'path': str(path.relative_to(ROOT)), **digest(path), 'files': len(manifest['files'])})
    jobs.extend((base, row) for row in manifest['files'])
with ThreadPoolExecutor(max_workers=8) as pool:
    differences = [row for row in pool.map(verify, jobs) if row]
protected = json.loads((ROOT / '.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text(encoding='utf-8'))[:15]
source_differences = [row['path'] for row in protected if digest(ROOT / row['path']) != {'bytes': row['bytes'], 'sha256': row['sha256']}]
original = digest(ROOT / '.roll-data/reconstructed19-v1/roll.sqlite3')
result = {'verification': 'DESTINATION_ONLY_AFTER_MANAGED_ARCHIVE', 'managed_source_exists': long_path(TARGET).exists(),
          'files': len(jobs), 'manifests': manifests, 'differences': differences, 'protected_source_differences': source_differences,
          'original19_checksum_only': original, 'sqlite_connections': 0}
(Path(__file__).parent / 'ticket31-archive-postflight.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'files': len(jobs), 'differences': len(differences), 'protected_differences': len(source_differences),
                  'source_exists': result['managed_source_exists'], 'original19': original}, ensure_ascii=False))
assert not result['managed_source_exists'] and not differences and not source_differences
assert original == {'bytes': 165814272, 'sha256': 'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'}
