"""Inventory only ticket16's retained native/browser directories, without moving originals."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from roll.runtime.backups import file_path

WORKTREE = Path(__file__).resolve().parents[4]
RUNTIME = WORKTREE / 'backend/.roll-data'
REPORT = Path(__file__).with_name('runtime-retention.json')
entries = []
for name, required, scope in [
    ('acceptance-16-browser', False, 'Earlier actual Chrome two-phase history; prototype manifest metadata may be absent.'),
    ('acceptance-16-browser-final', True, 'Final actual Chrome export/staging/restart RECOVERY_LOCK, isolated account 1.'),
    ('acceptance-16-process-files', True, 'Exact copy of nine stopped real OS cases; old source/DB/WAL/bundles/raw/process logs.')
]:
    root = RUNTIME / name
    extended = file_path(root)
    files = []
    for path in sorted(extended.rglob('*')):
        if not path.is_file():
            continue
        if path.is_symlink():
            raise RuntimeError('Do not inventory a linked runtime file')
        relative = path.relative_to(extended).as_posix()
        if '/tasks/' in '/' + relative or relative.endswith('auth.json'):
            raise RuntimeError('Credential/task file is outside ticket16 retained scope')
        raw = path.read_bytes()
        files.append({'path': relative, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    entries.append({'source': str(root), 'required': required, 'scope': scope,
                    'file_count': len(files), 'byte_total': sum(row['bytes'] for row in files), 'files': files})
result = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'worktree': str(WORKTREE),
          'keep_until': 'Parent confirms permanent root copy and SHA identity; no cleanup performed here.',
          'classification': 'Financial inputs are synthetic METHOD only; native process/file and actual Chrome evidence are real. Old source.py is reproducibility source, not a runtime attachment; SDK/key/Temp task workspaces are excluded.',
          'native_original_copy_report': 'native-file-preservation.json',
          'directories': entries, 'file_count': sum(row['file_count'] for row in entries),
          'byte_total': sum(row['byte_total'] for row in entries)}
REPORT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print(json.dumps({key: value for key, value in result.items() if key != 'directories'}, ensure_ascii=False))
print(json.dumps([{key: value for key, value in row.items() if key != 'files'} for row in entries], ensure_ascii=False))
