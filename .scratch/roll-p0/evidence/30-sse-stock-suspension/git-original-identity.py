"""Compare committed actual public originals to working bytes; no database/network."""
import hashlib
import json
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parents[3]
records = []
for name, size in [
    ('f45a2a21a972c1150d69db7a60e8506932974bc1bdd216d3f6d052a5cdc7fc22', 599),
    ('7fd45879b5af75c7e0cb7f4c92ce9ad6fa31ddca8ad472deb83b66f3bbfd1c6f', 481),
]:
    path = folder / 'runtime/source-assessment' / (name + '.raw')
    relative = path.relative_to(repo).as_posix()
    blob = subprocess.run(['git', 'show', 'HEAD:' + relative], cwd=repo,
                          capture_output=True, check=True).stdout
    working = path.read_bytes()
    assert working == blob and len(blob) == size
    assert hashlib.sha256(blob).hexdigest() == name
    records.append({'path': relative, 'sha256': name, 'bytes': size,
                    'git_blob_identical': True})
(folder / 'git-original-identity.json').write_text(
    json.dumps({'originals': records, 'network_calls': 0, 'sqlite_opened': False},
               indent=2) + '\n', encoding='utf-8', newline='\n')
print('TWO_ACTUAL_PUBLIC_ORIGINAL_GIT_BLOBS_IDENTICAL')
