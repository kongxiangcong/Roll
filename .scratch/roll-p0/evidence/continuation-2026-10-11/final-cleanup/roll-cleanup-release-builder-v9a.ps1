# PREPARED ONLY. Never invokes cleanup. Run only in the coordinator's final window.
[CmdletBinding()]
param(
 [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$FinalRootHead,
 [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$Final31Oid,
 [Parameter(Mandatory)][string]$CoordinatorReleaseId,
 [Parameter(Mandatory)][string]$AppendixJson,
 [Parameter(Mandatory)][string]$Final31AppendixAcceptanceReceipt,
 [string]$Final31AcceptanceReceipt='D:\dsh-proj\Roll\.scratch\roll-p0\evidence\continuation-2026-10-11\ticket31-final-independent\acceptance.md',
 [string]$CandidateJson=(Join-Path $PSScriptRoot 'roll-cleanup-batch-v7-final31-root-candidate.json'),
 [string]$ProcessOwnerRecordsJson,
 [string]$AdditionalIndependentManifestsJson,
 [switch]$AllFinalAcceptancesReviewed,
 [switch]$AllTestsEndedAndOwnersStoppedOrExactOutside,
 [switch]$RootExecutionWindow
)
$ErrorActionPreference='Stop';Set-StrictMode -Version 3
$Out=$PSScriptRoot;$Root='D:\dsh-proj\Roll';$Tree=Join-Path $Root '.scratch\worktrees\ticket31-final'
function N($p){[IO.Path]::GetFullPath([string]$p).TrimEnd('\')}
function Within($p,$base){$p=N $p;$base=N $base;if($p -ne $base -and -not $p.StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)){throw "Outside exact boundary: $p"};$p}
function Prop($o,$k,$default=$null){if($null -ne $o -and $null -ne $o.PSObject.Properties[$k]){$o.$k}else{$default}}
function Read($p){Get-Content -LiteralPath ('\\?\'+(N $p)) -Raw|ConvertFrom-Json}
function Resolve($p,$base){if([IO.Path]::IsPathFullyQualified($p)){N $p}else{N (Join-Path $base $p)}}
function SaveNew($path,$o){$path=Within $path $Out;if(Test-Path -LiteralPath $path){throw 'Never overwrite an existing draft/release/control'};[IO.File]::WriteAllText($path,($o|ConvertTo-Json -Depth 40)+"`n",[Text.UTF8Encoding]::new($false));$path}
$Git=@(Get-Command git.exe -CommandType Application)[0].Source
function G($repo,[string[]]$a){$v=@(& $Git --no-optional-locks -c core.longpaths=true -C $repo @a 2>&1);if($LASTEXITCODE){throw ('Read-only Git gate failed: '+($a -join ' '))};$v}
function FileMetadata($p){$p=N $p;$par=[IO.Directory]::GetParent($p);while($par){$i=Get-Item -LiteralPath ('\\?\'+$par.FullName) -Force;if($i.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Control/receipt reparse ancestor'};$par=$par.Parent};$i=Get-Item -LiteralPath ('\\?\'+$p) -Force;if($i.PSIsContainer -or ($i.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Regular control/receipt file required'};$i}
function ControlProof($p){
 $p=N $p;$name=[IO.Path]::GetFileName($p)
 if($name -like '.env*' -or $name -in @('auth.json','method-auth.json','api.json','chatgpt.json','credentials.json','credential.json','secrets.json','channel.json','channel.lock') -or $p -match '\\notification-private\\'){throw 'Private body/hash prohibited'}
 if([IO.Path]::GetExtension($p) -ne '.json'){throw 'Metadata JSON controls only'}
 $allowed=$p.StartsWith((N $Out)+'\',[StringComparison]::OrdinalIgnoreCase) -or $p.StartsWith((Join-Path $Root '.scratch\roll-p0\evidence')+'\',[StringComparison]::OrdinalIgnoreCase)
 foreach($t in $C.trees){if($p.StartsWith((Join-Path $t.path '.scratch\roll-p0\evidence')+'\',[StringComparison]::OrdinalIgnoreCase)){$allowed=$true}}
 if(-not $allowed){throw 'Control path not in exact outside/owner/root evidence scope'}
 $i=FileMetadata $p;[pscustomobject]@{bytes=[long]$i.Length;sha256=(Get-FileHash -LiteralPath ('\\?\'+$p) -Algorithm SHA256).Hash.ToLowerInvariant()}
}
$ProofCache=@{}
function BindDescriptor($d){
 $p=Resolve $d.path $Root;if(-not $ProofCache.ContainsKey($p)){$ProofCache[$p]=ControlProof $p};$proof=$ProofCache[$p]
 $oldSha=Prop $d 'manifest_sha256';$oldBytes=Prop $d 'manifest_bytes'
 if($oldSha -and $oldSha -ne $proof.sha256){throw "Declared metadata control SHA changed: $p"}
 if($null -ne $oldBytes -and [long]$oldBytes -ne $proof.bytes){throw "Metadata control length changed: $p"}
 $d|Add-Member -NotePropertyName manifest_sha256 -NotePropertyValue $proof.sha256 -Force;$d|Add-Member -NotePropertyName manifest_bytes -NotePropertyValue $proof.bytes -Force
}
if(-not($RootExecutionWindow -and $AllFinalAcceptancesReviewed -and $AllTestsEndedAndOwnersStoppedOrExactOutside)){throw 'Explicit coordinator final-window/all-acceptances/all-tests-ended release required'}
$null=Within $CandidateJson $Out;$null=Within $AppendixJson $Out
$C=Read $CandidateJson;$M=Read (Join-Path $Out 'roll-cleanup-batch-v6-metadata.json')
if(@(G $Root @('rev-parse','HEAD'))[0] -ne $FinalRootHead){throw 'Final root HEAD differs'}
$null=G $Root @('diff','--cached','--quiet');$null=G $Root @('diff','--quiet') # occupied index / tracked dirty rejects
$Names=@($M.trees.name|Sort-Object);if(($Names -join '|') -ne (@($C.trees.name|Sort-Object) -join '|') -or @($C.trees).Count -ne 10){throw 'Exact ten-tree registry mismatch'}
$F=@($C.trees|Where-Object name -eq 'final31')[0];$F.oid=$Final31Oid;$F.accepted_final=$true
foreach($required in @('roll-cleanup-batch-v7-final31-normalized.json','roll-cleanup-batch-v7-final31-raw-controls.json')){if(@($F.additional_manifests|Where-Object {(N $_.path) -eq (N (Join-Path $Out $required))}).Count -ne 1){throw 'Candidate must retain initial31 normalized645/raw control descriptors'}}
$F.finite_acceptance_receipt=Within $Final31AcceptanceReceipt $Root
$null=FileMetadata $F.finite_acceptance_receipt
$null=FileMetadata (Within $Final31AppendixAcceptanceReceipt $Root)
$F|Add-Member -NotePropertyName appendix_acceptance_receipt -NotePropertyValue (N $Final31AppendixAcceptanceReceipt) -Force
foreach($t in $C.trees){
 $meta=@($M.trees|Where-Object name -eq $t.name)[0]
 if((N $t.path) -ne (N $meta.path) -or $t.lifecycle -ne 'UNMANAGED_GIT'){throw 'Exact tree identity/lifecycle changed'}
 $null=Within $t.path (Join-Path $Root '.scratch\worktrees')
 if($meta.expected_accepted_oid -and $meta.expected_accepted_oid -ne $t.oid){throw 'Old accepted source OID changed'}
 if($t.accepted_final -ne $true -or $t.oid -notmatch '^[0-9a-f]{40}$'){throw 'No inferred acceptance for pending tree'}
 $null=FileMetadata (Within $t.finite_acceptance_receipt $Root)
 if(@(G $t.path @('rev-parse','HEAD'))[0] -ne $t.oid -or @(G $t.path @('branch','--show-current'))[0] -ne $t.branch){throw 'Exact accepted branch/head changed'}
 $null=G $Root @('merge-base','--is-ancestor',$t.oid,$FinalRootHead)
 if(@(G $t.path @('status','--porcelain=v1','--untracked-files=no')).Count){throw 'Source tracked/index dirty'}
}
# Appendix is a finite caller-reviewed array. No endpoint is opened or hashed.
# Each item: path, field, count, bytes, relative_paths, source_base,
# destination_base, raw_root_mirror, raw_saved_manifest, raw_sha256, raw_bytes.
$A=@(Read $AppendixJson);if(-not $A.Count){throw 'Current no-trade ON_DEMAND/POST_CLOSE appendix descriptor missing'}
$tag=[guid]::NewGuid().ToString('N');$newControls=@();$ordinal=0
foreach($a in $A){
 $ordinal++;$raw=Within $a.path (Join-Path $Tree '.scratch\roll-p0\evidence');$proof=ControlProof $raw
 if($proof.sha256 -ne $a.raw_sha256 -or $proof.bytes -ne [long]$a.raw_bytes){throw 'Appendix raw metadata proof differs'}
 $manifest=Read $raw;$values=@($manifest.($a.field))
 if($values.Count -ne $a.count -or ($values|Measure-Object bytes -Sum).Sum -ne $a.bytes){throw 'Appendix metadata count/bytes changed'}
 $sourceBase=Within $a.source_base $Tree;$destBase=Within $a.destination_base (Join-Path $Root '.roll-data\implementation-evidence')
 $rows=@(foreach($r in $values){
  if($a.relative_paths){$part=[string]$r.path;if([IO.Path]::IsPathRooted($part) -or ($part -split '[\\/]') -contains '..'){throw 'Unsafe appendix relative path'};$s=Join-Path $sourceBase $part;$d=Join-Path $destBase $part}
  else{$s=Resolve $r.source $sourceBase;$dp=Prop $r 'destination' (Prop $r 'preserved' (Prop $r 'target'));if(-not $dp){throw 'Unsupported appendix destination field'};$d=Resolve $dp $destBase}
  $s=Within $s $Tree;$d=Within $d $destBase
  if($r.sha256 -notmatch '^[0-9a-f]{64}$' -or [long]$r.bytes -lt 0){throw 'Invalid appendix declared byte proof'}
  [pscustomobject]@{source=$s;destination=$d;bytes=[long]$r.bytes;sha256=$r.sha256}
 })
 $rawMirror=Within $a.raw_root_mirror (Join-Path $Root '.scratch\roll-p0\evidence')
 $rawSaved=Within $a.raw_saved_manifest $destBase
 $rows+=@([pscustomobject]@{source=$raw;destination=$rawSaved;bytes=$proof.bytes;sha256=$proof.sha256})
 $control=Join-Path $Out ("roll-cleanup-release-$tag-appendix-$ordinal.json")
 $null=SaveNew $control ([ordered]@{source_manifest=$raw;rows=$rows;root_control_rows=@([ordered]@{destination=$rawMirror;bytes=$proof.bytes;sha256=$proof.sha256},[ordered]@{destination=$rawSaved;bytes=$proof.bytes;sha256=$proof.sha256});runtime_bodies_read=0})
 $newControls+=$control
 $F.additional_manifests+=@([pscustomobject]@{path=$control;field='rows';root_mirror=$null;source_base=$Tree;destination_base=$Root;special='';count=$rows.Count;bytes=($rows|Measure-Object bytes -Sum).Sum;manifest_bytes=$null;manifest_sha256=$null;self_copy=$null})
 $C.independent_manifests+=@([pscustomobject]@{path=$control;field='root_control_rows';count=2;destination_base=$Root;manifest_bytes=$null;manifest_sha256=$null})
}
if($AdditionalIndependentManifestsJson){$null=Within $AdditionalIndependentManifestsJson $Out;$C.independent_manifests+=@(Read $AdditionalIndependentManifestsJson)}
if($ProcessOwnerRecordsJson){$null=Within $ProcessOwnerRecordsJson $Out;$C.process_owner_records=@(Read $ProcessOwnerRecordsJson)}
foreach($r in $C.process_owner_records){
 if($r.disposition -ne 'OUTSIDE_DELETION_SCOPE' -or $r.name -notmatch '^(pythonw?|node)(\.exe)?$' -or -not [IO.Path]::IsPathFullyQualified($r.executable_path) -or (N $r.executable_path).StartsWith($Root+'\',[StringComparison]::OrdinalIgnoreCase) -or -not $r.parent_process_id -or -not $r.creation_date_utc){throw 'Outside owner record lacks concrete identity'}
 $proof=$r.source_owner_proof
 if($proof.command_kind -notin @('EXACT_ABSOLUTE_PUBLIC_DAEMON_PATH','EXACT_RELATIVE_MODULE_OUTSIDE_WITH_CWD') -or -not [IO.Path]::IsPathFullyQualified($proof.expected_public_argument_path) -or (N $proof.expected_public_argument_path).StartsWith($Root+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Public daemon argument provenance required; no relative argv guesses'}
 if($proof.command_kind -eq 'EXACT_RELATIVE_MODULE_OUTSIDE_WITH_CWD'){
  if(-not [IO.Path]::IsPathFullyQualified($proof.expected_cwd) -or (N $proof.expected_cwd).StartsWith($Root+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Relative module needs exact outside CWD'}
  $null=FileMetadata (Within $proof.coordinator_boundary_receipt $Out)
 }
 $null=FileMetadata (Within $r.source_receipt $Out);$null=FileMetadata (Within $proof.public_daemon_provenance $Out)
}
# Preserve all exact public METHOD and private metadata dispositions from base.
if(@(($C.trees|Where-Object name -eq 'codex-runner-scope').public_fixture_allow).Count -ne 18){throw 'Exact parent fixture count changed'}
foreach($t in $C.trees){foreach($d in @($t.additional_manifests)){if($null -ne $d){BindDescriptor $d}}}
foreach($d in $C.independent_manifests){BindDescriptor $d}
# Do not silently replace conflicting historical source identities with newest.
$seen=@{}
foreach($d in $F.additional_manifests){$x=Read $d.path;foreach($r in @($x.($d.field))){$key=N $r.source;if($seen.ContainsKey($key) -and ($seen[$key].sha256 -ne $r.sha256 -or $seen[$key].bytes -ne $r.bytes)){throw 'Conflicting original/new appendix source; retain historical target and require explicit owner disposition'};$seen[$key]=$r}}
$C.version='V9_COORDINATOR_RELEASE_BUILT';$C.root_head=$FinalRootHead;$C.coordinator_release_id=$CoordinatorReleaseId
foreach($k in @('final29_accepted','ninth30_accepted','final31_accepted','final_review_accepted','root_dependency_baseline_after_all_tests','all_test_processes_stopped_or_exact_outside_owned')){$C.$k=$true}
$C.root_candidate_only_not_released=$false
$C|Add-Member -NotePropertyName root_baseline_state -NotePropertyValue 'PREFLIGHT_PENDING_AFTER_ALL_TESTS; builder did not capture dependencies/cache' -Force
$C|Add-Member -NotePropertyName release_builder_note -NotePropertyValue 'Explicit coordinator release; metadata JSON controls hashed only; no runtime/private bodies/SQLite/CIM/process stop/Git mutation/cleanup.' -Force
$C|Add-Member -NotePropertyName final31_appendix_acceptance_receipt -NotePropertyValue (N $Final31AppendixAcceptanceReceipt) -Force
$path=Join-Path $Out ("roll-cleanup-release-$tag.json");$null=SaveNew $path $C
[pscustomobject]@{release=$path;new_appendix_controls=$newControls;metadata_control_hashes=$ProofCache.Count;runtime_hashes=0;baseline_captured=$false;preflight_run=$false;deleted=0}
