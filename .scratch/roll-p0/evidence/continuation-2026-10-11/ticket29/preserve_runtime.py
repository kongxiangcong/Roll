"""Stopped owned union, raw-byte preservation; no SQLite connection or credentials."""
import hashlib, json, os, shutil, stat
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
root = Path('D:/dsh-proj/Roll')
tree = root / '.scratch/worktrees/ticket29'
out = tree / '.scratch/roll-p0/evidence/continuation-2026-10-11/ticket29'
destination = root / '.roll-data/implementation-evidence/ticket29-r01'
assert json.loads((out / 'cim-final.json').read_text(encoding='utf-8-sig'))['exact_owned_matches'] == 0
assert destination.parent == root / '.roll-data/implementation-evidence'

def native(path): return Path('\\\\?\\' + str(path))
def guard(path):
    result = native(path).lstat()
    assert not result.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT, str(path)
    return result
def digest(path):
    with native(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
guard(destination.parent)
assert not destination.exists(), 'Fresh preservation identity required'
sources = sorted(p for p in (tree / '.scratch').iterdir() if p.is_dir() and p.name.startswith('t29'))
sources += [tree / 'frontend/test-results', tree / 'frontend/dist']
jobs, exclusions = [], []
for source in sources:
    guard(source)
    for directory, dirs, files in os.walk(native(source), followlinks=False):
        current = Path(str(Path(directory))[4:]); guard(current)
        for name in dirs: guard(current / name)
        for name in files:
            path = current / name; info = guard(path)
            assert stat.S_ISREG(info.st_mode)
            if (path.parent.name == 'notification-private' and path.name in {'channel.json', 'channel.lock'}) or name.lower() in {'auth.json', 'credentials.json', 'secrets.json', '.env'}:
                exclusions.append({'path':str(path), 'bytes_metadata_only':info.st_size, 'opened_hashed_copied':False})
                continue
            jobs.append((path, destination / path.relative_to(tree)))

def copy(item):
    source, saved = item
    size, sha = guard(source).st_size, digest(source)
    native(saved.parent).mkdir(parents=True, exist_ok=True)
    cursor = saved.parent
    while cursor.is_relative_to(destination): guard(cursor); cursor = cursor.parent
    shutil.copy2(native(source), native(saved))
    assert guard(source).st_size == guard(saved).st_size == size and digest(source) == digest(saved) == sha
    return {'source':str(source), 'preserved':str(saved), 'bytes':size, 'sha256':sha}
with ThreadPoolExecutor(max_workers=8) as pool: entries = list(pool.map(copy, jobs))
value = {'source_namespaces':[str(p.relative_to(tree)) for p in sources], 'destination':str(destination),
         'files':len(entries), 'bytes':sum(e['bytes'] for e in entries), 'mismatches':0,
         'entries':entries, 'exact_private_metadata_exclusions':exclusions, 'sqlite_connections':0,
         'credentials_opened_hashed_copied':0, 'all_existing_failed_and_successful_namespaces_preserved':True,
         'note':'Playwright replaces test-results on each run; original run logs and all surviving runtime profiles preserved. Prior final browser metadata separately retained.'}
raw = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
(out / 'runtime-preservation.json').write_text(raw, encoding='utf-8')
native(destination / 'manifest.json').write_text(raw, encoding='utf-8')
print(json.dumps({'files':value['files'], 'bytes':value['bytes'], 'mismatches':0,
                  'manifest_bytes':len(raw.encode()), 'manifest_sha256':hashlib.sha256(raw.encode()).hexdigest(), 'credentials_exclusions':len(exclusions)}))
