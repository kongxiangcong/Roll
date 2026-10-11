"""Bounded byte-only protection; never connect an original database."""
from pathlib import Path
import hashlib,json,subprocess,sys
TREE=Path(__file__).resolve().parents[5]
ROOT=Path('D:/dsh-proj/Roll')
OUT=TREE/'.scratch/roll-p0/evidence/31-final'
def proof(path):
    with path.open('rb') as stream: value=hashlib.file_digest(stream,'sha256').hexdigest()
    return {'bytes':path.stat().st_size,'sha256':value}
paths=[r['path'] for r in json.loads((ROOT/'.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_bytes())[:15]]
protected=[{'path':p,'root':proof(ROOT/p),'own':proof(TREE/p)} for p in paths]
assert len(protected)==15 and all(r['root']==r['own'] for r in protected)
reference=json.loads((ROOT/'.scratch/roll-p0/evidence/continuation-2026-10-11/frontier24-29/benchmark-artifact-reference.json').read_bytes())
artifacts=[]
for row in reference['artifacts']:
    value=proof(Path(row['path']))
    assert value=={'bytes':row['bytes'],'sha256':row['sha256']}
    artifacts.append({'path':row['path'],**value})
assert len(artifacts)==3
original=proof(ROOT/'.roll-data/reconstructed19-v1/roll.sqlite3')
assert original=={'bytes':165814272,'sha256':'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'}
files=subprocess.check_output(['git','ls-files','backend/src','frontend/src'],cwd=TREE,text=True).splitlines()
sources=[{'path':p,'sha256_lf':hashlib.sha256((TREE/p).read_bytes().replace(b'\r\n',b'\n')).hexdigest()} for p in files if (TREE/p).is_file()]
result={'accepted_root':'076e67d53e4e550d4027b4f76909fb693c952957','protected15':protected,'allowed3':artifacts,'original19_checksum_only':original,'sources':sources,'original_sqlite_connections':0}
before=OUT/'guard-before.json'
if before.exists():assert json.loads(before.read_bytes())==result
destination=OUT/sys.argv[1]
assert not destination.exists()
destination.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print('protected15 + allowed3 + original19 byte-only + current application sources PASS')
