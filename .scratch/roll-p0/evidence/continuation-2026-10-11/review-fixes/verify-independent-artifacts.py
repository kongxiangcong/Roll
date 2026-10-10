"""Compile-only helpers and opaque proof of merger-owned METHOD profile files."""
import hashlib
import json
from pathlib import Path

SCOPE = Path(__file__).resolve().parent
ROOT = SCOPE.parents[4]
profiles = []
for name in ('independent-fixed-boundaries', 'independent-fixed-boundaries-final'):
    base = ROOT / '.roll-data/implementation-evidence/continuation-review-fixes' / name
    files = []
    for path in sorted(base.rglob('*')):
        if path.is_file():
            assert not path.is_symlink()
            raw = path.read_bytes()
            files.append({'path': path.relative_to(base).as_posix(), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    profiles.append({'profile': str(base), 'file_count': len(files), 'bytes': sum(item['bytes'] for item in files), 'files': files})
helpers = []
for name in ('copy-actual-corrected.py', 'independent-fixed-boundaries.py', 'prepare-corrected-successor.py', 'actual-review-corrected.py'):
    path = SCOPE / name
    raw = path.read_bytes()
    compile(raw.decode('utf-8'), str(path), 'exec')
    helpers.append({'path': name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'static_compile': 'PASS'})
result = {'status': 'PASS', 'helper_compilation': helpers, 'profiles': profiles,
    'actual_review_helper_executed': False, 'provider_calls': 0, 'secret_files_read': False}
(SCOPE / 'independent-artifacts-manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': result['status'], 'compiled_helpers': len(helpers), 'profile_files': [item['file_count'] for item in profiles], 'provider_calls': 0}))
