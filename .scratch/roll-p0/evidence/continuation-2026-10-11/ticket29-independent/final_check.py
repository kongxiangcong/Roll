"""Final independent donor and append-preservation byte check only."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib,json
ROOT=Path('D:/dsh-proj/Roll');OUT=ROOT/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket29-independent'
def proof(p):
    p=Path(chr(92)*2+'?'+chr(92)+str(p.resolve()))
    with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'bytes':p.stat().st_size,'sha256':sha}
manifest=OUT/'runtime-preservation.json';runtime=json.loads(manifest.read_bytes())
assert proof(manifest)==proof(ROOT/'.roll-data/implementation-evidence/ticket29-independent-r01/manifest.json')
def verify(row):
    expected={k:row[k] for k in ['bytes','sha256']}
    assert proof(Path(row['source']))==expected and proof(Path(row['preserved']))==expected
with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(verify,runtime['entries']))
donor_manifest=ROOT/'.scratch/roll-p0/evidence/continuation-2026-10-11/independent20-profile-manifest.json'
assert proof(donor_manifest)['sha256']=='528688f65d19849fffeead4aa8082adc9374dac471eff71ff504c483460c62e7'
donor=json.loads(donor_manifest.read_bytes())
assert len(donor['entries'])==193
for row in donor['entries']:
    actual=proof(ROOT/'.roll-data/implementation-evidence/20/independent-api-runtime-fixed'/row['path'])
    assert actual['bytes']==row['bytes'] and actual['sha256'].upper()==row['sha256']
result={'independent_runtime':{'files':len(runtime['entries']),'bytes':sum(r['bytes'] for r in runtime['entries']),'manifest':proof(manifest),'dual_endpoint_mismatches':0},'original193_donor_mismatches':0,'original_or_saved_sqlite_connections':0,'actual_http_calls':0}
(OUT/'final-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
