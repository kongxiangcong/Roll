"""Copy only stopped ticket13 manifest files; no personal credential files copied."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

root=Path('D:/dsh-proj/Roll').resolve()
worktree=(root/'.scratch/worktrees/13-switch').resolve()
source=(worktree/'backend/.roll-data').resolve()
destination=(root/'backend/.roll-data/implementation-evidence/13').resolve()
assert source.is_relative_to(worktree)
assert destination.is_relative_to((root/'backend/.roll-data/implementation-evidence').resolve())
manifest=json.loads((worktree/'.scratch/roll-p0/evidence/13/runtime-inventory.json').read_text(encoding='utf-8'))
assert Path(manifest['source_directory']).resolve()==source
assert manifest['file_count']==464 and manifest['bytes']==723323443
assert len(manifest['directories'])==16 and manifest['all_runtime_stopped']
for run in manifest['runs']:
    assert run['status']!='RUNNING' and run['remaining_pids']==[] and not run['task_root_exists']
secrets=[]
for line in (root/'.env').read_text(encoding='utf-8-sig').splitlines():
    line=line.strip().removeprefix('export ').lstrip()
    name,sep,value=line.partition('=')
    if sep and name.strip() in {'DEEPSEEK_API_KEY','FUYAO_API_KEY'}:
        value=value.strip()
        value=value[1:value.find(value[0],1)] if value.startswith(('"',"'")) else re.split(r'\s+#',value,maxsplit=1)[0].rstrip()
        if value:secrets.append(value.encode())
assert len(secrets)==2
auth=json.loads(Path('C:/Users/72449/.codex/auth.json').read_text(encoding='utf-8'))
auth_tokens=[auth['tokens'][name].encode() for name in ['access_token','id_token','refresh_token'] if auth.get('tokens',{}).get(name)]
assert len(auth_tokens)==3
secrets+=auth_tokens
overlap=max(map(len,secrets))-1
def check_bytes(content):
    assert not any(value in content for value in secrets),'CREDENTIAL_MATCH'
def digest(path):
    checksum=hashlib.sha256(); tail=b''; size=0
    with path.open('rb') as stream:
        while chunk:=stream.read(2*1024*1024):
            size+=len(chunk); checksum.update(chunk)
            combined=tail+chunk; check_bytes(combined); tail=combined[-overlap:]
    return size,checksum.hexdigest()
paths=subprocess.check_output(['git','diff','--name-only','633a714','14568b1582f9500ee091dabe2b741224e95e5322'],cwd=root,text=True).splitlines()
for path in paths:check_bytes(subprocess.check_output(['git','show','14568b1582f9500ee091dabe2b741224e95e5322:'+path],cwd=root))
assert subprocess.run(['git','check-ignore','--quiet','.env'],cwd=root).returncode==0
rows=[]; expected=set()
for item in manifest['files']:
    relative=Path(item['relative'])
    assert not relative.is_absolute() and '..' not in relative.parts
    assert relative.parts[0] in manifest['directories']
    origin=(source/relative).resolve(); target=(destination/relative).resolve()
    assert origin.is_relative_to(source) and target.is_relative_to(destination)
    assert origin.name.lower() not in {'.env','auth.json','credentials.json'}
    assert not origin.is_symlink() and not origin.is_junction()
    size,checksum=digest(origin)
    assert (size,checksum)==(item['bytes'],item['sha256'])
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():shutil.copy2(origin,target)
    assert digest(target)==(size,checksum)
    rows.append(item); expected.add(relative.as_posix())
actual=set()
for name in manifest['directories']:
    directory=(source/name).resolve()
    assert directory.is_relative_to(source) and directory.is_dir()
    for path in directory.rglob('*'):
        assert not path.is_symlink() and not path.is_junction()
        if path.is_file():actual.add(path.relative_to(source).as_posix())
assert actual==expected
assert {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}==expected
report={'source':str(source),'destination':str(destination),'directories':manifest['directories'],'file_count':len(rows),'bytes':sum(r['bytes'] for r in rows),'sha256_mismatches':0,'credential_matches':0,'credential_files_copied':0,'env_keys_scanned':2,'authorized_auth_tokens_scanned':len(auth_tokens),'changed_git_blobs_scanned':len(paths),'root_env_ignored':True,'source_retained':True,'source_other_runtime_directories_untouched':True,'files':rows}
(root/'.scratch/roll-p0/evidence/continuation-2026-10-08/merge-13-runtime.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:v for k,v in report.items() if k not in {'files','directories'}}))
