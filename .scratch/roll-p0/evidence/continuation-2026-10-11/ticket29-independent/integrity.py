"""Independent byte-only acceptance; never connect to donor or saved databases."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json
ROOT=Path('D:/dsh-proj/Roll');TREE=ROOT/'.scratch/worktrees/ticket29'
OWNER=TREE/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket29'
OUT=ROOT/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket29-independent'
def native(p):return chr(92)*2+'?'+chr(92)+str(p.resolve())
def proof(p):
    with open(native(p),'rb') as f: sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'bytes':Path(native(p)).stat().st_size,'sha256':sha}
manifest_path=OWNER/'runtime-preservation.json'
manifest=json.loads(manifest_path.read_bytes())
assert proof(manifest_path)=={'bytes':7804746,'sha256':'be1cf70aa87e6855f2bbe67f59ede3814b70110d9e0f0acb57127cc476450ad6'}
assert proof(ROOT/'.roll-data/implementation-evidence/ticket29-r01/manifest.json')==proof(manifest_path)
entries=manifest['entries']
assert len(entries)==13043 and sum(r['bytes'] for r in entries)==732166275
def check(r):
    source=Path(r['source']);saved=Path(r['preserved'])
    assert source.is_relative_to(TREE) and saved.is_relative_to(ROOT/'.roll-data/implementation-evidence/ticket29-r01')
    assert 'notification-private' not in source.parts
    expected={k:r[k] for k in ['bytes','sha256']}
    assert proof(source)==expected and proof(saved)==expected, str(source)
with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(check,entries))
inventory=json.loads((OWNER/'handoff-inventory.json').read_bytes())
for r in inventory['entries']:assert proof(TREE/r['path'])=={k:r[k] for k in ['bytes','sha256']}
protected=json.loads((ROOT/'.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_bytes())[:15]
guards=[{'path':r['path'],'root':proof(ROOT/r['path']),'tree':proof(TREE/r['path'])} for r in protected]
assert len(guards)==15 and all(r['root']==r['tree'] for r in guards)
original=proof(ROOT/'.roll-data/reconstructed19-v1/roll.sqlite3')
assert original=={'bytes':165814272,'sha256':'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'}
ninth={
 'backend/src/roll/market/sse_company_actions.py':'63505424914969f9e1bd65237df93c886e163d01d0facb8cd2ca6754ce2eeb20',
 'backend/src/roll/market/sse_action_assessments.py':'c8ea677062d1f4ba711151015fa4162ca21df0b9b1c3c19751ba64020a34d13f'}
source_final=json.loads((ROOT/'.scratch/roll-p0/evidence/30-sse-company-actions/source-final-after.json').read_bytes())
for path,sha in ninth.items():
    body=(ROOT/path).read_bytes().replace(b'\r\n',b'\n')
    expected=source_final['own_inventory'][path]
    assert len(body)==expected['bytes_lf'] and hashlib.sha256(body).hexdigest()==expected['sha256_lf']
collector=hashlib.sha256(b'SSE_ACTION_RAW_FIRST_V1\n'+(ROOT/'backend/src/roll/market/sse_company_actions.py').read_bytes().replace(b'\r\n',b'\n')+b'424fe512ec29f76c415beba626c176fed8261d8ebdb22da25d9fac5d922f29cd'+b'72bdf9f924465e3c848577fa4ec5285c163474a79be9bee4a0500a2ecb53f55b'+b'478fb2a72fc5a3725088adb208756e88171f79628956a9f5ca67c900d37def2f').hexdigest()
assert collector==ninth['backend/src/roll/market/sse_company_actions.py']
assessment=hashlib.sha256(b'SSE_ACTION_ASSESSMENT_V1\n'+(ROOT/'backend/src/roll/market/sse_action_assessments.py').read_bytes().replace(b'\r\n',b'\n')+b'86fba6946b48e649a89d3cbae25661126b991f216029dec30ffc365916a8e489'+collector.encode()).hexdigest()
assert assessment==ninth['backend/src/roll/market/sse_action_assessments.py']
result={'owner_manifest':proof(manifest_path),'owner_files':len(entries),'owner_bytes':sum(r['bytes'] for r in entries),'dual_endpoint_mismatches':0,'inventory_paths':len(inventory['entries']),'protected':guards,'original19_checksum_only':original,'ninth_source_fingerprints':ninth,'sqlite_opened':False,'private_exclusions_metadata':manifest['exact_private_metadata_exclusions']}
(OUT/'byte-integrity.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print('13043 dual endpoints + owner inventory + 15 protected + original19 + ninth: PASS')
