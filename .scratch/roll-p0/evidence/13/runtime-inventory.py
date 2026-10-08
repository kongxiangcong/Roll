"""Inventory only ticket13 stopped isolated runtimes; credential matches are booleans."""
from pathlib import Path
import hashlib
import json
import re
import sqlite3
import subprocess

ROOT=Path(__file__).resolve().parents[4]
DATA=ROOT/'backend/.roll-data'
NAMES=['13-browser-offline','13-browser-offline-v2','13-browser-offline-v3','13-qualified-continuity-method',
       '13-live-adversarial-codex','13-live-adversarial-deepseek',
       '13-live-switch-codeX','13-live-switch-codeX-v2','13-live-switch-codex-v3','13-live-switch-codex-v4',
       '13-live-switch-deepseek-v2','13-live-switch-deepseek-v3','13-live-switch-deepseek-v4',
       '13-live-timeout-codex','13-live-timeout-deepseek','13-live-timeout-deepseek-v2']
secrets=[]
for line in Path('D:/dsh-proj/Roll/.env').read_text(encoding='utf-8-sig').splitlines():
    line=line.strip().removeprefix('export ').lstrip()
    name,sep,value=line.partition('=')
    if not sep or not re.search('KEY|TOKEN|SECRET|PASSWORD',name,re.I):continue
    value=value.strip()
    value=value[1:value.find(value[0],1)] if value.startswith(('"',"'")) else re.split(r'\s+#',value,maxsplit=1)[0].rstrip()
    if value:secrets.append(value.encode())
assert len(secrets)>=2

def safe(path):
    assert path.name.lower() not in {'.env','auth.json','credentials.json'}
    assert not path.is_symlink() and not path.is_junction()
    content=path.read_bytes()
    assert not any(s in content for s in secrets),'CREDENTIAL_MATCH'
    return content

rows=[];runs=[]
for name in NAMES:
    directory=(DATA/name).resolve()
    assert directory.is_relative_to(DATA.resolve()) and directory.is_dir()
    database=directory/'roll.sqlite3'
    if database.exists():
        with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as db:
            for row in db.execute('SELECT value FROM retrieval_runs'):
                run=json.loads(row[0])
                if run.get('backend') not in {'CODEX','DEEPSEEK'}:continue
                assert run['status']!='RUNNING','LIVE_RUNTIME_NOT_STOPPED'
                process=run.get('process',{})
                assert process.get('remaining_pids',[])==[]
                assert not process.get('task_root') or not Path(process['task_root']).exists(),'TASK_ROOT_NOT_REMOVED'
                runs.append({'directory':name,'run_id':run['run_id'],'backend':run['backend'],'status':run['status'],
                             'remaining_pids':process.get('remaining_pids',[]),'task_root_exists':False})
    for p in sorted(directory.rglob('*')):
        assert not p.is_symlink() and not p.is_junction()
        if p.is_file():
            content=safe(p)
            rows.append({'relative':p.relative_to(DATA).as_posix(),'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
git_paths=set(subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r','33280f4'],cwd=ROOT,text=True).splitlines())
git_paths.update(subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines())
git_paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'.scratch/roll-p0/evidence/13').rglob('*') if p.is_file())
for name in git_paths:
    p=ROOT/name
    if p.is_file():safe(p)
report={'source_directory':str(DATA),'directories':NAMES,'file_count':len(rows),'bytes':sum(r['bytes'] for r in rows),
        'credential_matches':0,'credential_files':0,'git_working_files_scanned':len(git_paths),
        'all_runtime_stopped':True,'runs':runs,'files':rows}
output=ROOT/'.scratch/roll-p0/evidence/13/runtime-inventory.json'
output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in {'files','runs'}}))
