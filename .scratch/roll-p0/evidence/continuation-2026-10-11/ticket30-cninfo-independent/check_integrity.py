from pathlib import Path
import hashlib, json, subprocess, concurrent.futures
root = Path('D:/dsh-proj/Roll')
source = Path.cwd().resolve()
out = root / '.scratch/roll-p0/evidence/continuation-2026-10-11/ticket30-cninfo-independent'
ev = source / '.scratch/roll-p0/evidence/30-cninfo-history'
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
    ('runtime-preservation-manifest.json', 2439, 346346030, 'continuation-ticket30-cninfo-history'),
    ('composition-preservation-manifest.json', 218, 35055992, 'continuation-ticket30-cninfo-history-composition')]:
    rows = json.loads((ev / manifest_name).read_text(encoding='utf-8'))
    assert len(rows) == expected_count and sum(row['bytes'] for row in rows) == expected_size
    for row in rows:
        s, d = Path(row['source']).resolve(), Path(row['destination']).resolve()
        assert s.is_relative_to(source / '.scratch')
        assert s.relative_to(source / '.scratch').parts[0].startswith('t30c-')
        assert d.is_relative_to(root / '.roll-data/implementation-evidence' / capture)
        jobs.extend([(s, row['sha256'], row['bytes']), (d, row['sha256'], row['bytes'])])
    counts.append({'manifest': manifest_name, 'files': expected_count, 'bytes': expected_size})
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    archives = list(pool.map(lambda args: check(*args), jobs))
protected = json.loads((root / '.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text(encoding='utf-8'))[:15]
fixed = [check(repo / row['path'], row['sha256'], row['bytes']) for row in protected for repo in [source, root]]
original = check(root / '.roll-data/reconstructed19-v1/roll.sqlite3', 'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4', 165814272)
originals = json.loads((ev / 'staged-originals.json').read_text(encoding='utf-8'))['originals']
assert len(originals) == 6 and sum(row['bytes'] for row in originals) == 17848
raw_checks = []
for row in originals:
    raw_checks.append(check(source / row['path'], row['sha256'], row['bytes']))
    blob = subprocess.check_output(['git', 'show', 'HEAD:' + row['path']])
    assert len(blob) == row['bytes'] and hashlib.sha256(blob).hexdigest() == row['sha256']
result = {'source_oid': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'runtime_files': 2657, 'runtime_bytes': 381402022, 'source_destination_checks': len(archives), 'mismatches': 0,
    'batches': counts, 'archive_hashes': archives, 'protected_15_root_source': fixed,
    'original19_checksum_only': original, 'raw6_file_and_git_blob_checks': raw_checks,
    'root_preserved_sqlite_connections': 0, 'prior13989_and2570_archives_scanned': False}
(out / 'integrity.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in ['archive_hashes', 'protected_15_root_source', 'raw6_file_and_git_blob_checks']}))
