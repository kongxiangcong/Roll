# PREPARED ONLY. Explicit post-all-tests observer; no process stop or cleanup.
[CmdletBinding()]
param([Parameter(Mandatory)][string]$ApprovedOutsideOwnersJson,
 [string]$CandidateJson=(Join-Path $PSScriptRoot 'roll-cleanup-batch-v7-final31-root-candidate.json'),
 [switch]$AllTestsEnded,[switch]$RootExecutionWindow)
$ErrorActionPreference='Stop';Set-StrictMode -Version 3
if(-not($AllTestsEnded -and $RootExecutionWindow)){throw 'Post-all-tests coordinator window required'}
$Root='D:\dsh-proj\Roll';$Out=$PSScriptRoot
function N($p){[IO.Path]::GetFullPath([string]$p).TrimEnd('\')}
function Inside($p,$b){$p=N $p;$b=N $b;$p -eq $b -or $p.StartsWith($b+'\',[StringComparison]::OrdinalIgnoreCase)}
function Read($p){if(-not(Inside $p $Out)){throw 'Outside control JSON required'};Get-Content -LiteralPath $p -Raw|ConvertFrom-Json}
function PathMention($cmd,$path){$cmd -match ([regex]::Escape((N $path))+'(?=\\|\s|["'']|$)')}
function PublicArgumentMatch($cmd,$path){$cmd -match ('(?:^|\s|["''])'+[regex]::Escape((N $path))+'(?=$|\s|["''])')}
$C=Read $CandidateJson;$Approved=@(Read $ApprovedOutsideOwnersJson)
. (Join-Path $Out 'roll-cleanup-owner-boundary-v9.ps1')
$Observation=@();$Records=@();$Blocked=@()
# CommandLine is used only for exact internal path comparisons. Never written,
# returned, interpolated in an error, or included in saved process evidence.
$All=@(Get-CimInstance Win32_Process -ErrorAction Stop)
foreach($p in $All){
 $cmd=([string]$p.CommandLine).Replace('/','\');$exe=([string]$p.ExecutablePath).Replace('/','\')
 $source=$false;foreach($t in $C.trees){if(($exe -and (Inside $exe $t.path)) -or (PathMention $cmd $t.path)){$source=$true}}
 $rootShared=($exe -and (Inside $exe $Root)) -or (PathMention $cmd $Root)
 if(-not($source -or $rootShared -or $p.Name -match '^(pythonw?|node)(\.exe)?$')){continue}
 $date=([datetime]$p.CreationDate).ToUniversalTime().ToString('o')
 $m=@($Approved|Where-Object {[int]$_.pid -eq [int]$p.ProcessId -and ([datetime]$_.creation_date_utc).ToUniversalTime().ToString('o') -eq $date})
 $ok=$false;$why='UNKNOWN_OWNER_BLOCKED';$publicArg=$null;$receipt=$null;$publicProof=$null
 if($source){$why='EXACT_DELETE_SOURCE_LIVE_BLOCKED'}
 elseif($rootShared){$why='ROOT_OR_SHARED_SOURCE_USAGE_BLOCKED'}
 elseif(-not $exe){$why='EXECUTABLE_UNAVAILABLE_BLOCKED'}
 elseif($m.Count -eq 1){
  $r=$m[0];$proof=$r.source_owner_proof
  $publicArg=N $proof.expected_public_argument_path;$receipt=N $r.source_receipt;$publicProof=N $proof.public_daemon_provenance
  if([IO.Path]::IsPathFullyQualified($r.executable_path) -and [IO.Path]::IsPathFullyQualified($proof.expected_public_argument_path) -and (N $exe) -eq (N $r.executable_path) -and $p.Name -eq $r.name -and [int]$p.ParentProcessId -eq [int]$r.parent_process_id -and $r.disposition -eq 'OUTSIDE_DELETION_SCOPE' -and $proof.command_kind -in @('EXACT_ABSOLUTE_PUBLIC_DAEMON_PATH','EXACT_RELATIVE_MODULE_OUTSIDE_WITH_CWD') -and -not(Inside $publicArg $Root) -and (ExactOutsideBoundary $p $r $All) -and (Inside $receipt $Out) -and (Inside $publicProof $Out) -and (Test-Path -LiteralPath $receipt) -and (Test-Path -LiteralPath $publicProof)){$ok=$true;$why='EXACT_PUBLIC_DAEMON_OUTSIDE_PROVEN';$Records+=$r}
  else{$why='SUPPLIED_OWNER_PROOF_MISMATCH_BLOCKED'}
 }
 $row=[pscustomobject]@{name=$p.Name;executable_path=$exe;pid=[int]$p.ProcessId;creation_date_utc=$date;parent_process_id=[int]$p.ParentProcessId;delete_source_usage=$source;root_shared_usage=$rootShared;outside_proven=$ok;unknown_owner=(-not $ok);reason=$why;source_receipt=$receipt;public_daemon_provenance=$publicProof;matched_public_argument_path=$publicArg;command_line_saved=$false}
 $Observation+=$row;if(-not $ok){$Blocked+=$row}
}
$after=@(Get-CimInstance Win32_Process -ErrorAction Stop)
foreach($r in $Records){$live=@($after|Where-Object {[int]$_.ProcessId -eq [int]$r.pid});if($live.Count -ne 1 -or -not(ProcessIdentityMatch $live[0] $r)){throw 'Outside process identity changed after bounded proof; no release'}}
$tag=[guid]::NewGuid().ToString('N');$recordPath=Join-Path $Out ("roll-cleanup-v9-process-owners-$tag.json");$obsPath=Join-Path $Out ("roll-cleanup-v9-process-observation-$tag.json")
[IO.File]::WriteAllText($recordPath,($Records|ConvertTo-Json -Depth 20 -AsArray)+"`n",[Text.UTF8Encoding]::new($false))
$result=[ordered]@{state=if($Blocked.Count){'UNKNOWN_OR_SOURCE_OWNER_BLOCKED'}else{'FINITE_CANDIDATE_OWNERS_PROVEN'};queried_utc=[datetime]::UtcNow.ToString('o');candidates=$Observation;blocked=$Blocked;approved_records_file=$recordPath;processes_stopped=0;command_lines_saved=0;private_bodies_read=0;hashes_computed=0;sqlite_connections=0;baseline=$false}
[IO.File]::WriteAllText($obsPath,($result|ConvertTo-Json -Depth 20)+"`n",[Text.UTF8Encoding]::new($false))
[pscustomobject]@{state=$result.state;observation=$obsPath;approved_records=$recordPath;blocked=$Blocked.Count;none_stopped=$true}
