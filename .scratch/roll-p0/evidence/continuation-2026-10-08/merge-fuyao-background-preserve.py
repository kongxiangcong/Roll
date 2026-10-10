"""Preserve exact own Fuyao manifest; compare actual credentials only in memory."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

root = Path('D:/dsh-proj/Roll').resolve()
worktree = root / '.scratch/worktrees/fuyao-data'
source = (worktree / 'backend/.roll-data').resolve()
target = (root / 'backend/.roll-data/implementation-evidence/fuyao-background').resolve()
assert source.is_relative_to(worktree.resolve())
assert target.is_relative_to((root / 'backend/.roll-data/implementation-evidence').resolve())
manifest = json.loads((worktree / '.scratch/roll-p0/evidence/fuyao/runtime-preservation-background.json').read_text(encoding='utf-8'))
assert Path(manifest['runtime_root']).resolve() == source
assert manifest['count'] == 60 and manifest['bytes'] == 5079079
secrets = []
for line in (root / '.env').read_text(encoding='utf-8-sig').splitlines():
    line = line.strip()
    if line.startswith('export '): line = line[7:].lstrip()
    name, separator, value = line.partition('=')
    if separator and re.search(r'KEY|TOKEN|SECRET|PASSWORD', name, re.I):
        value = value.strip()
        if value.startswith(('"', "'")): value = value[1:value.find(value[0], 1)]
        else: value = re.split(r'\s+#', value, maxsplit=1)[0].rstrip()
        if value: secrets.append(value.encode())
assert len(secrets) >= 2
def safe(content):
    assert not any(secret in content for secret in secrets), 'CREDENTIAL_MATCH'
scans = {}
for branch in ['67c4739c2b1355e17e0e5e088cb1020df402e778']:
    paths = subprocess.check_output(['git', 'diff', '--name-only', 'd0167ce', branch], cwd=root, text=True).splitlines()
    for path in paths: safe(subprocess.check_output(['git', 'show', branch + ':' + path], cwd=root))
    scans[branch] = len(paths)
assert subprocess.run(['git', 'check-ignore', '--quiet', '.env'], cwd=root).returncode == 0
rows=[]; expected=set()
for item in manifest['files']:
    relative=Path(item['relative_path'])
    assert not relative.is_absolute() and '..' not in relative.parts
    origin=(source/relative).resolve(); destination=(target/relative).resolve()
    assert origin.is_relative_to(source) and destination.is_relative_to(target)
    assert not origin.is_symlink() and origin.name.lower() not in {'.env','auth.json','credentials.json'}
    assert Path(item['source_path']).resolve() == origin
    content=origin.read_bytes(); safe(content)
    digest=hashlib.sha256(content).hexdigest()
    assert len(content)==item['bytes'] and digest==item['sha256']
    expected.add(relative.as_posix())
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists(): assert destination.read_bytes()==content
    else: shutil.copy2(origin,destination)
    assert destination.stat().st_size==len(content)
    assert hashlib.sha256(destination.read_bytes()).hexdigest()==digest
    rows.append({'relative':relative.as_posix(),'bytes':len(content),'sha256':digest})
# Added manifest is a subset; preserve and verify earlier 181 destination files without writes.
prior=json.loads((worktree/'.scratch/roll-p0/evidence/fuyao/runtime-preservation.json').read_text(encoding='utf-8'))
assert len(prior['files'])==181
for item in prior['files']:
    original=(source/item['relative_path']).resolve()
    preserved=(root/'backend/.roll-data/implementation-evidence/fuyao'/item['relative_path']).resolve()
    for path in [original,preserved]:
        assert path.stat().st_size==item['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
assert {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}==expected|{Path(item['relative_path']).as_posix() for item in prior['files']}
assert {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}==expected
report={'source':str(source),'destination':str(target),'file_count':len(rows),'bytes':sum(row['bytes'] for row in rows),'sha256_mismatches':0,'credential_matches':0,'credential_files_copied':0,'root_env_ignored':True,'changed_git_blobs_scanned':scans,'source_retained':True,'files':rows}
(root/'.scratch/roll-p0/evidence/continuation-2026-10-08/merge-fuyao-background-runtime.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({key:value for key,value in report.items() if key!='files'}))
