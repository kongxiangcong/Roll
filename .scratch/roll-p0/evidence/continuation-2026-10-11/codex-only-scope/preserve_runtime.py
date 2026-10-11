"""Retain owned METHOD profiles before the merger removes this checkout."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[5]
destination=Path('D:/dsh-proj/Roll/.roll-data/implementation-evidence/codex-only-scope')
assert root==Path('D:/dsh-proj/Roll/.scratch/worktrees/codex-scope')
names=['csr','csr2','csr3','csg','csg2','csg3','csf','csbrowser','csbrowser2']
rows=[]
for name in names:
    source=Path('\\\\?\\'+str(root/'.scratch'/name))
    assert source.is_dir() and not source.is_symlink()
    for path in sorted(source.rglob('*')):
        if not path.is_file():continue
        relative=path.relative_to(source)
        target=Path('\\\\?\\'+str(destination/name/relative))
        original=path.read_bytes()
        if target.exists():assert target.read_bytes()==original
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(original)
        copied=target.read_bytes()
        assert original==copied
        rows.append({'path':name+'/'+relative.as_posix(),'bytes':len(original),'sha256':hashlib.sha256(original).hexdigest()})
receipt={'kind':'METHOD_CASE_ONLY','destination':str(destination),'files':len(rows),
         'bytes':sum(row['bytes'] for row in rows),'mismatches':0,'inventory':rows}
Path(__file__).with_name('runtime-preservation.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps({key:value for key,value in receipt.items() if key!='inventory'}))
