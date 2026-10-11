"""Fixed owner union and source check; private exclusion contents never accessed."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,subprocess,sys
ROOT=Path('D:/dsh-proj/Roll');TREE=ROOT/'.scratch/worktrees/final-review-fix'
OWNER=TREE/'.scratch/roll-p0/evidence/final-review-fix'
OUT=ROOT/'.scratch/roll-p0/evidence/continuation-2026-10-11/final-singlefix-independent'
HANDOFF='94d871111693958ee11e1d75c142f19a0f1bebe0';PRODUCT='4a975c629379cba4cbee34178bf5d2ac4452d87c'
def native(p):return Path(chr(92)*2+'?'+chr(92)+str(p.resolve()))
def proof(p):
    p=native(p)
    with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'bytes':p.stat().st_size,'sha256':sha}
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=TREE).decode().strip()==HANDOFF
assert not subprocess.check_output(['git','diff',PRODUCT,HANDOFF,'--','backend/src','backend/tests','frontend/src','frontend/tests'],cwd=TREE)
manifest_path=OWNER/'runtime-preservation-manifest-v2.json'
assert proof(manifest_path)=={'bytes':3651911,'sha256':'042deedef5f872cb935cb6929eb913f4104955e026d523545a6f612e831684ee'}
manifest=json.loads(manifest_path.read_bytes());entries=manifest['entries'];private=manifest['exact_private_exclusions']
assert manifest['source_product_oid']==PRODUCT and len(entries)==4872 and sum(r['bytes'] for r in entries)==299928587
assert len(private)==5 and all(r['content_read']==r['hashed']==r['copied']==False for r in private)
excluded={r['path'] for r in private}
assert not any(r['path'] in excluded or 'notification-private' in Path(r['source']).parts or Path(r['source']).name.lower()=='auth.json' for r in entries)
saved_root=ROOT/'.roll-data/implementation-evidence/final-review-fix/runtime-v2'
def verify(r):
    source=Path(r['source']);target=Path(r['target'])
    assert source.is_relative_to(TREE) and target.is_relative_to(saved_root)
    expected={k:r[k] for k in ['bytes','sha256']}
    assert proof(source)==proof(target)==expected,str(source)
with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(verify,entries))
guard=json.loads((OWNER/'source-guard-preserved-final.json').read_bytes())
assert len(guard['protected_15_root_own'])==30 and len(guard['separate_allowed_3_checksum_only'])==3
for r in guard['protected_15_root_own']+guard['separate_allowed_3_checksum_only']:
    assert proof(Path(r['path']))=={k:r[k] for k in ['bytes','sha256']}
original=guard['original19_checksum_only_no_SQLite_connection']
assert proof(Path(original['path']))=={k:original[k] for k in ['bytes','sha256']}
owner_inventory={str(p.relative_to(TREE/'backend/src/roll')).replace(chr(92),'/'):hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in sorted((TREE/'backend/src/roll').rglob('*.py'))}
assert owner_inventory==guard['application_sources'] and len(owner_inventory)==75
if sys.argv[1]=='postmerge':
    root_inventory={str(p.relative_to(ROOT/'backend/src/roll')).replace(chr(92),'/'):hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in sorted((ROOT/'backend/src/roll').rglob('*.py'))}
    assert root_inventory==owner_inventory
    changed=subprocess.check_output(['git','diff','--name-only','fbc8bd5',PRODUCT,'--','backend/src','frontend/src'],cwd=TREE).decode().splitlines()
    for path in changed:assert (ROOT/path).read_bytes().replace(b'\r\n',b'\n')==(TREE/path).read_bytes().replace(b'\r\n',b'\n')
result={'stage':sys.argv[1],'handoff_oid':HANDOFF,'product_oid':PRODUCT,'owner_manifest':proof(manifest_path),'files':len(entries),'bytes':sum(r['bytes'] for r in entries),'dual_endpoint_checks':len(entries)*2,'mismatches':0,'private_exclusions_metadata':private,'protected_15_root_owner_checks':30,'separate_allowed_3_checksum_only':guard['separate_allowed_3_checksum_only'],'application_source_count':75,'original19_checksum_only':original,'original_or_saved_sqlite_connections':0}
(OUT/('handoff-'+sys.argv[1]+'.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:result[k] for k in ['stage','files','bytes','dual_endpoint_checks','mismatches','protected_15_root_owner_checks','application_source_count']}))
