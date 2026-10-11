"""Isolated reproduction of former current-action behavior; never edits live source."""
from pathlib import Path
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[5]
destination = root / '.scratch/r27-revival/backend'
assert destination.resolve().is_relative_to((root / '.scratch').resolve())
shutil.copytree(root / 'backend/src', destination / 'src', ignore=shutil.ignore_patterns('__pycache__'), dirs_exist_ok=False)
shutil.copyfile(root / 'backend/uv.lock', destination / 'uv.lock')
path = destination / 'src/roll/decisions/actions.py'
raw = path.read_bytes()
source = raw.decode().replace('\r\n', '\n')
old = "            if db.execute('SELECT 1 FROM action_invalidations WHERE decision_id=?', (decision['decision_id'],)).fetchone():\n                reasons.append('PREVIOUSLY_INVALIDATED_REQUIRES_NEW_ACTION')\n"
assert source.count(old) == 1
path.write_text(source.replace(old, ''), encoding='utf-8', newline='\n')
manifest = {'purpose': 'Public reproduction of former invalidation behavior with current resume implementation; not an unchanged historical commit',
            'original_actions_sha256': hashlib.sha256(raw).hexdigest(), 'reproduction_actions_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'removed_guard': old, 'source_copy': str(destination), 'provider_calls': 0}
(Path(__file__).parent / 'action-revival-reproduction.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps(manifest, indent=2))
