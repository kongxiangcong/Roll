import json, hashlib, subprocess
from pathlib import Path
v=Path(__file__).parent
root=Path('D:/dsh-proj/Roll')
git='C:/Program Files/Git/cmd/git.exe'
def g(*args): return subprocess.check_output([git,'--no-optional-locks','-c','core.longpaths=true','-C',str(root),*args])
prefix='.scratch/roll-p0/evidence/continuation-2026-10-11/final-cleanup/'
docs={'.scratch/roll-p0/execution-status.md','.scratch/roll-p0/issues/31-engineering-delivery.md'}
names=g('diff','--cached','--name-only').decode('utf-8').splitlines()
assert names and all(n.startswith(prefix) or n in docs for n in names)
assert docs.issubset(names)
g('diff','--cached','--check')
rows=[]
for n in names:
    content=(root/n).read_bytes()
    blob=g('show',':'+n)
    assert content==blob, n
    rows.append(dict(path=n,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),index_worktree_byte_identical=True))
old=json.loads((v/'roll-root-untracked-before-final-docs.json').read_text(encoding='utf-8-sig'))['untracked_entries']
current=g('status','--porcelain=v1','--untracked-files=normal').decode('utf-8').splitlines()
untracked=[n for n in current if n.startswith('?? ')]
assert sorted(untracked)==sorted(old)
proof=dict(status='PASS',scoped_files=len(rows),staged_byte_proofs=rows,foreign_untracked_entries=len(old),foreign_untracked_unchanged=True,private_endpoint_reads=0,sqlite_connections=0,push=False)
(v/'roll-cleanup-staged-byte-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(status='PASS',scoped_files=len(rows),foreign_untracked_entries=len(old))))
