from pathlib import Path
import hashlib, json, subprocess, concurrent.futures
root = Path('D:/dsh-proj/Roll')
source = Path.cwd().resolve()
out = root / '.scratch/roll-p0/evidence/continuation-2026-10-11/ticket30-sse-current-independent'
ev = source / '.scratch/roll-p0/evidence/30-sse-current-suspension'
def check(path, sha, size):
    path = Path(path).resolve()
    extended = Path('\\\\?\\' + str(path))
    with extended.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert digest == sha and extended.stat().st_size == size, str(path)
    return {'path': str(path), 'sha256': digest, 'bytes': size}
jobs = []
counts = []
for manifest_name, expected_count, expected_size, capture in [
    ('runtime-preservation-manifest.json', 2717, 420677469, 'continuation-ticket30-sse-current-suspension')]:
    rows = json.loads((ev / manifest_name).read_text(encoding='utf-8'))
    assert len(rows) == expected_count and sum(row['bytes'] for row in rows) == expected_size
    for row in rows:
        s, d = Path(row['source']).resolve(), Path(row['destination']).resolve()
        assert s.is_relative_to(source / '.scratch')
        assert s.relative_to(source / '.scratch').parts[0].startswith('t30s-')
        assert d.is_relative_to(root / '.roll-data/implementation-evidence' / capture)
        jobs.extend([(s, row['sha256'], row['bytes']), (d, row['sha256'], row['bytes'])])
    counts.append({'manifest': manifest_name, 'files': expected_count, 'bytes': expected_size})
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    archives = list(pool.map(lambda args: check(*args), jobs))
protected = json.loads((root / '.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text(encoding='utf-8'))[:15]
fixed = [check(repo / row['path'], row['sha256'], row['bytes']) for row in protected for repo in [source, root]]
original = check(root / '.roll-data/reconstructed19-v1/roll.sqlite3', 'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4', 165814272)
actual_raw=check(ev/'runtime/source-assessment/986c403e89bf4aab9f260034f1d301126daa0de9ff62926f90cf798768eeb958.raw','986c403e89bf4aab9f260034f1d301126daa0de9ff62926f90cf798768eeb958',13367)
original_paths=json.loads((ev/'git-original-identity.json').read_text())
result = {'source_oid': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'runtime_files': 2717, 'runtime_bytes': 420677469, 'source_destination_checks': len(archives), 'mismatches': 0,
    'batches': counts, 'archive_hashes': archives, 'protected_15_root_source': fixed,
    'original19_checksum_only': original,
    'actual_saved_public_raw': actual_raw, 'root_preserved_sqlite_connections': 0, 'prior13989_2570_2657_3048_archives_scanned': False}
(out / 'integrity.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in ['archive_hashes', 'protected_15_root_source', 'raw6_file_and_git_blob_checks']}))
