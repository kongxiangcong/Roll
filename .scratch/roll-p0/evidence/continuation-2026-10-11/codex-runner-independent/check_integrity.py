from pathlib import Path
import hashlib, json, subprocess, concurrent.futures
root = Path('D:/dsh-proj/Roll')
source = Path.cwd().resolve()
out = root / '.scratch/roll-p0/evidence/continuation-2026-10-11/codex-runner-independent'
ev = source / '.scratch/roll-p0/evidence/continuation-2026-10-11/codex-runner-scope'
manifest = json.loads((ev / 'runtime-preservation.json').read_text(encoding='utf-8'))
browser = json.loads((ev / 'browser-manifest.json').read_text(encoding='utf-8'))
sources = {name: source / '.scratch' / name for name in ['crmr', 'crmg', 'crsf', 'crs25']}
sources['default-browser'] = Path(browser['data_root'])
assert sources['default-browser'].is_relative_to(source / 'backend/.roll-data')
target = Path(manifest['capture'])
assert target == root / '.roll-data/implementation-evidence/codex-runner-scope/runner-2026-10-11'
assert manifest['files'] == len(manifest['inventory']) == 540
assert manifest['bytes'] == sum(row['bytes'] for row in manifest['inventory']) == 44276137
def check(path, sha, size):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert digest == sha and path.stat().st_size == size, str(path)
    return {'path': str(path), 'sha256': digest, 'bytes': size}
jobs = []
for row in manifest['inventory']:
    name, relative = row['path'].split('/', 1)
    s, d = sources[name] / relative, target / row['path']
    assert s.resolve().is_relative_to(sources[name].resolve()) and d.resolve().is_relative_to(target)
    jobs.extend([(s, row['sha256'], row['bytes']), (d, row['sha256'], row['bytes'])])
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    archives = list(pool.map(lambda args: check(*args), jobs))
protected = json.loads((root / '.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text(encoding='utf-8'))[:15]
fixed = [check(repo / row['path'], row['sha256'], row['bytes']) for row in protected for repo in [source, root]]
original = check(root / '.roll-data/reconstructed19-v1/roll.sqlite3', 'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4', 165814272)
product = json.loads((ev / 'source-integrated-final.json').read_text(encoding='utf-8'))
product_checks = [check(repo / row['path'], row['sha256'], row['bytes']) for row in product for repo in [source, root]]
changed = subprocess.check_output(['git', 'diff', '--name-only', '371dd9c7c75d1fb5df9827a81dc580ddd5a62c63', 'HEAD'], text=True).splitlines()
assert all(path.startswith(('.scratch/roll-p0/evidence/continuation-2026-10-11/codex-runner-scope/',
    'backend/tests/', 'frontend/tests/', 'frontend/scripts/')) or path in ['backend/pyproject.toml',
    'frontend/playwright.config.ts', 'frontend/playwright.default.config.ts', 'docs/browser-acceptance.md',
    '.scratch/roll-p0/issues/13-backend-switch-isolation.md', '.scratch/roll-p0/issues/31-engineering-delivery.md'] for path in changed)
append = json.loads((ev / 'root-manifest-append.json').read_text(encoding='utf-8'))
root_manifest = check(append['path'], append['sha256'], append['bytes'])
result = {'source_oid': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'runtime_files': 540, 'runtime_bytes': 44276137, 'source_destination_checks': len(archives), 'mismatches': 0,
    'archive_hashes': archives, 'protected_15_root_source': fixed, 'original19_checksum_only': original,
    'product_sources': len(product), 'product_root_source_hashes': product_checks, 'product_source_changes': 0,
    'scoped_changed_paths': changed, 'root_manifest_append_hash': root_manifest,
    'historical_deselection_is_not_pass': True, 'root_preserved_sqlite_connections': 0}
(out / 'integrity.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in ['archive_hashes', 'protected_15_root_source', 'product_root_source_hashes', 'scoped_changed_paths']}))
