import os,json,hashlib,shutil,subprocess
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
v=Path(__file__).parent; root=Path('D:/dsh-proj/Roll')
before=v/'roll-cleanup-batch-v6-preflight.json'; parent=v/'roll-cleanup-v15-before-native-resume.json'
assert not parent.exists(); shutil.copyfile(before,parent)
p=json.loads(parent.read_text(encoding='utf-8-sig'))
failed=json.loads((v/'roll-cleanup-final-execute-failure.json').read_text(encoding='utf-8-sig'))
assert failed['executor']=='roll-cleanup-batch-v15-root-exact-batch.ps1' and 'line 408' in failed['script_stack']
assert failed['error']=='Git failed: show-ref --verify refs/heads/ codex/roll-p0-ticket25'
git='C:/Program Files/Git/cmd/git.exe'
def g(*args):return subprocess.check_output([git,'--no-optional-locks','-c','core.longpaths=true','-C',str(root),*args],text=True,encoding='utf-8').splitlines()
assert g('rev-parse','HEAD')[0]==p['root_head'] and not g('diff','--cached','--name-only') and not g('diff','--name-only')
assert (datetime.now(timezone.utc)-datetime.fromisoformat(p['created_utc'].replace('Z','+00:00'))).total_seconds()<3600
trees=p['trees']; removed=[t['path'] for t in trees if not os.path.exists(t['path'])]
assert removed==[trees[0]['path']] and trees[0]['branch']=='codex/roll-p0-ticket25'
registry=g('worktree','list','--porcelain')
for t in trees:
    assert g('rev-parse','refs/heads/'+t['branch'])[0]==t['oid']
    if t['path'] in removed: assert 'worktree '+t['path'].replace('\\','/') not in registry
private=json.loads((v/'roll-cleanup-batch-v10-private-retention.json').read_text(encoding='utf-8-sig'))
assert private['status']=='PRIVATE_RETENTION_PASS' and private['release_id']==p['release_id']
moved=[m['source'] for m in private['retained_private_metadata']]
assert len(moved)==2 and all(not os.path.exists(x) for x in moved)
for j in p['junctions']: assert not os.path.lexists(j['path']) and os.path.isdir(j['target'])
def omitted(x):return x in moved or any(x.lower().startswith(a.lower()+'\\') for a in removed)
checks=[]
for t in trees[1:]:
    expected=[r['path'] for r in p['source_inventory'] if r['path'].lower().startswith(t['path'].lower()+'\\') and not omitted(r['path'])]
    current=[]; queue=[t['path']]; root_git=os.path.normcase(os.path.join(t['path'],'.git'))
    while queue:
        with os.scandir('\\\\?\\'+queue.pop()) as entries:
            for e in entries:
                s=e.stat(follow_symlinks=False); assert not (s.st_file_attributes&1024)
                name=e.path.removeprefix('\\\\?\\')
                if e.is_dir(follow_symlinks=False): queue.append(name)
                elif os.path.normcase(name)!=root_git: current.append(os.path.normpath(name))
    assert Counter(x.lower() for x in expected)==Counter(x.lower() for x in current),t['path']
    checks.append(dict(tree=t['path'],expected=len(expected),actual=len(current),identical=True))
metadata=0
for r in p['proofs']+p['source_inventory']:
    if omitted(r['path']):continue
    s=os.stat('\\\\?\\'+r['path'],follow_symlinks=False)
    assert not(s.st_file_attributes&1024) and s.st_size==r['bytes'] and s.st_mtime_ns//100+621355968000000000==r['mtime_ticks'],r['path']
    metadata+=1
