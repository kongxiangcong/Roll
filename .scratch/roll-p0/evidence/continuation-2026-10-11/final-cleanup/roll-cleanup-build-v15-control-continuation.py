import os, json, hashlib, shutil
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
v=Path(__file__).parent
oldexe=v/'roll-cleanup-batch-v14-root-exact-batch.ps1'
newexe=v/'roll-cleanup-batch-v15-root-exact-batch.ps1'
raw=oldexe.read_bytes()
old=b"[IO.Path]::GetFileName($_.FullName) -ne '.git'"
new=b"(N $_.FullName) -ne (N (Join-Path $t.path '.git'))"
assert raw.count(old)==1
if newexe.exists(): assert newexe.read_bytes()==raw.replace(old,new)
else: newexe.write_bytes(raw.replace(old,new))
assert newexe.read_bytes().replace(new,old)==raw
before=v/'roll-cleanup-batch-v6-preflight.json'
original=v/'roll-cleanup-v14-original-accepted-preflight.json'
if not original.exists(): shutil.copyfile(before,original)
sha=lambda p: hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
original_sha=sha(original)
assert sha(before)==original_sha
p=json.loads(original.read_text(encoding='utf-8-sig'))
assert p['status']=='PREFLIGHT_PASS'
assert (datetime.now(timezone.utc)-datetime.fromisoformat(p['created_utc'].replace('Z','+00:00'))).total_seconds()<3600
checks=[]
for t in p['trees']:
    base=t['path']; root_git=os.path.normcase(os.path.join(base,'.git'))
    expected=[r['path'] for r in p['source_inventory'] if r['path'].lower().startswith(base.lower()+'\\')]
    current=[]; queue=[base]
    while queue:
        with os.scandir(queue.pop()) as entries:
            for e in entries:
                s=e.stat(follow_symlinks=False)
                if s.st_file_attributes & 1024: continue
                if e.is_dir(follow_symlinks=False): queue.append(e.path)
                elif os.path.normcase(e.path)!=root_git: current.append(os.path.normpath(e.path))
    a=Counter(x.lower() for x in expected); b=Counter(x.lower() for x in current)
    assert a==b, (base,list((a-b).elements()),list((b-a).elements()))
    checks.append(dict(tree=base,expected=len(expected),actual=len(current),identical=True))
for r in p['proofs']+p['source_inventory']:
    s=os.stat('\\\\?\\'+r['path'],follow_symlinks=False)
    assert not (s.st_file_attributes & 1024)
    assert s.st_size==r['bytes'] and s.st_mtime_ns//100+621355968000000000==r['mtime_ticks'],r['path']
s=newexe.stat()
proof=dict(path=str(newexe),bytes=s.st_size,mtime_ticks=s.st_mtime_ns//100+621355968000000000,sha256=sha(newexe))
p['proofs'].append(proof); p['post_paths'].append(str(newexe))
continuation=dict(kind='CONTROL_GUARD_CORRECTION_CONTINUATION',created_utc=datetime.now(timezone.utc).isoformat(),original_preflight=str(original),original_preflight_bytes=original.stat().st_size,original_preflight_sha256=original_sha,original_created_utc_preserved=True,old_executor=str(oldexe),new_executor=proof,exact_replacement_old=old.decode(),exact_replacement_new=new.decode(),corrected_source_file_sets=checks,all_previous_proof_and_inventory_metadata_unchanged=True,source_or_saved_content_hash_sweeps_added=0,private_body_reads=0,sqlite_connections=0,deleted=0,private_moves=0)
p['control_guard_continuation']=continuation
before.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
continuation['continued_preflight_sha256']=sha(before)
(v/'roll-cleanup-v15-control-continuation.json').write_text(json.dumps(continuation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for source,target in [('roll-cleanup-final-execute-failure.json','roll-cleanup-v14-first-fileset-execute-failure.json'),('roll-cleanup-final-execute-run.log','roll-cleanup-v14-first-fileset-execute-run.log')]:
    assert not (v/target).exists()
    shutil.copyfile(v/source,v/target)
print(json.dumps(dict(status='CONTROL_CONTINUATION_PASS',trees=len(checks),metadata_entries=len(p['proofs'])+len(p['source_inventory'])-1,source_byte_sweeps_added=0,original_preflight_created_utc=p['created_utc'])))
