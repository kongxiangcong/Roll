from pathlib import Path
import hashlib, json, subprocess
root = Path('D:/dsh-proj/Roll')
out = root / '.scratch/roll-p0/evidence/continuation-2026-10-11/codex-runner-independent'
files = []
for runtime in [root / '.roll-data/rcri', root / '.roll-data/rcri-cancel']:
    assert runtime.is_dir()
    for path in sorted(runtime.rglob('*')):
        if path.is_file():
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            files.append({'path': str(path), 'sha256': digest, 'bytes': path.stat().st_size})
value = {'roots': [str(root / '.roll-data/rcri'), str(root / '.roll-data/rcri-cancel')],
    'file_count': len(files), 'total_bytes': sum(row['bytes'] for row in files), 'files': files,
    'root_preserved_sqlite_connections': 0, 'actual_provider_calls': 0, 'training_fits': 0,
    'source_oid': '31f3febcfee0e27ac5996feefe4ef6919cd4390e'}
(out / 'owned-runtime-manifest.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in value.items() if k != 'files'}))