oldexe=v/'roll-cleanup-batch-v15-root-exact-batch.ps1'; newexe=v/'roll-cleanup-batch-v16-root-exact-resume.ps1'
raw=oldexe.read_bytes(); begin=raw.index(b"if($Phase -eq 'Execute'){"); end=raw.index(b"if($Phase -eq 'Post'){")
block=r'''if($Phase -eq 'Execute'){
 if(([datetime]::UtcNow-([datetime]$Before.created_utc)).TotalMinutes -gt 60){throw 'Original preflight window expired; no further removals'}
 $resume=Read (Join-Path $Out 'roll-cleanup-v16-native-resume.json')
 if($resume.release_id -ne $Release.coordinator_release_id -or $resume.root_head -ne $Release.root_head -or @($resume.already_removed).Count -ne 1 -or $resume.already_removed[0] -ne $Trees[0].path -or $Trees[0].branch -ne 'codex/roll-p0-ticket25'){throw 'Exact single prior removal resume differs'}
 $removed=@($resume.already_removed);$remaining=@($Trees|Where-Object {$_.path -notin $removed})
 if($remaining.Count -ne 9 -or $Managed.Count){throw 'Exact nine unmanaged remaining required'}
 $registry=@(G $Root @('worktree','list','--porcelain'))
 foreach($t in $Trees){if(@(G $Root @('rev-parse',('refs/heads/'+$t.branch)))[0] -ne $t.oid){throw 'Accepted retained branch OID changed'}}
 foreach($p in $removed){if(Test-Path -LiteralPath $p){throw 'Prior removed tree returned'};if($registry -contains ('worktree '+$p.Replace('\','/'))){throw 'Prior removed tree remains registered'}}
 $retainedPrivateMetadata=@(VerifyRetainedPrivateMetadata)
 foreach($j in $Before.junctions){if(Test-Path -LiteralPath ('\\?\'+$j.path)){throw 'Previously unlinked junction returned'};if(-not(Test-Path -LiteralPath $j.target)){throw 'Root dependency target missing'}}
 foreach($t in $remaining){SourceGuard $t};$null=FreshProcesses
 foreach($r in @($Before.proofs)+@($Before.source_inventory)){
  $completedSource=$false;foreach($p in $removed){if($r.path.StartsWith($p+'\',[StringComparison]::OrdinalIgnoreCase)){$completedSource=$true}}
  if($completedSource -or $r.path -in $PrivateMoveSources){continue}
  $s=Stat $r.path;if($s.bytes -ne $r.bytes -or $s.mtime_ticks -ne $r.mtime_ticks){throw 'Remaining source/retained metadata changed; no further removal'}
 }
 foreach($t in $remaining){
  $now=@(Walk $t.path|Where-Object {-not($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -and (N $_.FullName) -ne (N (Join-Path $t.path '.git'))}|ForEach-Object {N $_.FullName}|Sort-Object)
  $old=@($Before.source_inventory|Where-Object {$_.path.StartsWith($t.path+'\',[StringComparison]::OrdinalIgnoreCase) -and $_.path -notin $PrivateMoveSources}|ForEach-Object path|Sort-Object)
  if(($now -join "`n") -ne ($old -join "`n")){throw 'Remaining source file set changed; no further removal'}
 }
 foreach($t in $remaining){
  $null=In $t.path (Join-Path $Root '.scratch/worktrees');SourceGuard $t
  if(@(Walk $t.path|Where-Object {$_.Attributes -band [IO.FileAttributes]::ReparsePoint}).Count){throw 'Residual reparse; stop'}
  $v=@(& $Git -c core.longpaths=true -C $Root worktree remove --force -- $t.path 2>&1);$code=$LASTEXITCODE
  if($code -ne 0 -or (Test-Path -LiteralPath $t.path)){Save 'roll-cleanup-batch-v6-native-failure.json' @{path=$t.path;exit=$code;already_removed=$removed;output=$v};throw 'Exact native remove failed/residual; no recursive fallback'}
  $removed+=$t.path
  Save 'roll-cleanup-v16-native-progress.json' @{status='PARTIAL_NATIVE_PROGRESS';removed=$removed;release_id=$Release.coordinator_release_id;private_moves_repeated=0;junction_unlinks_repeated=0}
  $null=G $Root @('show-ref','--verify',('refs/heads/'+$t.branch))
 }
 Save 'roll-cleanup-batch-v6-native-result.json' @{status='REMOVED_POST_PENDING';retained_private_metadata=$retainedPrivateMetadata;private_retention_receipt=$PrivateRetentionReceipt;removed=$removed;release_id=$Release.coordinator_release_id;branches_retained=$true;none_stopped=$true;hash_sweeps=1;prior_native_removals=1;resumed_native_removals=9;private_moves_repeated=0;junction_unlinks_repeated=0}
 return
}
'''.replace('\n','\n').encode('utf-8').replace(b'\n',b'\r\n')
newraw=raw[:begin]+block+raw[end:]
old=b"@('show-ref','--verify','refs/heads/'+$t.branch)"; new=b"@('show-ref','--verify',('refs/heads/'+$t.branch))"
assert newraw.count(old)==1; newraw=newraw.replace(old,new)
assert not newexe.exists();newexe.write_bytes(newraw)
sha=lambda x:hashlib.file_digest(x.open('rb'),'sha256').hexdigest()
resume=dict(kind='EXACT_PARTIAL_NATIVE_RESUME',release_id=p['release_id'],root_head=p['root_head'],already_removed=removed,remaining=[t['path'] for t in trees[1:]],retained_branches_exact=True,all_nine_corrected_file_sets=checks,remaining_and_retained_metadata_entries=metadata,remaining_and_retained_metadata_unchanged=True,private_retention_receipt_status=private['status'],private_moves_already=2,junction_unlinks_already=len(p['junctions']),private_moves_repeated=0,junction_unlinks_repeated=0,original_acceptance_time=p['created_utc'],original_acceptance_time_not_refreshed=True,parent_preflight=str(parent),parent_preflight_sha256=sha(parent),source_content_sweeps_added=0,private_content_reads=0,sqlite_connections=0,preceding_failure=failed)
control=v/'roll-cleanup-v16-native-resume.json';control.write_text(json.dumps(resume,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for file in (newexe,control):
 s=file.stat();p['proofs'].append(dict(path=str(file),bytes=s.st_size,mtime_ticks=s.st_mtime_ns//100+621355968000000000,sha256=sha(file)));p['post_paths'].append(str(file))
p['native_progress_resume']=resume
before.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
shutil.copyfile(v/'roll-cleanup-final-execute-failure.json',v/'roll-cleanup-v15-first-branch-argv-execute-failure.json')
shutil.copyfile(v/'roll-cleanup-final-execute-run.log',v/'roll-cleanup-v15-first-branch-argv-execute-run.log')
print(json.dumps(dict(status='EXACT_RESUME_CONTROL_PASS',already_removed=removed,remaining=9,metadata_entries=metadata,source_sweeps_added=0,original_acceptance_time=p['created_utc'])))
