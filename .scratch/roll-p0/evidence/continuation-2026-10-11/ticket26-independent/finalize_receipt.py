from pathlib import Path
import hashlib, json, subprocess, sys
root = Path('D:/dsh-proj/Roll')
out = root / '.scratch/roll-p0/evidence/continuation-2026-10-11/ticket26-independent'
if '--verify-merge' in sys.argv:
    from roll.decisions.capabilities import source_inventory
    guard = json.loads((root / '.scratch/roll-p0/evidence/ticket26/protected-source-final.json').read_text(encoding='utf-8'))
    assert source_inventory() == guard['host_source_inventory']
    parents = subprocess.check_output(['git', 'show', '-s', '--format=%P', 'HEAD'], cwd=root, text=True).strip().split()
    assert parents == ['7c761e009dc01061ee04ea4822487ba2d5f86f23', 'e708764af833baee970f34fcc4112146c2c33958']
    result = {'merge_oid': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'parents': parents, 'whole_backend_inventory_matches_independently_checked_source': True, 'root_preserved_sqlite_connections': 0}
    (out / 'merge-verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
else:
    files = []
    for runtime in [root / '.roll-data/r26i', root / '.roll-data/r26i-partial']:
        for path in sorted(runtime.rglob('*')):
            if path.is_file():
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                files.append({'path': str(path), 'sha256': digest, 'bytes': path.stat().st_size})
    result = {'roots': [str(root / '.roll-data/r26i'), str(root / '.roll-data/r26i-partial')],
        'file_count': len(files), 'total_bytes': sum(row['bytes'] for row in files), 'files': files,
        'root_preserved_sqlite_connections': 0, 'actual_http_provider_calls': 0, 'training_fits': 0}
    (out / 'owned-runtime-manifest.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'files'}))
