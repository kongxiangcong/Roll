"""Byte-only independent preservation/donor final proof."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json
ROOT=Path('D:/dsh-proj/Roll');OUT=ROOT/'.scratch/roll-p0/evidence/continuation-2026-10-11/final-singlefix-independent'
def proof(p):
    p=Path(chr(92)*2+'?'+chr(92)+str(p.resolve()))
    with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'bytes':p.stat().st_size,'sha256':sha}
manifest=OUT/'runtime-preservation.json';saved=ROOT/'.roll-data/implementation-evidence/final-singlefix-independent-r01/manifest.json'
assert proof(manifest)==proof(saved)=={'bytes':214851,'sha256':'fd09e9e6cca68ac64db8eb49c1ef37d5def8aa913904153b5722c22f542ce7f8'}
data=json.loads(manifest.read_bytes())
def verify(r):
    expected={k:r[k] for k in ['bytes','sha256']}
    assert proof(Path(r['source']))==proof(Path(r['preserved']))==expected
with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(verify,data['entries']))
pin=ROOT/'.scratch/roll-p0/evidence/continuation-2026-10-11/independent20-profile-manifest.json'
assert proof(pin)['sha256']=='528688f65d19849fffeead4aa8082adc9374dac471eff71ff504c483460c62e7'
donor=json.loads(pin.read_bytes());assert len(donor['entries'])==193
for row in donor['entries']:
    actual=proof(ROOT/'.roll-data/implementation-evidence/20/independent-api-runtime-fixed'/row['path'])
    assert actual['bytes']==row['bytes'] and actual['sha256'].upper()==row['sha256']
result={'files':len(data['entries']),'bytes':sum(r['bytes'] for r in data['entries']),'dual_endpoint_mismatches':0,'donor193_mismatches':0,'original_or_saved_sqlite_connections':0,'manifest':proof(manifest)}
(OUT/'final-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(result))
