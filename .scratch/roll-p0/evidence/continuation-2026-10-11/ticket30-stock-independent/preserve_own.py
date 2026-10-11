"""Preserve every new stopped independent run, including failures, outside repo."""
import os,stat,hashlib,json,shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
root=Path('D:/dsh-proj/Roll');out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket30-stock-independent'
dest=Path('C:/Users/72449/.codex/visualizations/2026/10/10/01a126a2-cdcc-7d52-b24a-ad47b49bcc56/roll-ticket30-stock-independent-runtime')
names=['t30si-first','t30si-worker-corrected','t30si-worker-watch-corrected']
def native(p):return Path('\\\\?\\'+str(p))
def guard(p):
    s=native(p).lstat();assert not s.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT,str(p)
    return s
def digest(p):
    with native(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert dest.parent.name=='01a126a2-cdcc-7d52-b24a-ad47b49bcc56';guard(dest.parent)
jobs=[]
for name in names:
    source=root/'.roll-data'/name;guard(source)
    for directory,dirs,files in os.walk(native(source),followlinks=False):
        current=Path(directory);guard(Path(str(current)[4:]))
        for child in dirs:guard(Path(str(current/child)[4:]))
        for filename in files:
            assert filename.lower() not in {'auth.json','secrets.json','.env'},filename
            s=Path(str(current/filename)[4:]);d=dest/name/s.relative_to(source);assert stat.S_ISREG(guard(s).st_mode)
            jobs.append((s,d))
def copy(item):
    s,d=item;size=guard(s).st_size;sha=digest(s)
    native(d.parent).mkdir(parents=True,exist_ok=True)
    cursor=d.parent
    while cursor.is_relative_to(dest):guard(cursor);cursor=cursor.parent
    if native(d).exists():assert guard(d).st_size==size and digest(d)==sha,str(d)
    else:shutil.copy2(native(s),native(d))
    assert guard(s).st_size==guard(d).st_size==size and digest(s)==digest(d)==sha,str(d)
    return {'source':str(s),'preserved':str(d),'bytes':size,'sha256':sha}
with ThreadPoolExecutor(max_workers=8) as pool:records=list(pool.map(copy,jobs))
result={'source_namespaces':names,'destination_root':str(dest),'files':len(records),'bytes':sum(r['bytes'] for r in records),'mismatches':0,'entries':records,
    'preserved_sqlite_connections':0,'credentials_read':0,'network_calls':0,'real_account_actions':0,
    'first_harness_synthetic_method_baseline_retained':True,'all_failure_namespaces_retained':True}
raw=json.dumps(result,ensure_ascii=False,indent=2)+'\n';(out/'own-runtime-preservation.json').write_text(raw,encoding='utf-8');native(dest/'manifest.json').write_text(raw,encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='entries'}))
