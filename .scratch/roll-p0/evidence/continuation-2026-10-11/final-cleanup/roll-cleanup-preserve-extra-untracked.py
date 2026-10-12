import hashlib
import json
import os
import shutil
import stat
from pathlib import Path

v = Path(__file__).parent
root = Path('D:/dsh-proj/Roll')
coverage = json.loads((v/'roll-cleanup-v9c-coverage-only.json').read_text(encoding='utf-8-sig'))
rows = coverage['uncovered']
assert len(rows) == 3802 and sum(r['private_candidate'] for r in rows) == 115
destination_base = root / '.roll-data/implementation-evidence/final-cleanup-residual-20261012'
assert not destination_base.exists(), 'Never replace prior evidence'
manifest = {}
total_bytes = 0
def extended(path):
    return '\\\\?\\' + os.path.abspath(path)
def regular(path):
    p = Path(path)
    for current in [p, *p.parents]:
        meta = os.stat(extended(current), follow_symlinks=False)
        assert not meta.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT, str(current)
    assert os.path.isfile(extended(p)), str(p)
for row in rows:
    if row['private_candidate']:
        continue
    tree = row['tree']
    assert tree in {'ticket25','ticket26','codex-runner-scope','ticket28'}
    rel = Path(row['relative'])
    assert not rel.is_absolute() and '..' not in rel.parts
    source_base = root / '.scratch/worktrees' / tree
    source = Path(row['source'])
    assert source == source_base / rel
    # Explicit observed public outputs only; no broad directory copy.
    assert row['relative'].startswith(('frontend/dist/','frontend/test-results/','backend/.test-tmp-notifications-'))
    assert source.name not in {'auth.json','method-auth.json','chatgpt.json','channel.json','channel.lock'}
    assert not any(x == 'notification-private' or x.startswith('.env') for x in rel.parts)
    regular(source)
    before = os.stat(extended(source))
    assert before.st_size == row['bytes']
    with open(extended(source), 'rb') as f:
        original_sha = hashlib.file_digest(f, 'sha256').hexdigest()
    target = destination_base / tree / rel
    os.makedirs(extended(target.parent), exist_ok=True)
    shutil.copyfile(extended(source), extended(target))
    with open(extended(target), 'rb') as f:
        target_sha = hashlib.file_digest(f, 'sha256').hexdigest()
    after = os.stat(extended(source))
    assert before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns
    assert original_sha == target_sha and os.stat(extended(target)).st_size == before.st_size
    manifest.setdefault(tree, []).append(dict(source=str(source), destination=str(target), bytes=before.st_size, sha256=original_sha))
    total_bytes += before.st_size
    if sum(map(len, manifest.values())) % 500 == 0:
        print(json.dumps(dict(copied=sum(map(len, manifest.values())))), flush=True)
assert sum(map(len, manifest.values())) == 3687
(v/'roll-cleanup-extra-untracked-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
receipt = dict(state='PUBLIC_RESIDUALS_PRESERVED', count=3687, bytes=total_bytes,
    partitions={k:dict(count=len(a), bytes=sum(r['bytes'] for r in a)) for k,a in manifest.items()},
    source_provenance='Exact full metadata coverage from accepted source OIDs; frontend current generated build/browser artifacts; Ticket28 own named historical test profiles and browser failures.',
    private_metadata_rows_skipped=115, private_reads=0, private_hashes=0, private_copies=0,
    sqlite_connections=0, business_tests=0, provider_calls=0, processes_stopped=0,
    source_and_target_sha_mismatches=0, source_byte_sweep=1, copied_byte_sweep=1,
    deletion=False)
(v/'roll-cleanup-extra-untracked-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(receipt, ensure_ascii=False))
