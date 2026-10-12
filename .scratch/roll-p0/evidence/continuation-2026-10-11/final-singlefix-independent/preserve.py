"""Append only new independent METHOD runtime; no saved databases connected."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,os,shutil
ROOT=Path('D:/dsh-proj/Roll');OUT=ROOT/'.scratch/roll-p0/evidence/continuation-2026-10-11/final-singlefix-independent'
SOURCE=ROOT/'.scratch/sfi01';SAVE=ROOT/'.roll-data/implementation-evidence/final-singlefix-independent-r01'
def native(p):return chr(92)*2+'?'+chr(92)+str(p.resolve())
def proof(p):
    with open(native(p),'rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'bytes':Path(native(p)).stat().st_size,'sha256':sha}
assert SOURCE.exists() and not SAVE.exists()
rows=[];excluded=[]
for directory,_,files in os.walk(native(SOURCE)):
    for name in files:
        ext=Path(directory)/name;relative=ext.relative_to(Path(native(SOURCE)));source=SOURCE/relative
        if 'notification-private' in relative.parts or name.lower() in {'auth.json','credentials.json','secrets.json','.env'}:
            excluded.append({'source':str(source),'bytes_metadata_only':ext.stat().st_size,'opened_hashed_copied':False});continue
        saved=SAVE/relative;Path(native(saved.parent)).mkdir(parents=True,exist_ok=True)
        prior=proof(source);shutil.copyfile(native(source),native(saved));assert proof(saved)==proof(source)==prior
        rows.append({'source':str(source),'preserved':str(saved),**prior})
def verify(row):
    expected={k:row[k] for k in ['bytes','sha256']}
    assert proof(Path(row['source']))==proof(Path(row['preserved']))==expected
with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(verify,rows))
manifest={'product_oid':'4a975c629379cba4cbee34178bf5d2ac4452d87c','source_namespace':str(SOURCE),'destination':str(SAVE),'files':len(rows),'bytes':sum(r['bytes'] for r in rows),'entries':rows,'dual_endpoint_mismatches':0,'exact_private_metadata_exclusions':excluded,'original_saved_sqlite_connections':0,'old_namespaces_modified':False,'dependency_caches_read_or_copied':False}
body=(json.dumps(manifest,indent=2)+'\n').encode();(SAVE/'manifest.json').write_bytes(body);(OUT/'runtime-preservation.json').write_bytes(body)
assert proof(SAVE/'manifest.json')==proof(OUT/'runtime-preservation.json')
result={k:manifest[k] for k in ['product_oid','source_namespace','destination','files','bytes','dual_endpoint_mismatches','exact_private_metadata_exclusions']};result['manifest']=proof(OUT/'runtime-preservation.json')
(OUT/'preservation-summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(result))
