"""Byte-only frozen product, protected sources and original19 check."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path('D:/dsh-proj/Roll');TREE=ROOT/'.scratch/worktrees/final-review-fix'
OUT=ROOT/'.scratch/roll-p0/evidence/continuation-2026-10-11/final-singlefix-independent'
OID='4a975c629379cba4cbee34178bf5d2ac4452d87c'
def proof(path):
    with path.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'bytes':path.stat().st_size,'sha256':sha}
paths=[r['path'] for r in json.loads((ROOT/'.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_bytes())[:15]]
protected=[{'path':p,'root':proof(ROOT/p),'owner':proof(TREE/p)} for p in paths]
assert len(protected)==15 and all(r['root']==r['owner'] for r in protected)
changed=subprocess.check_output(['git','diff','--name-only','fbc8bd5',OID,'--','backend/src','backend/tests','frontend/src','frontend/tests'],cwd=TREE).decode().splitlines()
sources=[]
for path in changed:
    if not (TREE/path).is_file():continue
    expected=subprocess.check_output(['git','show',OID+':'+path],cwd=TREE).replace(b'\r\n',b'\n')
    actual=(TREE/path).read_bytes().replace(b'\r\n',b'\n')
    assert expected==actual,path
    sources.append({'path':path,'sha256_lf':hashlib.sha256(actual).hexdigest(),'bytes_lf':len(actual)})
original=proof(ROOT/'.roll-data/reconstructed19-v1/roll.sqlite3')
assert original=={'bytes':165814272,'sha256':'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'}
from roll.market.sse_company_actions import fingerprint
assert fingerprint()=='63505424914969f9e1bd65237df93c886e163d01d0facb8cd2ca6754ce2eeb20'
result={'product_oid':OID,'changed_sources':sources,'protected15':protected,'allowed3_status':'Already accepted shadow/statistics/validation bytes retained within protected15','original19_checksum_only':original,'sse_collector_fingerprint':fingerprint(),'original_sqlite_connections':0}
before=OUT/'guards-before.json'
if before.exists():assert json.loads(before.read_bytes())==result
(OUT/sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print('fixed product + protected15/current3 + original19 + SSE fingerprint PASS')
