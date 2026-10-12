"""Independent three exact Ticket28 preservation targets, metadata-only private exclusions."""
import os,json,hashlib,stat,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
root=Path('D:/dsh-proj/Roll');source=root/'.scratch/worktrees/ticket28';ev=source/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket28'
out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket28-independent'
def native(p):return Path('\\\\?\\'+str(p))
def meta(p):
    p=Path(p);s=native(p).lstat();assert not s.st_file_attributes & 0x400,str(p);return s
def proof(p):
    p=Path(p);s=meta(p);assert stat.S_ISREG(s.st_mode) and p.parent.name!='notification-private',str(p)
    assert p.name.lower() not in {'auth.json','.env','secrets.json'},str(p)
    with native(p).open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'path':str(p),'bytes':s.st_size,'sha256':sha}
def check(p,row):
    r=proof(p);assert (r['bytes'],r['sha256'])==(row['bytes'],row['sha256']),str(p);return r
def git(repo,*a):return subprocess.check_output(['git','-C',str(repo),*a])
assert git(source,'rev-parse','HEAD').decode().strip()=='83c9289db44a1d6d6d91542b638e22eb45f5a72f'
assert not git(source,'diff','--name-only') and not git(source,'diff','--cached','--name-only')
jobs=[];parents=set();sets=[];excluded=[]
for prefix,suffix,count,size,nprivate in [('runtime','final-internal-v2',1218,100247004,35),('length-runtime','length-correction',198,15686482,10),('current-runtime','current-composition',72,5682523,2)]:
    manifest=ev/(prefix+'-preservation-manifest.json');rows=json.loads(manifest.read_bytes());receipt=json.loads((ev/(prefix+'-preservation-receipt.json')).read_bytes())
    exceptions=json.loads((ev/(prefix+'-private-exclusions.json')).read_bytes());dest=root/'.roll-data/implementation-evidence/ticket28'/suffix
    assert len(rows)==receipt['copied_files']==count and sum(r['bytes'] for r in rows)==receipt['copied_bytes']==size
    assert len(exceptions)==receipt['excluded_private_configuration_files']==nprivate
    assert proof(manifest)['sha256']==receipt['manifest_sha256']
    seens=set();seend=set();profile_roots=set()
    for r in rows:
        s=root/r['source'];d=root/r['destination'];rel=s.relative_to(source/'backend')
        assert d.relative_to(dest)==rel and s not in seens and d not in seend
        seens.add(s);seend.add(d);profile_roots.add(source/'backend'/rel.parts[0])
        jobs.extend([(s,r),(d,r)])
        for p,b in [(s,source),(d,dest)]:
            cur=p.parent
            while cur.is_relative_to(b):parents.add(cur);cur=cur.parent
    privates=set()
    for r in exceptions:
        p=root/r['source'];assert p.parent.name=='notification-private' and p.name in {'channel.json','channel.lock'}
        assert any(p.is_relative_to(b) for b in profile_roots) and p not in seens and p not in privates
        privates.add(p);s=meta(p);assert stat.S_ISREG(s.st_mode)
        excluded.append({'path':str(p),'bytes_metadata_only':s.st_size,'content_read_hashed_copied':False,'owner_fixture':r['owner_fixture']})
    # Metadata coverage only: all public source files and exact excluded paths accounted.
    actual=set()
    for b in profile_roots:
        for directory,dirs,files in os.walk(native(b),followlinks=False):
            cur=Path(str(directory)[4:]);meta(cur)
            for name in dirs:meta(cur/name)
            for name in files:meta(cur/name);actual.add(cur/name)
    assert actual==seens|privates,(actual-(seens|privates),(seens|privates)-actual)
    actual_dest=set()
    for directory,dirs,files in os.walk(native(dest),followlinks=False):
        cur=Path(str(directory)[4:]);meta(cur)
        for name in dirs:meta(cur/name)
        for name in files:meta(cur/name);actual_dest.add(cur/name)
    assert actual_dest==seend
    sets.append({'target':str(dest),'files':count,'bytes':size,'private_exclusions':nprivate,'manifest':proof(manifest)})
for p in parents:meta(p)
with ThreadPoolExecutor(max_workers=8) as pool:checks=list(pool.map(lambda pair:check(*pair),jobs))
fixed=json.loads((root/'.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_bytes())[:15]
protected=[check(repo/r['path'],r) for r in fixed for repo in [root,source]]
original=check(root/'.roll-data/reconstructed19-v1/roll.sqlite3',{'bytes':165814272,'sha256':'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'})
inventory=json.loads((ev/'source-after-current-composition.json').read_bytes());assert len(inventory)==109
owned=[]
for r in inventory:
    found=check(source/r['path'],r);blob=git(source,'show','HEAD:'+r['path'])
    assert (source/r['path']).read_bytes().replace(b'\r\n',b'\n')==blob.replace(b'\r\n',b'\n'),r['path']
    owned.append({**found,'git_blob':git(source,'rev-parse','HEAD:'+r['path']).decode().strip()})
r={'source_head':'83c9289db44a1d6d6d91542b638e22eb45f5a72f','namespaces':sets,'files':1488,'bytes':121616009,'double_end_checks':len(checks),'mismatches':0,'materials':checks,'private_metadata_exclusions':excluded,'private_excluded_count':47,'protected15_root_source':protected,'original19_checksum_only':original,'source109_raw_git_identity':owned,'saved_sqlite_connections':0,'private_contents_read_hashed_copied':0,'actual_ntfy_provider_calls':0,'source_tracked_index_clean':True}
assert sum(s['files'] for s in sets)==r['files'] and sum(s['bytes'] for s in sets)==r['bytes'] and len(excluded)==47
(out/'integrity.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in r.items() if k not in ['materials','private_metadata_exclusions','protected15_root_source','source109_raw_git_identity']}))
