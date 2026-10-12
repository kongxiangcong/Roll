"""Append preservation of this independent acceptance's newly owned runtimes only."""
from pathlib import Path
import hashlib,json,os,shutil
ROOT=Path('D:/dsh-proj/Roll');OUT=ROOT/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket29-independent'
SAVE=ROOT/'.roll-data/implementation-evidence/ticket29-independent-r01'
NAMES=['.scratch/t29-independent-api','.scratch/t29i-short','.scratch/t29i-run02','.scratch/t29i-root']
def native(p):return chr(92)*2+'?'+chr(92)+str(p.resolve())
def proof(p):
    with open(native(p),'rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'bytes':Path(native(p)).stat().st_size,'sha256':sha}
assert not SAVE.exists()
rows=[];excluded=[]
for name in NAMES:
    source=ROOT/name;assert source.exists()
    for directory,_,files in os.walk(native(source)):
        for filename in files:
            ext=Path(directory)/filename;relative=ext.relative_to(Path(native(source)))
            original=source/relative
            if 'notification-private' in relative.parts:
                excluded.append({'source':str(original),'bytes':ext.stat().st_size,'disposition':'PRIVATE_CHANNEL_METADATA_ONLY_NO_CONTENT_READ_OR_COPY'});continue
            saved=SAVE/name/relative
            Path(native(saved.parent)).mkdir(parents=True,exist_ok=True)
            prior=proof(original);shutil.copyfile(native(original),native(saved))
            assert proof(saved)==prior and proof(original)==prior
            rows.append({'source':str(original),'preserved':str(saved),**prior})
manifest={'source_namespaces':NAMES,'destination':str(SAVE),'entries':rows,'files':len(rows),'bytes':sum(r['bytes'] for r in rows),'mismatches':0,'private_exclusions_metadata':excluded,'original_or_saved_sqlite_connections':0,'dependencies_copied':False,'old_owner_preservation_modified':False}
body=(json.dumps(manifest,indent=2)+'\n').encode()
Path(native(SAVE/'manifest.json')).write_bytes(body);(OUT/'runtime-preservation.json').write_bytes(body)
assert proof(SAVE/'manifest.json')==proof(OUT/'runtime-preservation.json')
print(json.dumps({k:manifest[k] for k in ['files','bytes','mismatches','source_namespaces','private_exclusions_metadata']}))
