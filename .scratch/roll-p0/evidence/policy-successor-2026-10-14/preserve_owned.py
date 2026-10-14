"""Preserve only new owned METHOD test directories, after their processes exit."""
from pathlib import Path
import hashlib
import json
import shutil

workspace = Path(__file__).resolve().parents[4]
assert workspace.name == 't20-policy-successor'
target = Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/t20-policy-successor-20261014')
target.mkdir(parents=True, exist_ok=True)
evidence = Path(__file__).resolve().parent
def extended(path):
    return Path('\\\\?\\' + str(path.resolve()))

workspace_long, target_long = extended(workspace), extended(target)
roots = [p for p in (workspace_long/'.scratch').iterdir() if p.is_dir() and (
    p.name.startswith('policy-') or p.name.startswith('successor-shadow-') or p.name == 'successor-combined-final')]
manifest, excluded = [], []
for root in sorted(roots):
    for source in sorted(root.rglob('*')):
        if not source.is_file():
            continue
        relative = source.relative_to(workspace_long/'.scratch')
        if source.name in {'auth.json', '.env'}:
            excluded.append(str(relative))
            continue
        destination = target_long/relative
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            assert hashlib.sha256(destination.read_bytes()).hexdigest() == digest, relative
        else:
            shutil.copyfile(source, destination)
        assert destination.stat().st_size == source.stat().st_size
        assert hashlib.sha256(destination.read_bytes()).hexdigest() == digest
        manifest.append({'path': relative.as_posix(), 'length': source.stat().st_size, 'sha256': digest})
document = {'source': str(workspace), 'target': str(target), 'files': manifest,
    'file_count': len(manifest), 'bytes': sum(row['length'] for row in manifest),
    'mismatches': 0, 'excluded_credential_paths': excluded}
encoded = json.dumps(document, ensure_ascii=False, indent=2)
(evidence/'runtime-preservation.json').write_text(encoded, encoding='utf-8')
(target/'runtime-preservation.json').write_text(encoded, encoding='utf-8')
print(json.dumps({k: v for k, v in document.items() if k != 'files'}, ensure_ascii=False))
