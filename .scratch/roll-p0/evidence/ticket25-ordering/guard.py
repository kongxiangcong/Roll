"""Own repair checksum guard; no SQLite connection, Roll import or secret access."""
from pathlib import Path
import hashlib, json, sys

own=Path(__file__).resolve().parents[4]
root=Path('D:/dsh-proj/Roll')
out=Path(__file__).parent
def digest(path):
    with path.open('rb') as stream: sha=hashlib.file_digest(stream,'sha256').hexdigest()
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':sha}
reference=json.loads((own/'.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text(encoding='utf-8'))[:15]
checks=[]
for r in reference:
    for repo in [own,root]:
        got=digest(repo/r['path'])
        assert got['sha256']==r['sha256'] and got['bytes']==r['bytes'], got['path']
        checks.append(got)
old=json.loads((own/'.scratch/roll-p0/evidence/ticket26/protected-source-final.json').read_text(encoding='utf-8'))['actual19_database']
db=digest(Path(old['path']))
assert (db['bytes'],db['sha256'])==(old['bytes'],old['sha256'])
inventory={str(p.relative_to(own/'backend/src/roll')).replace('\\','/'):hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in sorted((own/'backend/src/roll').rglob('*.py'))}
result={'stage':sys.argv[1], 'protected_15_root_own':checks,'original19_checksum_only_no_SQLite_connection':db,'application_sources':inventory,'mismatches':0}
path=out/('source-guard-'+sys.argv[1]+'.json')
if path.exists():raise ValueError('NEW_STAGE_REQUIRED_DO_NOT_OVERWRITE')
path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'stage':sys.argv[1],'protected_checks':len(checks),'original19_bytes':db['bytes'],'original19_sha256':db['sha256'],'source_count':len(inventory),'mismatches':0}))
