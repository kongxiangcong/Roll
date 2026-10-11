"""Preserve only this implementer's stopped runtime bytes; no SQLite connection."""
import hashlib
import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[5]
workspace = Path('D:/dsh-proj/Roll').resolve()
destination = workspace / '.roll-data/implementation-evidence/ticket27-r02'
assert root == workspace / '.scratch/worktrees/ticket27'
assert destination.resolve().is_relative_to(workspace / '.roll-data/implementation-evidence')
assert not destination.exists(), 'Never overwrite earlier preserved runtime'
owned = sorted(p for p in (root / '.scratch').iterdir() if p.is_dir() and (
    re.fullmatch(r'p27[rg]\d+', p.name) or p.name == 'r27-revival' or p.name.startswith('t27-browser-')))
owned += [root / 'frontend/test-results', root / 'frontend/dist']
excluded_names = {'auth.json', 'credentials.json', 'credentials', 'tokens.json', 'cookies.json',
                  '.env', '.env.local', '.env.production', 'secrets.json'}
excluded_dirs = {'.aws', '.codex', '.agents', 'node_modules', '.venv', 'credentials', 'secrets'}
entries, exclusions, jobs = [], [], []
destination.mkdir(parents=True)
for directory in owned:
    assert directory.resolve().is_relative_to(root) and not directory.is_symlink(), directory
    if not directory.exists():
        continue
    for source in sorted(directory.rglob('*')):
        relative = source.relative_to(root)
        parts = {part.lower() for part in relative.parts}
        if source.name.lower() in excluded_names or parts & excluded_dirs:
            if source.is_file():
                exclusions.append(relative.as_posix())
            continue
        if source.is_symlink():
            raise RuntimeError(f'Unexpected runtime symlink: {relative}')
        if not source.is_file():
            continue
        jobs.append(source)

def preserve_file(source):
    # Independent files only. No concurrent database or manifest writers.
    relative = source.relative_to(root)
    native_source = Path('\\\\?\\' + str(source))
    raw = native_source.read_bytes()
    target = destination / relative
    native_target = Path('\\\\?\\' + str(target))
    native_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(native_source, native_target)
    copied = native_target.read_bytes()
    assert copied == raw, relative
    return {'source': relative.as_posix(), 'preserved': target.relative_to(workspace).as_posix(),
            'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

with ThreadPoolExecutor(max_workers=8) as executor:
    entries = list(executor.map(preserve_file, jobs))
manifest = {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'source_root': str(root),
            'destination_root': str(destination), 'sqlite_connections': 0,
            'credential_content_reads': 0, 'directories': [p.relative_to(root).as_posix() for p in owned],
            'exclusions': exclusions, 'files': len(entries), 'bytes': sum(e['bytes'] for e in entries),
            'entries': entries}
payload = (json.dumps(manifest, indent=2) + '\n').encode()
(destination / 'manifest.json').write_bytes(payload)
Path(__file__).with_name('runtime-preservation-manifest.json').write_bytes(payload)
receipt = {'manifest': str(destination / 'manifest.json'), 'bytes': len(payload),
           'sha256': hashlib.sha256(payload).hexdigest(), 'files': manifest['files'],
           'runtime_bytes': manifest['bytes'], 'exclusions': exclusions, 'mismatches': 0}
Path(__file__).with_name('runtime-preservation-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
print(json.dumps(receipt))
