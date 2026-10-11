import hashlib,json,sys,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[5]
folder=Path(__file__).parent
rows=[]
for directory in ['backend/src','frontend/src']:
    for path in sorted((root/directory).rglob('*')):
        if path.is_file() and path.suffix in {'.py','.json','.ts','.tsx','.css'}:
            value=path.read_bytes()
            rows.append({'path':path.relative_to(root).as_posix(),'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()})
protected=json.loads((root/'.scratch/roll-p0/evidence/continuation-2026-10-11/codex-only-scope/source-final.json').read_text(encoding='utf-8'))[:15]
for item in protected:assert item in rows,item['path']
phase=sys.argv[1]
if phase in {'integrated','integrated-final'}:
    before={item['path']:item for item in json.loads((folder/'source-before.json').read_text(encoding='utf-8'))}
    after={item['path']:item for item in rows}
    changed=sorted(path for path in before.keys()|after.keys() if before.get(path)!=after.get(path))
    accepted=subprocess.check_output(['git','diff','--name-only','c3fe7d8d83d05b8579979be3c6b62a5af03103ce',
        '371dd9c7c75d1fb5df9827a81dc580ddd5a62c63','--','backend/src','frontend/src'],cwd=root,text=True).splitlines()
    assert changed==sorted(accepted),(changed,accepted)
    subprocess.run(['git','diff','--exit-code','--','backend/src','frontend/src'],cwd=root,check=True)
    (folder/'accepted-25-source-delta.json').write_text(json.dumps({'integration_tip':'371dd9c7c75d1fb5df9827a81dc580ddd5a62c63',
        'changed_paths':changed,'all_changes_from_accepted_25':True},indent=2),encoding='utf-8',newline='\n')
elif phase!='before':assert rows==json.loads((folder/'source-before.json').read_text(encoding='utf-8'))
(folder/f'source-{phase}.json').write_text(json.dumps(rows,indent=2),encoding='utf-8',newline='\n')
print(f'{phase}: {len(rows)} product source files checked; 15 protected fingerprints match')
