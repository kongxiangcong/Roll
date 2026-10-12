# V14 exact one public cache current/historical split; original manifests and old saved bytes retained.
# V13 four bounded readonly byte workers; same five verifier definitions, every ancestor fresh.
# V12 verifies every actual live candidate and rechecks only the identities proved in this call; retired approvals are historical.
# V11 same SHA256 stream function with explicit 1MiB read buffering; prior V10 readonly interruption retained.
# V10 exact two-file private retention; metadata FileID continuity and same-volume rename only. V9c retained unchanged.
# V6 PREPARED ONLY. Default is metadata-only. Never dot-source v2.
# implement-spec step9 authorizes cleanup; root coordinator opens the final window.
# Windows PowerShell 7 required (GetRelativePath / long literal paths).
[CmdletBinding()]
param([ValidateSet('Metadata','Preflight','Execute','Post')][string]$Phase='Metadata',
 [string]$ReleaseFile,[switch]$RootExecutionWindow)
$ErrorActionPreference='Stop';Set-StrictMode -Version 3
$Root='D:\dsh-proj\Roll';$Out=$PSScriptRoot
$Git=@(Get-Command git.exe -CommandType Application)[0].Source
function N([string]$p){if($p.StartsWith('\\?\UNC\')){$p='\\'+$p.Substring(8)}elseif($p.StartsWith('\\?\')){$p=$p.Substring(4)};[IO.Path]::GetFullPath($p.Replace('/','\')).TrimEnd('\')}
function In([string]$p,[string]$b){$p=N $p;$b=N $b;if($p -ne $b -and -not $p.StartsWith($b+'\',[StringComparison]::OrdinalIgnoreCase)){throw "Outside exact boundary: $p"};$p}
function Resolve([string]$p,[string]$b){if([IO.Path]::IsPathFullyQualified($p)){N $p}else{N (Join-Path $b $p)}}
function GetProp($obj,[string]$name,$default=$null){if($null -ne $obj -and $null -ne $obj.PSObject.Properties[$name]){$obj.$name}else{$default}}
function Read($p){Get-Content -LiteralPath ('\\?\'+(N $p)) -Raw|ConvertFrom-Json}
function Save($n,$v){[IO.File]::WriteAllText((Join-Path $Out $n),($v|ConvertTo-Json -Depth 30)+"`n",[Text.UTF8Encoding]::new($false))}
function G($repo,[string[]]$arguments){$v=@(& $Git --no-optional-locks -c core.longpaths=true -C $repo @arguments 2>&1);if($LASTEXITCODE){throw ('Git failed: '+($arguments -join ' '))};$v}
function Ancestors($p){$par=[IO.Directory]::GetParent((N $p));while($par){$i=[IO.DirectoryInfo]::new('\\?\'+$par.FullName);if(-not $i.Exists){throw 'Required regular ancestor missing'};if($i.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse ancestor refused before file read'};$par=$par.Parent}}
function Stat($p){Ancestors $p;$i=[IO.FileInfo]::new('\\?\'+(N $p));if(-not $i.Exists -or ($i.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Regular file required'};[pscustomobject]@{path=N $p;bytes=[long]$i.Length;mtime_ticks=$i.LastWriteTimeUtc.Ticks}}
function Proof($p){$s=Stat $p;$stream=[IO.FileStream]::new('\\?\'+$s.path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read,1048576,[IO.FileOptions]::SequentialScan);try{$sha=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($stream)).ToLowerInvariant()}finally{$stream.Dispose()};$s|Add-Member -NotePropertyName sha256 -NotePropertyValue $sha;$s}
function Private($p){$n=[IO.Path]::GetFileName($p);$n -like '.env*' -or $n -in @('auth.json','method-auth.json','api.json','chatgpt.json','credentials.json','credential.json','secrets.json','channel.json','channel.lock') -or (N $p) -match '\\notification-private\\'}
function Walk($base){$q=[Collections.Generic.Stack[string]]::new();$q.Push((N $base));while($q.Count){foreach($i in @(Get-ChildItem -LiteralPath ('\\?\'+$q.Pop()) -Force)){if($i.Attributes -band [IO.FileAttributes]::ReparsePoint){$i}elseif($i.PSIsContainer){$q.Push((N $i.FullName))}else{$i}}}}
$Meta=Read (Join-Path $Out 'roll-cleanup-batch-v6-metadata.json')
$ForcedMetadataOnly=@($Meta.forced_metadata_only_paths|ForEach-Object {N $_})
if($Phase -eq 'Metadata'){
 $Meta.trees|Select-Object name,path,expected_accepted_oid,observed_head,dynamic_required_accepted_final,observed_tracked_dirty
 return # No runtime walk / hash / CIM / Git mutation in this phase.
}
if(-not $RootExecutionWindow -or -not $ReleaseFile){throw 'Final internal execution/Git window and exact release file required; no user reapproval needed'}
$ReleaseFile=In $ReleaseFile $Out;$Release=Read $ReleaseFile
# UNKNOWN private origin stays UNKNOWN. These are retention moves, never synthetic disposal.
$PrivateFileIDHelper=Join-Path $Out 'roll-cleanup-private-file-id-v10.cs'
$PrivateRetentionReceipt=Join-Path $Out 'roll-cleanup-batch-v10-private-retention.json'
$PrivateSourceBase=N (Join-Path $Root '.scratch/worktrees/ticket28/backend/.test-tmp-notifications-browser-green2/notification-private')
$PrivateDestinationBase=N (Join-Path $Root '.roll-data/implementation-evidence/final-cleanup-private-retained-20261012/ticket28/browser-green2/notification-private')
$PrivateMoves=@(GetProp $Release 'exact_private_retention_moves' @())
if($PrivateMoves.Count -ne 2){throw 'Exactly two private retention moves required'}
$PrivateMoveSources=@();$PrivateMoveTargets=@()
foreach($name in @('channel.json','channel.lock')){
 $source=N (Join-Path $PrivateSourceBase $name);$destination=N (Join-Path $PrivateDestinationBase $name)
 $matches=@($PrivateMoves|Where-Object {(N $_.source) -eq $source -and (N $_.destination) -eq $destination})
 if($matches.Count -ne 1){throw 'Exact private retention source/destination differs'}
 $m=$matches[0]
 if($m.kind -ne 'PRIVATE_METADATA_RETENTION_MOVE' -or $m.classification -ne 'UNKNOWN' -or -not $m.source_provenance -or -not $m.accepted_receipt){throw 'Private retention provenance or UNKNOWN classification missing'}
 $null=In $m.accepted_receipt (Join-Path $Root '.scratch/roll-p0/evidence')
 if(([IO.Path]::GetPathRoot($source)) -ne 'D:\' -or ([IO.Path]::GetPathRoot($destination)) -ne 'D:\'){throw 'Private rename requires exact D volume paths'}
 $PrivateMoveSources+=$source;$PrivateMoveTargets+=$destination
}
function LoadPrivateMetadataHelper{
 if(-not ('RollCleanupV10.NativeMetadata' -as [type])){Add-Type -Path $PrivateFileIDHelper}
}
function PrivateMetadata([string]$p){
 LoadPrivateMetadataHelper;Ancestors $p
 [RollCleanupV10.NativeMetadata]::File('\\?\'+(N $p))
}
function RetentionDestinationGuard([string]$p,[string]$volume){
 $p=N $p;$null=In $p $PrivateDestinationBase
 if($p -notin $PrivateMoveTargets){throw 'Unplanned private destination'}
 if(Test-Path -LiteralPath ('\\?\'+$p) -ErrorAction Stop){throw 'Private target must be absent; never overwrite'}
 LoadPrivateMetadataHelper
 $parent=[IO.Directory]::GetParent($p);$nearest=$null
 while($parent){
  if(Test-Path -LiteralPath ('\\?\'+$parent.FullName) -ErrorAction Stop){
   $d=[RollCleanupV10.NativeMetadata]::Directory('\\?\'+$parent.FullName)
   if(-not $nearest){$nearest=$d}
   if($d.volume_serial -ne $volume){throw 'Private retention ancestor volume differs'}
  }
  $parent=$parent.Parent
 }
 if(-not $nearest){throw 'No existing regular destination ancestor'}
 $rootVolume=[RollCleanupV10.NativeMetadata]::Directory('\\?\D:\')
 if($rootVolume.volume_serial -ne $volume){throw 'Private retention must stay on actual D root volume'}
}
function SamePrivateMetadata($a,$b){
 foreach($k in @('volume_serial','file_id','bytes','mtime_ticks','attributes','number_of_links')){if([string]$a.$k -ne [string]$b.$k){throw ('Private FileID/metadata differs: '+$k)}}
}
function PrivatePreflightMetadata{
 $result=@()
 foreach($m in $PrivateMoves){
  $s=N $m.source;$d=N $m.destination;$null=In $s $PrivateSourceBase
  $meta=PrivateMetadata $s
  if([long]$meta.bytes -ne [long]$m.bytes_from_prior_metadata){throw 'Private prior length differs; retain source and stop'}
  RetentionDestinationGuard $d $meta.volume_serial
  $result+=@{source=$s;destination=$d;kind=$m.kind;classification='UNKNOWN';source_provenance=$m.source_provenance;accepted_receipt=$m.accepted_receipt;metadata=$meta;contents_read=$false;hashed=$false;copied=$false;acl_read=$false}
 }
 $result
}
function PrivateBeforeGuard{
 $beforeMoves=@(GetProp $Before 'private_retention_moves' @())
 if($beforeMoves.Count -ne 2){throw 'Bound private metadata preflight missing'}
 foreach($m in $PrivateMoves){
  $matched=@($beforeMoves|Where-Object {$_.source -eq (N $m.source) -and $_.destination -eq (N $m.destination) -and $_.kind -eq $m.kind -and $_.classification -eq 'UNKNOWN'})
  if($matched.Count -ne 1){throw 'Private preflight plan changed'}
 }
 $beforeMoves
}
function MoveRetainedPrivateMetadata{
 $beforeMoves=@(PrivateBeforeGuard);$moved=@()
 # Guard BOTH identities/targets before any mkdir or rename.
 foreach($m in $beforeMoves){SamePrivateMetadata $m.metadata (PrivateMetadata $m.source);RetentionDestinationGuard $m.destination $m.metadata.volume_serial}
 foreach($m in $beforeMoves){
  try{
   SamePrivateMetadata $m.metadata (PrivateMetadata $m.source);RetentionDestinationGuard $m.destination $m.metadata.volume_serial
   $parent=In ([IO.Path]::GetDirectoryName($m.destination)) $PrivateDestinationBase
   $null=[IO.Directory]::CreateDirectory('\\?\'+$parent)
   Ancestors $m.destination
   $dir=[RollCleanupV10.NativeMetadata]::Directory('\\?\'+$parent)
   if($dir.volume_serial -ne $m.metadata.volume_serial){throw 'Created destination volume differs'}
   RetentionDestinationGuard $m.destination $m.metadata.volume_serial
   SamePrivateMetadata $m.metadata (PrivateMetadata $m.source)
   Move-Item -LiteralPath ('\\?\'+$m.source) -Destination ('\\?\'+$m.destination) -ErrorAction Stop
   $after=PrivateMetadata $m.destination;SamePrivateMetadata $m.metadata $after
   if(Test-Path -LiteralPath ('\\?\'+$m.source) -ErrorAction Stop){throw 'Private source still exists after rename'}
   $moved+=@{source=$m.source;destination=$m.destination;classification='UNKNOWN';kind=$m.kind;metadata=$after;source_absent=$true;contents_read=$false;hashed=$false;copied=$false;acl_read=$false;operation='SAME_VOLUME_LITERAL_RENAME';acl_semantics='Same-volume move retains original file security; ACL not read or independently verified'}
   Save 'roll-cleanup-batch-v10-private-retention.json' @{status=$(if($moved.Count -eq 2){'PRIVATE_RETENTION_PASS'}else{'PRIVATE_RETENTION_PARTIAL'});release_id=$Release.coordinator_release_id;root_head=$Release.root_head;retained_private_metadata=$moved;none_stopped=$true;private_content_reads=0;private_hashes=0;private_copies=0;acl_reads=0}
  }catch{
   Save 'roll-cleanup-batch-v10-private-retention-failure.json' @{status='STOP_PRIVATE_RETENTION';release_id=$Release.coordinator_release_id;already_retained=$moved;failing_source=$m.source;failing_destination=$m.destination;private_content_reads=0;private_hashes=0;private_copies=0;acl_reads=0}
   throw
  }
 }
 $moved
}
function VerifyRetainedPrivateMetadata{
 $beforeMoves=@(PrivateBeforeGuard);$receipt=Read $PrivateRetentionReceipt
 if($receipt.status -ne 'PRIVATE_RETENTION_PASS' -or $receipt.release_id -ne $Release.coordinator_release_id -or $receipt.root_head -ne $Release.root_head -or @($receipt.retained_private_metadata).Count -ne 2){throw 'Completed exact private move receipt missing'}
 $retained=@()
 foreach($m in $beforeMoves){
  if(Test-Path -LiteralPath ('\\?\'+$m.source) -ErrorAction Stop){throw 'Private source returned after retention'}
  $matching=@($receipt.retained_private_metadata|Where-Object {$_.source -eq $m.source -and $_.destination -eq $m.destination -and $_.classification -eq 'UNKNOWN'})
  if($matching.Count -ne 1){throw 'Private move receipt exact path mismatch'}
  $after=PrivateMetadata $m.destination;SamePrivateMetadata $m.metadata $after;SamePrivateMetadata $matching[0].metadata $after
  $retained+=@{source=$m.source;destination=$m.destination;metadata=$after;classification='UNKNOWN';source_absent=$true;contents_read=$false;hashed=$false;copied=$false;acl_read=$false}
 }
 $retained
}
foreach($key in @('final29_accepted','ninth30_accepted','final31_accepted','final_review_accepted')){if((GetProp $Release $key $false) -ne $true){throw "Required final acceptance not released: $key"}}
foreach($key in @('root_dependency_baseline_after_all_tests','all_test_processes_stopped_or_exact_outside_owned')){if((GetProp $Release $key $false) -ne $true){throw "Final cleanup interval baseline/owner release missing: $key"}}
if(-not $Release.coordinator_release_id -or $Release.root_head -notmatch '^[0-9a-f]{40}$'){throw 'Concrete coordinator/root identity required'}
if(@(G $Root @('rev-parse','HEAD'))[0] -ne $Release.root_head){throw 'Root tip changed; no operation'}
if(@(G $Root @('diff','--cached','--name-only')).Count){throw 'Root index occupied'}
$Trees=@();$Managed=@()
foreach($m in $Meta.trees){
 $matches=@($Release.trees|Where-Object name -eq $m.name);if($matches.Count -ne 1){throw 'Missing/duplicate release tree'};$r=$matches[0]
 if($r.no_worktree_required_receipt){
  if($m.name -notin @('final31','final-singlefix')){throw 'Existing tree cannot be bypassed'}
  $null=In $r.no_worktree_required_receipt $Root
  if(-not(Test-Path -LiteralPath $r.no_worktree_required_receipt)){throw 'No-tree reviewer/coordinator receipt missing'}
  continue
 }
 if($r.accepted_final -ne $true -or $r.oid -notmatch '^[0-9a-f]{40}$' -or -not $r.branch -or -not $r.finite_acceptance_receipt){throw 'Stable accepted OID, branch and receipt required'}
 $p=N $r.path;if($p -eq (N $Root) -or $p -eq (N $Meta.excluded_archived_managed)){throw 'Root/archived old31 never a removal target'}
 if($m.path -and $p -ne (N $m.path)){throw 'Exact source path changed'}
 if($m.expected_accepted_oid -and $r.oid -ne $m.expected_accepted_oid){throw 'Accepted old source changed; new source requires separate receipt and plan update'}
 $receipt=In $r.finite_acceptance_receipt $Root;if(-not(Test-Path -LiteralPath $receipt)){throw 'Acceptance receipt missing'}
 if($r.lifecycle -eq 'UNMANAGED_GIT'){$null=In $p (Join-Path $Root '.scratch/worktrees')}
 elseif($r.lifecycle -eq 'MANAGED_APP'){
  $null=In $p 'C:\Users\72449\.codex\worktrees'
  if(-not $r.managed_identity -or (N $r.managed_identity) -ne $p){throw 'Exact list_artifacts managed identity required'}
  $Managed+=,$r
 }else{throw 'Unknown lifecycle; native cleanup forbidden'}
 $Trees+=,[pscustomobject]@{name=$m.name;path=$p;oid=$r.oid;branch=$r.branch;lifecycle=$r.lifecycle;release=$r;metadata=$m}
}
function SourceGuard($t){
 $i=Get-Item -LiteralPath ('\\?\'+$t.path) -Force;if($i.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Tree root reparse'}
 Ancestors $t.path
 if(@(G $t.path @('rev-parse','HEAD'))[0] -ne $t.oid -or @(G $t.path @('branch','--show-current'))[0] -ne $t.branch){throw 'Source OID/branch changed'}
 $null=G $Root @('merge-base','--is-ancestor',$t.oid,'HEAD')
 if(@(G $t.path @('status','--porcelain=v1','--untracked-files=no')).Count){throw 'Tracked source/index dirty'}
}
function PublicAllowed($p){
 if((N $p) -in $PrivateMoveSources -or (N $p) -in $PrivateMoveTargets){return $false} # Retention files can never enter a byte proof.
 # Root expressly excludes the ninth runner chatgpt.json source AND saved target.
 # Even an exact public-fixture allow record cannot authorize content access here.
 if((N $p) -in $ForcedMetadataOnly){return $false}
 foreach($t in $Trees){foreach($a in @($t.release.public_fixture_allow)){if($null -eq $a){continue};if((N $a.path) -eq (N $p)){
  if($a.kind -ne 'PUBLIC_METHOD_FIXTURE' -or -not $a.source_provenance -or -not $a.accepted_receipt){throw 'Exact METHOD provenance missing'};return $true
 }}}
 foreach($a in @($Release.public_package_fixtures)){if($null -eq $a){continue};if((N $a.path) -eq (N $p)){
  if($a.kind -ne 'PUBLIC_PACKAGE_FIXTURE' -or -not $a.package_metadata_provenance){throw 'Exact package fixture provenance missing'};return $true
 }}
 return $false
}
function FreshProcesses{
 $all=@(Get-CimInstance Win32_Process -ErrorAction Stop);$blocked=@();$outside=@();$verifiedOutsideRecords=@()
 foreach($p in $all){
  $date=([datetime]$p.CreationDate).ToUniversalTime().ToString('o')
  $cmd=([string]$p.CommandLine).Replace('/','\');$exe=([string]$p.ExecutablePath).Replace('/','\');$exact=$false
  foreach($t in $Trees){$pattern=[regex]::Escape($t.path)+'(?=\\|\s|["'']|$)';if($cmd -match $pattern -or $exe -match $pattern){$exact=$true}}
  $owners=@($Release.process_owner_records|Where-Object {[int]$_.pid -eq [int]$p.ProcessId -and ([datetime]$_.creation_date_utc).ToUniversalTime().ToString('o') -eq $date})
  $shared=([string]$p.Name -match '^(pythonw?|node)(\.exe)?$' -or $cmd -match [regex]::Escape((Join-Path $Root 'backend/.venv').Replace('/','\')) -or $exe -match [regex]::Escape((Join-Path $Root 'frontend/node_modules').Replace('/','\')))
  if($exact -or @($owners|Where-Object disposition -eq 'OWN_DELETE_TREE').Count){$blocked+=@{pid=$p.ProcessId;creation_date_utc=$date;reason='EXACT_SOURCE_OWNER_LIVE'};continue}
  if($shared){
   if($owners.Count -eq 1 -and $owners[0].disposition -eq 'OUTSIDE_DELETION_SCOPE' -and $owners[0].source_receipt -and (ExactOutsideBoundary $p $owners[0] $all)){$outside+=@{pid=$p.ProcessId;creation_date_utc=$date;source_receipt=$owners[0].source_receipt};$verifiedOutsideRecords+=,$owners[0]}
   else{$blocked+=@{pid=$p.ProcessId;creation_date_utc=$date;reason='SHARED_OR_RELATIVE_ARGV_OWNER_UNKNOWN'}}
  }
 }
 if($blocked.Count){Save 'roll-cleanup-batch-v6-process-blockers.json' @{processes=$blocked;none_stopped=$true};throw 'Live/unknown owner blocks; use concrete PID+CreationDate owner receipt; never broad kill'}
 $after=@(Get-CimInstance Win32_Process -ErrorAction Stop)
 foreach($r in $verifiedOutsideRecords){$live=@($after|Where-Object {[int]$_.ProcessId -eq [int]$r.pid});if($live.Count -ne 1 -or -not(ProcessIdentityMatch $live[0] $r)){throw 'Outside process identity changed after bounded proof; no deletion'}}
 @{queried=$true;blocked=0;outside=$outside;none_stopped=$true;relative_cwd_contract='EXACT_RELATIVE_MODULE_OUTSIDE_WITH_CWD';command_lines_saved=0;environment_reads=0}
}
function Rows($t){
 $descs=@($t.metadata.manifests)+@($t.release.additional_manifests)
 if(-not $descs.Count){throw 'Final source has no preserved manifest'}
 foreach($d in $descs){
  if($null -eq $d){continue};$path=N $d.path
  if(-not $path.StartsWith($t.path+'\',[StringComparison]::OrdinalIgnoreCase)){
   if($path.StartsWith((N $Out)+'\',[StringComparison]::OrdinalIgnoreCase)){$null=In $path $Out}
   else{$null=In $path (Join-Path $Root '.scratch/roll-p0/evidence')}
  }
  $manifest=Read $path;$values=if($d.field -eq 'array'){@($manifest)}else{@($manifest.($d.field))}
  if($values.Count -ne $d.count -or ($values|Measure-Object bytes -Sum).Sum -ne $d.bytes){throw "Manifest metadata/count changed: $path"}
  foreach($v in $values){
   if($d.special -eq 'runner'){
    $part=$v.path.Replace('\','/').Split('/',2)
    if($part[0] -eq 'default-browser'){$b=Read (Join-Path $t.path '.scratch/roll-p0/evidence/continuation-2026-10-11/codex-runner-scope/browser-manifest.json');$base=In $b.data_root $t.path}
    elseif($part[0] -in @('crmr','crmg','crsf','crs25')){$base=Join-Path $t.path ('.scratch/'+$part[0])}else{throw 'Unknown runner prefix'}
    $s=In (Join-Path $base $part[1]) $t.path;$dest=Resolve $v.path $d.destination_base
   }else{
    $s=Resolve $v.source $d.source_base
    if(-not $s.StartsWith($t.path+'\',[StringComparison]::OrdinalIgnoreCase)){
     $exact=@($Release.exact_external_runtime_sources|Where-Object {$_.source -eq $s -and $_.manifest -eq $path -and $_.tree -eq $t.name -and $_.kind -eq 'ROOT_RETAINED_RUNTIME_SOURCE' -and $_.bytes -eq $v.bytes -and $_.sha256 -eq $v.sha256})
     if($exact.Count -ne 1 -or -not(Test-Path -LiteralPath $exact[0].source_owner_receipt -PathType Leaf)){throw 'External source lacks exact retained-root provenance'}
     $null=In $s (Join-Path $Root '.scratch');$null=In $exact[0].destination (Join-Path $Root '.roll-data/implementation-evidence')
     $dp=GetProp $v 'destination' (GetProp $v 'preserved' (GetProp $v 'target'));if((Resolve $dp $d.destination_base) -ne (N $exact[0].destination)){throw 'Exact external destination differs'}
    }else{$s=In $s $t.path}
    $dp=GetProp $v 'destination' (GetProp $v 'preserved' (GetProp $v 'target'));if(-not $dp){throw 'Unknown destination schema'};$dest=Resolve $dp $d.destination_base
   }
   $null=In $dest (Join-Path $Root '.roll-data/implementation-evidence')
   if($s -in $ForcedMetadataOnly -or $dest -in $ForcedMetadataOnly){
    if($t.name -ne 'codex-runner-scope' -or $s -ne (N $Meta.forced_metadata_only_dispositions[0].source) -or $dest -ne (N $Meta.forced_metadata_only_dispositions[0].preserved_target)){throw 'Unexpected forced metadata-only binding'}
    continue # Do not read/hash/copy either fixture. Its row stays in original manifest.
   }
   if($v.sha256 -notmatch '^[0-9a-f]{64}$' -or [long]$v.bytes -lt 0){throw 'Invalid byte proof'}
   $row=[pscustomobject]@{source=$s;destination=$dest;bytes=[long]$v.bytes;sha256=$v.sha256;manifest=$path}
   $versions=@($Release.exact_historical_source_versions|Where-Object {$_.source -eq $s -and $_.manifest -eq $path -and $_.historical_destination -eq $dest})
   if($versions.Count -gt 1){throw 'Duplicate exact historical cache binding'}
   if($versions.Count -eq 1){
    $z=$versions[0]
    if($z.kind -ne 'PUBLIC_PYTEST_CACHE_CURRENT_VERSION' -or $z.tree -ne $t.name -or $s -ne (Join-Path $Root '.scratch/worktrees/ticket30-producer/.pytest_cache/v/cache/nodeids') -or $z.historical_bytes -ne $v.bytes -or $z.historical_sha256 -ne $v.sha256 -or -not(Test-Path -LiteralPath $z.source_owner_receipt)){throw 'Exact public cache version provenance differs'}
    $null=In $z.current_destination (Join-Path $Root '.roll-data/implementation-evidence/final-cleanup-cache-current-20261012')
    $row|Add-Member -NotePropertyName source_expected_bytes -NotePropertyValue ([long]$z.current_bytes)
    $row|Add-Member -NotePropertyName source_expected_sha256 -NotePropertyValue $z.current_sha256
   }
   $row
  }
  # Source manifest and accepted root mirror are themselves retained proof.
  if($d.root_mirror -and (N $d.root_mirror) -ne $path){
   [pscustomobject]@{source=$path;destination=(In $d.root_mirror (Join-Path $Root '.scratch/roll-p0/evidence'));bytes=[long]$d.manifest_bytes;sha256=$null;manifest=$path}
  }
  if($d.self_copy){[pscustomobject]@{source=$path;destination=(In $d.self_copy.destination (Join-Path $Root '.roll-data/implementation-evidence'));bytes=[long]$d.self_copy.bytes;sha256=$d.self_copy.sha256;manifest=$path}}
 }
}
function Exclusions($t){
 foreach($d in @($t.metadata.exclusions)){
  if((GetProp $d 'exact_relative')){[pscustomobject]@{path=(In (Join-Path $t.path $d.exact_relative) $t.path);source_provenance=$d.provenance;kind=$d.kind};continue}
  $m=Read $d.path;$v=if($d.field -eq 'array'){@($m)}else{@($m.($d.field))};if($v.Count -ne $d.required_count){throw 'Exact private exclusion count changed'}
  foreach($r in $v){
   $sp=GetProp $r 'source' (GetProp $r 'path');$p=In (Resolve $sp $d.source_base) $t.path
   $pr=GetProp $r 'fixture_provenance' (GetProp $r 'owner_fixture' (GetProp $d 'source_provenance'));if(-not $pr){throw 'Private exclusion source provenance absent'}
   foreach($key in @('contents_read','hashed','copied')){if((GetProp $r $key $false) -eq $true){throw 'Private exclusion was consumed'}}
   if((GetProp $r 'opened_hashed_copied' $false) -eq $true){throw 'Private metadata-only exclusion consumed'}
   if($d.kind -eq 'METHOD_NOTIFICATION_PRIVATE_METADATA'){
    if($p -notmatch '\\notification-private\\channel\.(json|lock)$'){throw 'Not an exact synthetic notification exclusion'}
    if($t.name -eq 'ticket28' -and (GetProp $r 'identity' '') -notmatch 'METHOD fixture'){throw 'Ticket28 fixture identity missing'}
    if($t.name -eq 'ticket29' -and $pr -notmatch 'test_report_preserves_actual_28_worker_attempt_receipt'){throw 'Ticket29 fixture provenance missing'}
   }
   [pscustomobject]@{path=$p;source_provenance=$pr;kind=$d.kind}
  }
 }
 foreach($e in @($t.release.exact_exclusions)){if($null -eq $e){continue};$p=In $e.path $t.path;if($p -in $PrivateMoveSources){throw 'UNKNOWN retention source cannot be a METHOD disposal exclusion'};if(-not $e.source_provenance -or -not $e.accepted_receipt -or $e.kind -notin @('METHOD_AUTH_METADATA','METHOD_NOTIFICATION_PRIVATE_METADATA')){throw 'Unproven private exclusion'};[pscustomobject]@{path=$p;source_provenance=$e.source_provenance;kind=$e.kind}}
 foreach($m in $PrivateMoves){if((N $m.source).StartsWith($t.path+'\',[StringComparison]::OrdinalIgnoreCase)){
  if($t.name -ne 'ticket28' -or (N $m.source) -notin $PrivateMoveSources){throw 'Private retention tree/path differs'}
  [pscustomobject]@{path=N $m.source;destination=N $m.destination;source_provenance=$m.source_provenance;accepted_receipt=$m.accepted_receipt;kind='PRIVATE_METADATA_RETENTION_MOVE';classification='UNKNOWN'}
 }}
}
function ProtectedRows{
 $s=@(Read (Join-Path $Root '.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json'))
 foreach($r in $s[0..14]){[pscustomobject]@{path=(In (Resolve $r.path $Root) $Root);bytes=[long]$r.bytes;sha256=$r.sha256}}
 [pscustomobject]@{path=(Join-Path $Root '.roll-data/reconstructed19-v1/roll.sqlite3');bytes=165814272L;sha256='ec46257c4420f69c245791778c49079355700615cc3ed7b94d8027bd4dcf66c4'}
 foreach($a in @(@('062d5e3a5389d918367ee84d815250bfad8e7fe9bb4adfdeb73914f1a1002f50',16282),@('85966ee09476d01af83548fa66fbca644598cd36e108c70c0d826f92dcfdbb1d',474))){[pscustomobject]@{path=(Join-Path $Root ('.roll-data/implementation-evidence/continuation-review-fixes/actual-corrected-copy/raw/'+$a[0]+'.raw'));bytes=[long]$a[1];sha256=$a[0]}}
 [pscustomobject]@{path=(Join-Path $Root '.roll-data/implementation-evidence/ticket25-offline-model/candidate-config.json');bytes=3971L;sha256='ceb23fe9881584f1c2c5955497895a2a9bd6a0806888afe2a749750e22dee9e9'}
}
function DependencyPaths{
 foreach($d in @('backend/.venv','frontend/node_modules')){foreach($i in @(Walk (Join-Path $Root $d))){if($i.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Root dependency reparse requires separate exact guard'};$i.FullName}}
 'C:\Program Files\Google\Chrome\Application\chrome.exe'
}
function AddExpected($dict,$p,$bytes,$sha){
 $p=N $p;if((Private $p) -and -not(PublicAllowed $p)){throw "Unknown/private byte read forbidden: $p"}
 if($dict.ContainsKey($p)){
  $old=$dict[$p];if($null -ne $bytes -and $null -ne $old.bytes -and [long]$bytes -ne [long]$old.bytes){throw 'Conflicting historical length; owner must append current capture, retain old target'}
  if($sha -and $old.sha256 -and $sha -ne $old.sha256){throw 'Conflicting historical SHA; owner must retain historical target and provide explicit current-source disposition'}
  if($sha){$old.sha256=$sha};if($null -ne $bytes){$old.bytes=$bytes}
 }else{$dict.Add($p,[pscustomobject]@{path=$p;bytes=$bytes;sha256=$sha})}
}
function VerifyExpected($rows){foreach($r in $rows){$p=Proof $r.path;if($null -ne $r.bytes -and $p.bytes -ne [long]$r.bytes){throw "Length mismatch: $($r.path)"};if($r.sha256 -and $p.sha256 -ne $r.sha256){throw "SHA mismatch: $($r.path)"};$p}}
function PhysicalDisposition($t,$rel){
 foreach($d in @($t.release.physical_dependency_receipts)+@($t.release.disposable_cache_receipts)){
  if($null -eq $d){continue};$base=In $d.path $t.path
  if((Resolve $rel $t.path).StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)){
   if(-not $d.source_owner_receipt -or $d.kind -notin @('REPRODUCIBLE_INSTALLED_DEPENDENCY','DISPOSABLE_CACHE')){throw 'Physical dependency/cache source ownership unresolved'};return $true
  }
 };return $false
}
. (Join-Path $Out 'roll-cleanup-owner-boundary-v9.ps1')
. (Join-Path $Out 'roll-cleanup-bounded-verifier-v13.ps1')
$PreflightFile=Join-Path $Out 'roll-cleanup-batch-v6-preflight.json'
if($Phase -eq 'Preflight'){
 $process=FreshProcesses;$expected=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::OrdinalIgnoreCase)
 $runtime=@();$junctions=@();$exclusions=@();$snapshot=[Collections.Generic.List[object]]::new();$depPaths=@()
 $privateRetention=@(PrivatePreflightMetadata)
 foreach($t in $Trees){
  SourceGuard $t;$rows=@(Rows $t);$runtime+=$rows;$exc=@(Exclusions $t);$exclusions+=$exc; $excByPath=@{};foreach($entry in $exc){if($excByPath.ContainsKey($entry.path)){$excByPath[$entry.path]+=,$entry}else{$excByPath[$entry.path]=@($entry)}}
  foreach($d in @($t.metadata.manifests)+@($t.release.additional_manifests)){
   if($null -eq $d){continue};AddExpected $expected $d.path $d.manifest_bytes (GetProp $d 'manifest_sha256')
  }
  $coverage=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
  foreach($r in $rows){$null=$coverage.Add($r.source);AddExpected $expected $r.source (GetProp $r 'source_expected_bytes' $r.bytes) (GetProp $r 'source_expected_sha256' $r.sha256);AddExpected $expected $r.destination $r.bytes $r.sha256}
  $tracked=@(G $t.path @('-c','core.quotePath=false','ls-files'))
  $trackedSet=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase);foreach($f in $tracked){$null=$trackedSet.Add((N (Join-Path $t.path $f)))}
  foreach($i in @(Walk $t.path)){
   $p=In $i.FullName $t.path;$rel=[IO.Path]::GetRelativePath($t.path,$p).Replace('\','/')
   if($i.Attributes -band [IO.FileAttributes]::ReparsePoint){
    $decl=@($t.metadata.dependencies|Where-Object {$_.relative -eq $rel -and $_.kind -eq 'Junction'})+@($t.release.additional_junctions|Where-Object relative -eq $rel)
    if($decl.Count -ne 1 -or $i.LinkType -ne 'Junction'){throw "Unexpected reparse: $p"}
    $target=N ([string]$i.Target);$declTarget=N ([string]$decl[0].target)
    if($target -ne $declTarget -or $target -notin @((N (Join-Path $Root 'backend/.venv')),(N (Join-Path $Root 'frontend/node_modules')))){throw "Unexpected root dependency target: $p"}
    $junctions+=@{path=$p;target=N ([string]$i.Target)};continue
   }
   if($rel -eq '.git'){continue}
   $x=@(if($excByPath.ContainsKey($p)){$excByPath[$p]})
   if($x.Count -eq 1){$snapshot.Add((Stat $p));continue} # metadata only; no private read/hash/copy
   if((Private $p) -and -not(PublicAllowed $p)){throw "Unknown private file retained: $p"}
   if($coverage.Contains($p) -or $trackedSet.Contains($p)){$snapshot.Add((Stat $p));continue}
   if(PhysicalDisposition $t $rel){$snapshot.Add((Stat $p));continue}
   throw "Uncovered untracked file retained; require append preservation or exact owner disposition: $p"
  }
  # Include each accepted-source protected15 in byte guards; does not alter them.
  foreach($r in @(ProtectedRows|Select-Object -First 15)){AddExpected $expected (Join-Path $t.path ([IO.Path]::GetRelativePath($Root,$r.path))) $r.bytes $r.sha256}
 }
 foreach($r in @(ProtectedRows)){AddExpected $expected $r.path $r.bytes $r.sha256}
 foreach($r in @($Meta.retained_manifest_controls)){AddExpected $expected $r.path $r.bytes $r.sha256}
 # All independent run manifests are root/outside owned, never deletion targets.
 if(-not @($Release.independent_manifests).Count){throw 'Independent preservation union must be explicitly supplied; v2 four are insufficient for full batch'}
 foreach($d in @($Release.independent_manifests)){
  $p=Resolve $d.path $Root;AddExpected $expected $p $d.manifest_bytes $d.manifest_sha256
  $m=Read $p;$v=if($d.field -eq 'array'){@($m)}else{@($m.($d.field))}
  if($v.Count -ne $d.count){throw 'Independent manifest count changed'}
  foreach($r in $v){$rp=GetProp $r 'preserved' (GetProp $r 'destination' (GetProp $r 'path'));$dp=Resolve $rp $d.destination_base
   if(-not $dp.StartsWith((N $Root)+'\',[StringComparison]::OrdinalIgnoreCase)){$null=In $dp $Out}
   foreach($t in $Trees){if($dp.StartsWith($t.path+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Independent preserved target inside deletion scope'}}
   AddExpected $expected $dp $r.bytes $r.sha256
  }
 }
 # Manifest/acceptance source bytes and retained branches/root dependencies bound once.
 foreach($t in $Trees){AddExpected $expected $t.release.finite_acceptance_receipt $null $null}
 AddExpected $expected $ReleaseFile $null $null
 AddExpected $expected (Join-Path $Out 'roll-cleanup-owner-boundary-v9.ps1') $null $null
 AddExpected $expected (Join-Path $Out 'roll-cleanup-cwd-reader-v9.cs') $null $null
 AddExpected $expected $PSCommandPath $null $null # Bind this exact executor for preflight/execute/post continuity.
 AddExpected $expected (Join-Path $Out 'roll-cleanup-bounded-verifier-v13.ps1') $null $null; AddExpected $expected $PrivateFileIDHelper $null $null # Public metadata helper byte proof; never private bodies.
 $depPaths=@(DependencyPaths);foreach($p in $depPaths){AddExpected $expected $p $null $null}
 $proofs=@(VerifyExpectedParallel @($expected.Values) $PSCommandPath)
 # Manifest rows without SHA are self/mirror pairs; compare calculated identity after one sweep.
 $byPath=@{};foreach($p in $proofs){$byPath[$p.path]=$p}
 foreach($r in $runtime){if(-not $r.sha256 -and $byPath[$r.source].sha256 -ne $byPath[$r.destination].sha256){throw 'Root manifest mirror differs'}}
 $targets=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
 foreach($p in $proofs){$insideTree=$false;foreach($t in $Trees){if($p.path.StartsWith($t.path+'\',[StringComparison]::OrdinalIgnoreCase)){$insideTree=$true}};if(-not $insideTree){$null=$targets.Add($p.path)}}
 Save 'roll-cleanup-batch-v6-preflight.json' @{version=6;status='PREFLIGHT_PASS';created_utc=[datetime]::UtcNow.ToString('o');release_id=$Release.coordinator_release_id;root_head=$Release.root_head;trees=$Trees;proofs=$proofs;post_paths=@($targets);source_inventory=$snapshot;runtime=$runtime;junctions=$junctions;exact_private_exclusions=$exclusions;private_retention_moves=$privateRetention;root_dependency_paths=$depPaths;process=$process;hash_sweeps=1;sqlite_connections=0;none_deleted=$true}
 if($Managed.Count){Save 'roll-cleanup-batch-v6-managed-archive-queue.json' @{status='APP_ARCHIVE_REQUIRED';release_id=$Release.coordinator_release_id;items=@($Managed|Select-Object path,managed_identity,oid,branch);preflight=$PreflightFile;instruction='Coordinator uses archive_worktree exact identity, saves confirmed actual tool result in separate managed-lifecycle-receipts.json; no restore of old31 or native managed removal'}}
 return
}
$Before=Read $PreflightFile
foreach($name in @('roll-cleanup-owner-boundary-v9.ps1','roll-cleanup-cwd-reader-v9.cs','roll-cleanup-private-file-id-v10.cs','roll-cleanup-bounded-verifier-v13.ps1',(Split-Path -Leaf $PSCommandPath))){
 $helper=Join-Path $Out $name;$old=@($Before.proofs|Where-Object path -eq $helper);if($old.Count -ne 1){throw 'Bound helper missing from preflight'}
 $fresh=Proof $helper;if($fresh.sha256 -ne $old[0].sha256 -or $fresh.bytes -ne $old[0].bytes){throw 'Bound executor/helper changed; no operation'}
}
if($Before.status -ne 'PREFLIGHT_PASS' -or $Before.release_id -ne $Release.coordinator_release_id -or $Before.root_head -ne $Release.root_head){throw 'Mismatched preflight/release'}
if($Phase -eq 'Execute'){
 if(([datetime]::UtcNow-([datetime]$Before.created_utc)).TotalMinutes -gt 60){throw 'Preflight window expired; none deleted'}
 if($Managed.Count){
  $lifeFile=Join-Path $Out 'roll-cleanup-batch-v6-managed-lifecycle-receipts.json'
  if(-not(Test-Path -LiteralPath $lifeFile)){throw 'Run queued managed archive_worktree actions first and retain confirmed tool results; no native removal'}
  $life=Read $lifeFile
  foreach($t in @($Trees|Where-Object lifecycle -eq 'MANAGED_APP')){
   $matches=@($life|Where-Object {$_.release_id -eq $Release.coordinator_release_id -and (N $_.identity_key) -eq $t.path -and $_.confirmed_archived -eq $true -and $_.actual_tool_result_path})
   if($matches.Count -ne 1 -or (Test-Path -LiteralPath $t.path) -or -not(Test-Path -LiteralPath $matches[0].actual_tool_result_path)){throw 'Managed archive actual result/absence not established'}
  }
 }
 foreach($t in @($Trees|Where-Object lifecycle -eq 'UNMANAGED_GIT')){SourceGuard $t}
 $null=FreshProcesses
 # Cheap metadata continuity only; no second full byte hash sweep.
 foreach($r in @($Before.proofs)+@($Before.source_inventory)){
  $archivedSource=$false;foreach($t in @($Trees|Where-Object lifecycle -eq 'MANAGED_APP')){if($r.path.StartsWith($t.path+'\',[StringComparison]::OrdinalIgnoreCase)){$archivedSource=$true}}
  if($archivedSource){continue};$s=Stat $r.path;if($s.bytes -ne $r.bytes -or $s.mtime_ticks -ne $r.mtime_ticks){throw 'File metadata changed since preflight; none deleted'}
 }
 foreach($t in @($Trees|Where-Object lifecycle -eq 'UNMANAGED_GIT')){$now=@(Walk $t.path|Where-Object { -not($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -and (N $_.FullName) -ne (N (Join-Path $t.path '.git'))}|ForEach-Object {N $_.FullName}|Sort-Object);$old=@($Before.source_inventory|Where-Object {$_.path.StartsWith($t.path+'\',[StringComparison]::OrdinalIgnoreCase)}|ForEach-Object path|Sort-Object);if(($now -join "`n") -ne ($old -join "`n")){throw 'Source file set changed; none deleted'}}
 $retainedPrivateMetadata=@(MoveRetainedPrivateMetadata)
 foreach($j in $Before.junctions){$archived=$false;foreach($t in @($Trees|Where-Object lifecycle -eq 'MANAGED_APP')){if($j.path.StartsWith($t.path+'\',[StringComparison]::OrdinalIgnoreCase)){$archived=$true}};if($archived){continue};$i=Get-Item -LiteralPath ('\\?\'+$j.path) -Force;if($i.LinkType -ne 'Junction' -or (N ([string]$i.Target)) -ne $j.target){throw 'Junction changed'};[IO.Directory]::Delete(('\\?\'+$j.path),$false);if(Test-Path -LiteralPath $j.path){throw 'Unlink failed; stop'};if(-not(Test-Path -LiteralPath $j.target)){throw 'Root dependency target missing; stop'}}
 $removed=@()
 foreach($t in @($Trees|Where-Object lifecycle -eq 'UNMANAGED_GIT')){$null=In $t.path (Join-Path $Root '.scratch/worktrees');if(@(Walk $t.path|Where-Object {$_.Attributes -band [IO.FileAttributes]::ReparsePoint}).Count){throw 'Residual reparse; stop'}
  $v=@(& $Git -c core.longpaths=true -C $Root worktree remove --force -- $t.path 2>&1);$code=$LASTEXITCODE
  if($code -ne 0 -or (Test-Path -LiteralPath $t.path)){Save 'roll-cleanup-batch-v6-native-failure.json' @{path=$t.path;exit=$code;already_removed=$removed;output=$v};throw 'Exact native remove failed/residual; no recursive fallback'}
  $removed+=$t.path;$null=G $Root @('show-ref','--verify','refs/heads/'+$t.branch)
 }
 Save 'roll-cleanup-batch-v6-native-result.json' @{status='REMOVED_POST_PENDING';retained_private_metadata=$retainedPrivateMetadata;private_retention_receipt=$PrivateRetentionReceipt;removed=$removed;release_id=$Release.coordinator_release_id;branches_retained=$true;none_stopped=$true;hash_sweeps=1}
 return
}
if($Phase -eq 'Post'){
 $retainedPrivateMetadata=@(VerifyRetainedPrivateMetadata)
 $registry=@(G $Root @('worktree','list','--porcelain'))
 foreach($t in $Trees){if(Test-Path -LiteralPath $t.path){throw 'Target tree still exists'};if($registry -contains ('worktree '+$t.path.Replace('\','/'))){throw 'Target remains registered'};$null=G $Root @('show-ref','--verify','refs/heads/'+$t.branch)}
 $nowDeps=@(DependencyPaths|ForEach-Object {N $_}|Sort-Object);$oldDeps=@($Before.root_dependency_paths|ForEach-Object {N $_}|Sort-Object)
 if(($nowDeps -join "`n") -ne ($oldDeps -join "`n")){throw 'Root dependency file set changed'}
 $postSet=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase);foreach($p in $Before.post_paths){$null=$postSet.Add($p)}
 $post=@(VerifyExpectedParallel @($Before.proofs|Where-Object {$postSet.Contains($_.path)}) $PSCommandPath)
 Save 'roll-cleanup-batch-v6-post.json' @{status='PASS';root_head=$Release.root_head;release_id=$Release.coordinator_release_id;retained_private_metadata=$retainedPrivateMetadata;private_retention_receipt=$PrivateRetentionReceipt;retained_proofs=$post;root_protected15_allowed3_original19_unchanged=$true;root_dependency_file_set_bytes_unchanged=$true;all_preserved_targets_unchanged=$true;branches_retained=$true;no_process_stopped=$true;sqlite_connections=0;private_file_content_reads=0;hash_sweeps=2;actual_business_completion_not_changed=$true}
}
