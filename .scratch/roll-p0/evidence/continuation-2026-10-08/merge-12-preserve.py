"""Verify ticket 12 scoped changes and preserve only its manifest-listed stopped runtime."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

root = Path('D:/dsh-proj/Roll').resolve()
worktree = root / '.scratch/worktrees/12-live'
source = (worktree / 'backend/.roll-data/12-live').resolve()
target = (root / 'backend/.roll-data/implementation-evidence/12-live').resolve()
assert source.is_relative_to(worktree.resolve())
assert target.is_relative_to((root / 'backend/.roll-data/implementation-evidence').resolve())
manifest = json.loads((worktree / '.scratch/roll-p0/evidence/12/live/runtime-inventory.json').read_text(encoding='utf-8'))
assert Path(manifest['source_directory']).resolve() == source
assert manifest['file_count'] == 146 and manifest['bytes'] == 6011362
# Values are compared only in memory. No credential contents enter report/stdout.
secrets = []
for line in (root / '.env').read_text(encoding='utf-8-sig').splitlines():
    line = line.strip()
    if line.startswith('export '):
        line = line[7:].lstrip()
    name, sep, value = line.partition('=')
    if sep and re.search(r'KEY|TOKEN|SECRET|PASSWORD', name, re.I):
        value = value.strip()
        if value.startswith(('"', "'")):
            value = value[1:value.find(value[0], 1)]
        else:
            value = re.split(r'\s+#', value, maxsplit=1)[0].rstrip()
        if value:
            secrets.append(value.encode())
assert len(secrets) >= 2
def safe(content):
    assert not any(secret in content for secret in secrets), 'CREDENTIAL_MATCH'
paths = subprocess.check_output(['git', 'diff', '--name-only', '6842461', '0d1385d'], cwd=root, text=True).splitlines()
for path in paths:
    safe(subprocess.check_output(['git', 'show', '0d1385d:' + path], cwd=root))
assert subprocess.run(['git', 'check-ignore', '--quiet', '.env'], cwd=root).returncode == 0
rows = []
expected = set()
for item in manifest['files']:
    relative = Path(item['relative'])
    assert not relative.is_absolute() and '..' not in relative.parts
    origin = (source / relative).resolve()
    destination = (target / relative).resolve()
    assert origin.is_relative_to(source) and destination.is_relative_to(target)
    assert not origin.is_symlink()
    assert origin.name.lower() not in {'.env', 'auth.json', 'credentials.json'}
    content = origin.read_bytes()
    safe(content)
    digest = hashlib.sha256(content).hexdigest()
    assert len(content) == item['bytes'] and digest == item['sha256']
    expected.add(relative.as_posix())
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        assert destination.read_bytes() == content
    else:
        shutil.copy2(origin, destination)
    assert destination.stat().st_size == len(content)
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == digest
    rows.append({'relative': relative.as_posix(), 'bytes': len(content), 'sha256': digest})
assert {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()} == expected
assert {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()} == expected
report = {'source': str(source), 'destination': str(target), 'file_count': len(rows), 'bytes': sum(row['bytes'] for row in rows), 'sha256_mismatches': 0, 'credential_matches': 0, 'credential_files_copied': 0, 'root_env_ignored': True, 'changed_git_blobs_scanned': len(paths), 'source_retained': True, 'files': rows}
output = root / '.scratch/roll-p0/evidence/continuation-2026-10-08/merge-12-runtime.json'
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: value for key, value in report.items() if key != 'files'}))
