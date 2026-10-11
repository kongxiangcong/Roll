"""Independent byte-only audit; saved SQLite never connected."""
import json,hashlib,stat,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
root=Path('D:/dsh-proj/Roll');source=root/'.scratch/worktrees/ticket25-ordering'
ev=source/'.scratch/roll-p0/evidence/ticket25-ordering'
out=root/'.scratch/roll-p0/evidence/continuation-2026-10-11/ticket25-ordering-independent'
def native(p):return Path('\\\\?\\'+str(p))
def proof(p):
    p=Path(p);s=native(p).lstat();assert stat.S_ISREG(s.st_mode) and not s.st_file_attributes & 0x400,str(p)
    assert not any(t in p.name.lower() for t in ['auth','secret','credential']),str(p)
    with native(p).open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'path':str(p),'bytes':s.st_size,'sha256':sha}
def check(p,row):
    r=proof(p);assert (r['bytes'],r['sha256'])==(row['bytes'],row['sha256']),str(p);return r
def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args])
assert git(source,'rev-parse','HEAD').decode().strip()=='9332d0cd78d721301faf675354aa209db3b37dea'
assert not git(source,'diff','--name-only') and not git(source,'diff','--cached','--name-only')
manifest=ev/'preservation-manifest.json';m=json.loads(manifest.read_bytes());rows=m['rows']
target=root/'.roll-data/implementation-evidence/ticket25-ordering'
assert Path(m['own_tree'])==source and Path(m['namespace'])==target
assert len(rows)==m['file_count']==2039 and sum(r['bytes'] for r in rows)==m['bytes']==154331607
assert m['exclusions']==m['failures']==[] and m['sqlite_connections']==m['deleted_files']==0
assert proof(manifest)=={'path':str(manifest),'bytes':1432272,'sha256':'2ebf5d583dc3d75210a891ac66f6499bb61ba48205a1acdea233419c2e97d429'}
assert (target/'preservation-manifest.json').read_bytes()==manifest.read_bytes()
jobs=[];parents=set();seen=set()
for row in rows:
    s=Path(row['source']);d=Path(row['destination']);rel=s.relative_to(source)
    assert rel.as_posix()==row['relative'] and d.relative_to(target)==Path('runtime')/rel
    assert s not in seen;seen.add(s)
    assert any(s.is_relative_to(source/p) for p in ['.ord','.scratch/roll-p0/run-ordering','.pytest_cache'])
    jobs.extend([(s,row),(d,row)])
    for p,b in [(s,source),(d,target)]:
        cursor=p.parent
        while cursor.is_relative_to(b):parents.add(cursor);cursor=cursor.parent
for p in parents:assert not native(p).lstat().st_file_attributes & 0x400,str(p)
with ThreadPoolExecutor(max_workers=8) as pool:checks=list(pool.map(lambda pair:check(*pair),jobs))
fixed=json.loads((root/'.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json').read_bytes())[:15]
protected=[check(repo/r['path'],r) for r in fixed for repo in [root,source]]
prior=json.loads((source/'.scratch/roll-p0/evidence/ticket25/source-guard-latest.json').read_bytes())
artifacts=[check(r['path'],r) for r in prior['allowed_model_artifacts_unchanged']]
original=check(root/'.roll-data/reconstructed19-v1/roll.sqlite3',{'bytes':165814272,'sha256':'ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'})
old=[]
for name in ['runtime-preservation.json','runtime-preservation-all.json','runtime-preservation-states.json','runtime-preservation-handoff.json','runtime-preservation-latest.json','source-guard-latest.json']:
    rel='.scratch/roll-p0/evidence/ticket25/'+name
    bodies=[git(repo,'show','HEAD:'+rel) for repo in [root,source]]
    assert bodies[0]==bodies[1],rel
    for repo in [root,source]:assert (repo/rel).read_bytes().replace(b'\r\n',b'\n')==bodies[0].replace(b'\r\n',b'\n'),rel
    old.append({'path':rel,'root':proof(root/rel),'source':proof(source/rel),'git_equal':True})
owned=[]
rel='.scratch/roll-p0/evidence/continuation-2026-10-11/ticket25-preservation-additional/roll-ticket25-cleanup-additional-manifest.json'
assert git(root,'show','HEAD:'+rel)==git(source,'show','HEAD:'+rel)
for repo in [root,source]:
    p=repo/rel
    old.append({'path':rel,'metadata':check(p,{'bytes':8717987,'sha256':'24b5e32692348db6459ef14f96e546f9ed12373b79bdce012d5a713b49f2472d'}),'git_equal':True})
for rel in ['backend/src/roll/decisions/actions.py','backend/src/roll/decisions/capabilities.py','backend/tests/support/action_order_method.py','backend/tests/application/test_action_risk_priority.py','backend/tests/application/test_action_invalidation_fact.py']:
    raw=(source/rel).read_bytes();blob=git(source,'show','HEAD:'+rel)
    assert raw.replace(b'\r\n',b'\n')==blob.replace(b'\r\n',b'\n'),rel
    owned.append({**proof(source/rel),'git_blob':git(source,'rev-parse','HEAD:'+rel).decode().strip()})
r={'source_head':'9332d0cd78d721301faf675354aa209db3b37dea','files':len(rows),'bytes':m['bytes'],'dual_checks':len(checks),'mismatches':0,'manifest':proof(manifest),'materials':checks,'protected15_root_source':protected,'allowed3_checksum_only':artifacts,'original19_checksum_only':original,'old6_metadata_raw_git_unchanged':old,'owned_source_raw_git_identity':owned,'saved_sqlite_connections':0,'real_network_calls':0,'source_tracked_index_clean':True}
(out/'integrity.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in r.items() if k not in ['materials','protected15_root_source','old6_metadata_raw_git_unchanged','owned_source_raw_git_identity']}))
