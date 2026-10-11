"""Raw source evidence only; never opens any SQLite profile."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[5]
protected = json.loads((root / '.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text(encoding='utf-8'))[:15]
for entry in protected:
    raw = (root / entry['path']).read_bytes()
    assert len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256'], entry['path']
sources = []
for folder in ['backend/src', 'frontend/src']:
    for path in sorted((root / folder).rglob('*')):
        if path.is_file() and path.suffix in {'.py', '.json', '.ts', '.tsx', '.css'}:
            raw = path.read_bytes()
            sources.append({'path': path.relative_to(root).as_posix(), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
Path(__file__).with_name(sys.argv[1]).write_text(json.dumps({'protected': protected, 'sources': sources}, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'protected_unchanged': len(protected), 'sources': len(sources)}))
