"""Sixth Ticket30 two-target byte-only preservation and source/raw identity audit."""
import json,hashlib,stat,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
root=Path('D:/dsh-proj/Roll');source=root/'.scratch/worktrees/ticket30-producer'
ev=source/'.scratch/roll-p0/evidence/30-sse-stock-suspension'
out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket30-stock-independent'
def git(*args):return subprocess.check_output(['git','-C',str(source),*args])
def native(p):return Path('\\\\?\\'+str(p))
def proof(p):
    info=native(p).lstat();assert not info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT,str(p)
    assert p.name.lower() not in {'auth.json','secrets.json','.env'},str(p)
    with native(p).open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'path':str(p),'sha256':sha,'bytes':info.st_size}
def check(p,row):
    r=proof(p);assert r['sha256']==row['sha256'] and r['bytes']==row['bytes'],str(p)
    return r
assert git('rev-parse','HEAD').decode().strip()=='f44d1685a808fcba976007ea3e0fc14d218f93c6'
assert git('diff','--name-only')==b'' and git('diff','--cached','--name-only')==b''
sets=[];jobs=[];parents=set()
for name,count,size,suffix in [('runtime',2728,375082862,''),('composition27',153,20080223,'-composition27')]:
    manifest=ev/(name+'-preservation-manifest.json');receipt=json.loads((ev/(name+'-preservation-receipt.json')).read_bytes())
    records=json.loads(manifest.read_bytes());dest=root/('.roll-data/implementation-evidence/continuation-ticket30-sse-stock-suspension'+suffix)
    assert len(records)==receipt['files']==count and sum(r['bytes'] for r in records)==receipt['bytes']==size
    assert Path(receipt['target'])==dest
    source_dirs=[Path(p) for p in receipt.get('source_directories',[receipt.get('source_directory')])]
    seen=set()
    for row in records:
        s=Path(row['source']);d=Path(row['destination'])
        assert s not in seen;seen.add(s)
        assert s.is_relative_to(source/'.scratch') and d.is_relative_to(dest)
        assert any(s.is_relative_to(p) for p in source_dirs)
        relative=s.relative_to(source/'.scratch')
        assert d.relative_to(dest)==(relative if not suffix else s.relative_to(source_dirs[0]))
        jobs.extend([(s,row),(d,row)])
        for p,b in [(s,source),(d,dest)]:
            cursor=p.parent
            while cursor.is_relative_to(b):parents.add(cursor);cursor=cursor.parent
    sets.append({'namespace':str(dest),'files':count,'bytes':size,'manifest':proof(manifest),'receipt':proof(ev/(name+'-preservation-receipt.json'))})
for p in parents:assert not native(p).lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT,str(p)
with ThreadPoolExecutor(max_workers=8) as pool:checks=list(pool.map(lambda item:check(*item),jobs))
fixed=json.loads((root/'.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_bytes())[:15]
protected=[check(repo/r['path'],r) for r in fixed for repo in [root,source]]
original=check(root/'.roll-data/reconstructed19-v1/roll.sqlite3',{'bytes':165814272,'sha256':'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'})
inventory=json.loads((ev/'source-composition27-after.json').read_bytes())['own'];owned=[]
for p,row in inventory.items():
    found=check(source/p,row);body=git('show','HEAD:'+p)
    assert (source/p).read_bytes().replace(b'\r\n',b'\n')==body.replace(b'\r\n',b'\n'),p
    owned.append({**found,'git_blob':git('rev-parse','HEAD:'+p).decode().strip()})
raws=[]
for row in json.loads((ev/'git-original-identity.json').read_bytes())['originals']:
    found=check(source/row['path'],row);body=git('show','HEAD:'+row['path'])
    assert hashlib.sha256(body).hexdigest()==row['sha256'] and len(body)==row['bytes']
    raws.append({**found,'git_blob':git('rev-parse','HEAD:'+row['path']).decode().strip()})
reference=source/'backend/src/roll/market/reference/sse-history'
mapping=json.loads((reference/'sources.json').read_bytes())
dependencies=[]
for row in mapping['sources']:
    if row['role'] in {'suspension_query_js','suspension_inconsistent'}:
        p=reference/row['path'];found=check(p,row);rel=p.relative_to(source).as_posix();body=git('show','HEAD:'+rel)
        assert hashlib.sha256(body).hexdigest()==row['sha256'] and len(body)==row['bytes']
        dependencies.append({**found,'git_blob':git('rev-parse','HEAD:'+rel).decode().strip()})
result={'source_head':'f44d1685a808fcba976007ea3e0fc14d218f93c6','source_tracked_index_clean':True,
    'namespaces':sets,'files':2881,'bytes':395163085,'double_end_checks':len(checks),'mismatches':0,
    'materials':checks,'protected15_root_source':protected,'original19_checksum_only':original,
    'owned_source_raw_git_identity':owned,'actual_raw_git_identity':raws,'fixed_public_dependencies':dependencies,
    'source_mapping':proof(reference/'sources.json'),'preserved_sqlite_connections':0,'credentials_read':0,'network_calls':0,'old_preservation_targets_touched':False}
(out/'integrity.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['materials','protected15_root_source','owned_source_raw_git_identity']}))
