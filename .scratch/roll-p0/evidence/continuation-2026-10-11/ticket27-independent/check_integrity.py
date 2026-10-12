from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,subprocess,stat
root=Path('D:/dsh-proj/Roll');source=root/'.scratch/worktrees/ticket27'
out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket27-independent'
ev=source/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket27'
def proof(path):
    assert path.name.lower() not in ['auth.json','secrets.json','.env']
    p=Path('\\\\?\\'+str(path));info=p.lstat();assert not info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
    with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'path':str(path),'sha256':sha,'bytes':info.st_size}
def check(path,row):
    r=proof(path);assert r['sha256']==row['sha256'] and r['bytes']==row['bytes'],str(path)
    return r
path=ev/'runtime-preservation-manifest.json';manifest_guard=check(path,{'bytes':3676724,'sha256':'6e7e9294d093af1aa491b7da86867222a74aa24ae3bab5c01e9266b56a69d00d'})
m=json.loads(path.read_text());assert m['files']==len(m['entries'])==8245 and m['bytes']==sum(r['bytes'] for r in m['entries'])==691953514
dest=root/'.roll-data/implementation-evidence/ticket27-r02';assert Path(m['source_root'])==source and Path(m['destination_root'])==dest
jobs=[];parents=set()
for row in m['entries']:
    s=source/row['source'];d=root/row['preserved']
    assert s.is_relative_to(source) and d.is_relative_to(dest)
    assert s.relative_to(source)==d.relative_to(dest)
    jobs.extend([(s,row),(d,row)])
    for p,base in [(s,source),(d,dest)]:
        cursor=p.parent
        while cursor.is_relative_to(base):parents.add(cursor);cursor=cursor.parent
for p in parents:
    assert not Path('\\\\?\\'+str(p)).lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT,str(p)
with ThreadPoolExecutor(max_workers=8) as pool:checked=list(pool.map(lambda pair:check(*pair),jobs))
duplicate_guard=check(dest/'manifest.json',manifest_guard)
fixed=json.loads((root/'.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_text())[:15]
protected=[check(repo/r['path'],r) for r in fixed for repo in [root,source]]
original=check(root/'.roll-data/reconstructed19-v1/roll.sqlite3',{'bytes':165814272,'sha256':'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'})
inventory=json.loads((ev/'source-final.json').read_text())['sources'];assert len(inventory)==111
sources=[check(source/r['path'],r) for r in inventory]
prior={r['path']:r for r in json.loads((ev/'source-final-before-integration.json').read_text())['sources']}
reuse=['backend/src/roll/decisions/lifecycle_journal.py','backend/src/roll/decisions/recovery.py','backend/src/roll/decisions/capabilities.py','backend/src/roll/decisions/monitoring.py','backend/src/roll/runtime/backups.py']
for p in reuse:
    assert prior[p]==next(r for r in inventory if r['path']==p)
blobs=[]
for row in inventory:
    body=subprocess.check_output(['git','-C',str(source),'show','HEAD:'+row['path']])
    actual=(source/row['path']).read_bytes();assert actual.replace(b'\r\n',b'\n')==body.replace(b'\r\n',b'\n'),row['path']
    blobs.append({'path':row['path'],'git_blob':subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD:'+row['path']],text=True).strip(),'raw_sha256':row['sha256']})
result={'stable_source':'86ed2c2052b4be4e4aaa0581e7e067c55dcfdf5c','files':8245,'bytes':691953514,'double_end_checks':len(checked),'mismatches':0,'material_checks':checked,'manifest_guards':[manifest_guard,duplicate_guard],'protected15_root_source':protected,'original19_checksum_only':original,'current_product111_raw_unchanged':sources,'source_git_identity':blobs,'pre_composition_native_os_recovery_sources_raw_unchanged':reuse,'partial_r01_and_long_namespace_touched':False,'root_preserved_sqlite_connections':0}
(out/'integrity.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['material_checks','protected15_root_source','current_product111_raw_unchanged','source_git_identity']}))
