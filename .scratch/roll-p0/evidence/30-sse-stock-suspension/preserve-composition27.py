"""Append only the new accepted27 composition namespace; bytewise, no SQLite open."""
import hashlib
import json
import os
import shutil
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parents[3]
source = repo / '.scratch/t30i-composition27'
target = Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/continuation-ticket30-sse-stock-suspension-composition27')

def extended(path):
    return Path('\\\\?\\' + str(path.resolve()))

def digest(path):
    h = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(1048576):
            h.update(chunk)
            size += len(chunk)
    return {'sha256': h.hexdigest(), 'bytes': size}

records = []
origin = extended(source)
assert origin.is_dir() and not origin.is_symlink() and not origin.is_junction()
for current, directories, files in os.walk(origin):
    current = Path(current)
    assert not current.is_symlink() and not current.is_junction()
    for name in directories:
        child = current / name
        assert not child.is_symlink() and not child.is_junction()
    for name in files:
        child = current / name
        assert not child.is_symlink()
        destination = extended(target) / child.relative_to(origin)
        expected = digest(child)
        destination.parent.mkdir(parents=True, exist_ok=True)
        assert not destination.is_symlink() and not destination.is_junction()
        if destination.exists():
            assert digest(destination) == expected
        else:
            shutil.copyfile(child, destination)
        assert digest(destination) == expected
        records.append({'source': str(child).removeprefix('\\\\?\\'),
                        'destination': str(destination).removeprefix('\\\\?\\'), **expected})
receipt = {'scope': 'NEW_ACCEPTED27_COMPOSITION_ONLY', 'files': len(records),
           'bytes': sum(r['bytes'] for r in records), 'sha_or_length_mismatches': 0,
           'target': str(target), 'source_directory': str(source),
           'previous_preservation_targets_read_or_written': False,
           'network_calls': 0, 'sqlite_opened': False, 'own_process_exited': True}
for filename, value in [('composition27-preservation-manifest.json', records),
                        ('composition27-preservation-receipt.json', receipt)]:
    (folder / filename).write_text(json.dumps(value, indent=2) + '\n',
                                 encoding='utf-8', newline='\n')
print(json.dumps({k: receipt[k] for k in ['files', 'bytes', 'sha_or_length_mismatches']}))
