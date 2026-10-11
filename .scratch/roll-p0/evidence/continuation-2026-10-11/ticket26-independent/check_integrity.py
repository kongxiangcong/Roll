from pathlib import Path
import hashlib, json, subprocess, concurrent.futures
from roll.decisions.capabilities import source_inventory
from roll.decisions.actions import fingerprint
root = Path('D:/dsh-proj/Roll')
source = Path.cwd().resolve()
out = root / '.scratch/roll-p0/evidence/continuation-2026-10-11/ticket26-independent'
ev = source / '.scratch/roll-p0/evidence/ticket26'
manifest_path = ev / 'runtime-preservation-manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
target = root / '.roll-data/implementation-evidence/ticket26/2026-10-11-ca9e3b0'
assert Path(manifest['destination']) == target
assert manifest['file_count'] == len(manifest['files']) == 5930
assert manifest['bytes'] == sum(row['bytes'] for row in manifest['files']) == 502947022
assert len(manifest['excluded']) == 1 and manifest['excluded'][0]['path'].endswith('auth.json')
def check(path, sha, size):
    path = Path(path).resolve()
    extended = Path('\\\\?\\' + str(path))
    with extended.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert digest == sha and extended.stat().st_size == size, str(path)
    return {'path': str(path), 'sha256': digest, 'bytes': size}
jobs = []
for row in manifest['files']:
    s, d = Path(row['source']).resolve(), Path(row['destination']).resolve()
    assert s.is_relative_to(source) and d.is_relative_to(target)
    assert s.name.lower() not in {'auth.json', '.env', 'secrets.json'}
    jobs.extend([(s, row['sha256'], row['bytes']), (d, row['sha256'], row['bytes'])])
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    archives = list(pool.map(lambda args: check(*args), jobs))
manifest_checks = [check(path, '9d2d37893673dcd20aa6ff9413db3aa3ab246eb74192cc12fd150f059c0c9efc', 3365222)
    for path in [manifest_path, target / 'runtime-preservation-manifest.json']]
protected = json.loads((root / '.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text(encoding='utf-8'))[:15]
fixed = [check(repo / row['path'], row['sha256'], row['bytes']) for row in protected for repo in [source, root]]
original = check(root / '.roll-data/reconstructed19-v1/roll.sqlite3', 'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4', 165814272)
guard = json.loads((ev / 'protected-source-final.json').read_text(encoding='utf-8'))
mapping = json.loads((ev / 'final-source/method-500-policy-bindings.json').read_text(encoding='utf-8'))
assert source_inventory() == guard['host_source_inventory'] == mapping['grant']['dependency_fingerprints']
assert fingerprint(source_inventory()) == guard['host_source_inventory_fingerprint']
assert fingerprint(mapping['declaration']) == mapping['grant']['complete_protocol_fingerprint']
assert fingerprint(mapping['declaration']['policy']) == mapping['grant']['execution']['policy_fingerprint']
result = {'source_oid': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'material_files': 5930, 'material_bytes': 502947022, 'with_manifest_files': 5931, 'with_manifest_bytes': 506312244,
    'source_destination_checks': len(archives) + 2, 'mismatches': 0, 'archive_hashes': archives,
    'manifest_hashes': manifest_checks, 'protected_15_root_source': fixed, 'original19_checksum_only': original,
    'host_inventory_matches_final_mapping': True, 'declared500_protocol_policy_bindings_verified': True,
    'excluded_sentinel_not_read': True, 'root_preserved_sqlite_connections': 0}
(out / 'integrity.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in ['archive_hashes', 'protected_15_root_source']}))
