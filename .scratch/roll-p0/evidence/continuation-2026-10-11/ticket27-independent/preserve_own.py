"""Byte-only preservation of stopped independent METHOD profiles outside repo."""
import os,stat,hashlib,json,shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
root=Path('D:/dsh-proj/Roll')
source=root/'.roll-data/r27i-first'
destination=Path('C:/Users/72449/.codex/visualizations/2026/10/10/01a126a2-cdcc-7d52-b24a-ad47b49bcc56/roll-ticket27-independent-runtime')
out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket27-independent'
def native(p):return Path('\\\\?\\'+str(p))
def guard(p):
    s=native(p).lstat();assert not s.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT,str(p)
    return s
assert source.is_relative_to(root/'.roll-data')
assert destination.parent.name=='01a126a2-cdcc-7d52-b24a-ad47b49bcc56'
guard(source);guard(destination.parent)
entries=[]
for directory,dirs,files in os.walk(native(source),followlinks=False):
    current=Path(directory);guard(Path(str(current)[4:]))
    for child in dirs:guard(Path(str(current/child)[4:]))
    for filename in files:
        assert filename.lower() not in {'auth.json','secrets.json','.env'},filename
        physical=current/filename;s=guard(Path(str(physical)[4:]));assert stat.S_ISREG(s.st_mode)
        relative=physical.relative_to(native(source));entries.append((relative,s.st_size))
def digest(path):
    with native(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def copy(item):
    relative,length=item;s=source/relative;d=destination/relative
    native(d.parent).mkdir(parents=True,exist_ok=True)
    for p,base in [(s,source),(d,destination)]:
        cursor=p.parent
        while cursor.is_relative_to(base):guard(cursor);cursor=cursor.parent
    original=digest(s)
    if native(d).exists():assert guard(d).st_size==length and digest(d)==original,str(d)
    else:shutil.copy2(native(s),native(d))
    assert guard(s).st_size==guard(d).st_size==length and digest(s)==digest(d)==original,str(d)
    return {'source':str(s),'preserved':str(d),'relative_path':str(relative),'bytes':length,'sha256':original}
with ThreadPoolExecutor(max_workers=8) as pool:records=list(pool.map(copy,entries))
result={'source_root':str(source),'destination_root':str(destination),'files':len(records),'bytes':sum(r['bytes'] for r in records),'mismatches':0,'entries':records,'sqlite_connections_during_preservation':0,'credentials_read':0,'actual_model_fits':0,'provider_calls':0,'partial_owner_namespaces_touched':False}
raw=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
(out/'own-runtime-preservation.json').write_text(raw,encoding='utf-8')
native(destination/'manifest.json').write_text(raw,encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='entries'}))
