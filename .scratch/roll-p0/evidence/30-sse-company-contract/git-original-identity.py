"""Verify exact Git/working identity of four scoped public originals, no SQLite/network."""
import hashlib
import json
import subprocess
from pathlib import Path
folder = Path(__file__).resolve().parent
repo = folder.parents[3]
records = []
for prefix, sha, size in [
    ('backend/src/roll/market/reference/sse-company-contract/', '72bdf9f924465e3c848577fa4ec5285c163474a79be9bee4a0500a2ecb53f55b', 39826),
    ('backend/src/roll/market/reference/sse-company-contract/', '478fb2a72fc5a3725088adb208756e88171f79628956a9f5ca67c900d37def2f', 277193),
    ('.scratch/roll-p0/evidence/30-sse-company-contract/runtime/source-assessment/', 'bc0971238819277c2b9d6773e341c6d12496adb7991fc897000974cbb2942403', 409),
    ('.scratch/roll-p0/evidence/30-sse-company-contract/runtime/source-assessment/', '4e4bd76727f03b989b98f923c65c2d3d99816f6683172dba4ab7e148b6c2fb7a', 1732),
]:
    path = prefix + sha + '.raw'
    blob = subprocess.run(['git', 'show', 'HEAD:' + path], cwd=repo, capture_output=True, check=True).stdout
    assert (repo / path).read_bytes() == blob and len(blob) == size and hashlib.sha256(blob).hexdigest() == sha
    records.append({'path': path, 'sha256': sha, 'bytes': size, 'git_blob_identical': True})
(folder / 'git-original-identity.json').write_text(json.dumps({'originals': records,
    'network_calls': 0, 'sqlite_opened': False}, indent=2) + '\n', encoding='utf-8', newline='\n')
print('FOUR_EXACT_PUBLIC_ORIGINAL_GIT_BLOBS_IDENTICAL')
