param([switch]$Remove)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath('D:\dsh-proj\Roll')
$scope=Join-Path $root '.scratch/roll-p0/evidence/continuation-2026-10-11/review-fixes'
$target=[IO.Path]::GetFullPath((Join-Path $root '.scratch/worktrees/continuation-review-fixes'))
$accepted='581aa21ff3f78e36d8912a89c72714225ea7af4a'
$gitExecutable=@(Get-Command git.exe -CommandType Application)[0].Source
function Git([string[]]$Arguments){$output=@(& $gitExecutable -C $root @Arguments 2>$null);if($LASTEXITCODE -ne 0){throw 'Git operation failed'};return $output}
function Inside([string]$Path,[string]$Base){$absolute=[IO.Path]::GetFullPath($Path);if($absolute -ne $Base -and -not $absolute.StartsWith($Base+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Path outside exact boundary'};return $absolute}
function Proof([string]$Path){$file=Get-Item -LiteralPath $Path;return [ordered]@{path=$file.FullName;bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLower()}}
function Check($Item){$now=Proof $Item.path;if($now.bytes -ne $Item.bytes -or $now.sha256 -ne $Item.sha256.ToLower()){throw "SHA/length mismatch: $($Item.path)"}}
function Save([string]$Name,$Value){[IO.File]::WriteAllText((Join-Path $scope $Name),(($Value|ConvertTo-Json -Depth 12).Replace("`r`n","`n")+"`n"),[Text.UTF8Encoding]::new($false))}
function NoProcess{
    $found=@(Get-CimInstance Win32_Process|Where-Object{
        $_.Name -in @('python.exe','pythonw.exe','node.exe','chrome.exe','msedge.exe','uvicorn.exe','vite.exe') -and
        ($_.CommandLine -match '[\\/]\.scratch[\\/]worktrees[\\/]continuation-review-fixes([\\/]|\s|$)' -or $_.ExecutablePath -match '[\\/]\.scratch[\\/]worktrees[\\/]continuation-review-fixes([\\/]|\s|$)')
    }|Select-Object ProcessId,Name,ExecutablePath)
    if($found.Count){throw 'Exact-tree active process found; none stopped'}
}
function Profiles([switch]$RootOnly){
    $final=Get-Content -LiteralPath (Join-Path $scope 'cleanup-source-final-preservation.json') -Raw|ConvertFrom-Json
    if($final.status -ne 'PASS'){throw 'Final-state preservation proof missing'}
    $records=@(foreach($name in @('runtime-manifest.json','runtime-failed-forward-manifest.json','runtime-new-method-manifest.json','runtime-new-forward-endpoint-manifest.json')){
        $manifest=Get-Content -LiteralPath (Join-Path $scope $name) -Raw|ConvertFrom-Json
        $source=Inside $manifest.source $target
        $destination=Inside $manifest.destination (Join-Path $root '.roll-data/implementation-evidence/continuation-review-fixes')
        if(@($manifest.files).Count -ne $manifest.file_count -or $manifest.file_count -eq 0){throw 'Invalid required preservation manifest'}
        $sourceReused=@($final.source_final_state_copies|Where-Object{$_.source -eq $source}).Count -eq 1
        $bases=if($RootOnly -or $sourceReused){@($destination)}else{@($source,$destination)}
        foreach($entry in $manifest.files){foreach($base in $bases){$path=Inside (Join-Path $base $entry.path) $base;Check ([pscustomobject]@{path=$path;bytes=$entry.bytes;sha256=$entry.sha256})}}
        [ordered]@{manifest=$name;source=$source;destination=$destination;file_count=$manifest.file_count;bytes=$manifest.bytes;historical_root_SHA_length_matches=$true;source_reused_and_preserved_separately=$sourceReused}
    })
    foreach($snapshot in $final.source_final_state_copies){
        $source=Inside $snapshot.source $target
        $destination=Inside $snapshot.destination (Join-Path $root '.roll-data/implementation-evidence/continuation-review-fixes/source-final-state')
        $bases=if($RootOnly){@($destination)}else{@($source,$destination)}
        foreach($entry in $snapshot.files){foreach($base in $bases){Check ([pscustomobject]@{path=(Inside (Join-Path $base $entry.path) $base);bytes=$entry.bytes;sha256=$entry.sha256})}}
        if(@($snapshot.files).Count -ne $snapshot.file_count){throw 'Final source file count mismatch'}
        $records+=@([ordered]@{manifest='cleanup-source-final-preservation.json';source=$source;destination=$destination;file_count=$snapshot.file_count;bytes=$snapshot.bytes;source_final_SHA_length_matches=$true;historical_timepoint=$false})
    }
    return $records
}
function Dependencies{
    $files=@(Get-Item -LiteralPath (Join-Path $root '.env'))
    foreach($name in @('backend/.venv','frontend/node_modules')){
        $base=Join-Path $root $name;if((Get-Item -LiteralPath $base).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Root dependency is link'}
        $files+=@(Get-ChildItem -LiteralPath $base -Recurse -File -Force)
    }
    $files+=Get-Item -LiteralPath 'C:\Program Files\Google\Chrome\Application\chrome.exe'
    return @(foreach($file in ($files|Sort-Object FullName)){Proof $file.FullName})
}
NoProcess
Git @('merge-base','--is-ancestor',$accepted,'HEAD')|Out-Null
if(@(Git @('diff','--name-only')).Count -or @(Git @('diff','--cached','--name-only')).Count){throw 'Root tracked state dirty'}
if(-not $Remove){
    if((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Worktree root is link'}
    if(@(Git @('-C',$target,'rev-parse','HEAD'))[0] -ne $accepted){throw 'Unexpected final source HEAD'}
    $status=@(Git @('-C',$target,'status','--porcelain=v1','--untracked-files=all'))
    if(@($status|Where-Object{-not $_.StartsWith('?? ')}).Count){throw 'Tracked tree dirty'}
    foreach($relative in @('.env','backend/.env')){if(Test-Path -LiteralPath (Join-Path $target $relative)){throw 'Unexpected own-tree credential config; do not remove'}}
    $expected=@{'backend/.venv'=(Join-Path $root 'backend/.venv');'frontend/node_modules'=(Join-Path $root 'frontend/node_modules')}
    $junctions=@(foreach($link in @(Get-ChildItem -LiteralPath $target -Recurse -Force -Attributes ReparsePoint)){
        $relative=[IO.Path]::GetRelativePath($target,$link.FullName).Replace('\','/')
        if(-not $expected.ContainsKey($relative) -or $link.LinkType -ne 'Junction'){throw 'Unexpected link'}
        $final=[IO.Path]::GetFullPath([string]$link.Target)
        if($final -ne $expected[$relative] -or -not(Test-Path -LiteralPath $final)){throw 'Junction final target mismatch'}
        [ordered]@{path=$link.FullName;target=$final}
    })
    $record=[ordered]@{status='PREFLIGHT_PASS';root_tip=@(Git @('rev-parse','HEAD'))[0];source_head=$accepted;target=$target;tracked_clean=$true;related_processes=0;
        own_untracked_paths=@($status|ForEach-Object{Inside (Join-Path $target $_.Substring(3)) $target});
        owned_entity_file_paths=@(Get-ChildItem -LiteralPath $target -Recurse -File -Force|ForEach-Object{Inside $_.FullName $target});
        junctions=$junctions;profiles=Profiles;dependencies=Dependencies;model_sources=@();protected_paths=@();
        logs=@('acceptance.md','14-final-related-with-recovery.txt','independent-acceptance.md','actual-corrected-successor-results.json')}
    $baseline=Get-Content -LiteralPath (Join-Path $scope '../upstream19-before20.json') -Raw|ConvertFrom-Json
    foreach($entry in $baseline){$item=Proof (Join-Path $root $entry.path);if($item.bytes -ne $entry.bytes -or $item.sha256 -ne $entry.sha256.ToLower()){throw 'Model source changed'};$record.model_sources+=@($item)}
    foreach($name in @('.scratch/local-commit-20261011','.scratch/roll-p0/evidence/19-reconstruction-2026-10-10/negative-real-integrity/.startup.lock','.scratch/roll-p0/evidence/19-reconstruction-2026-10-10/negative-real-integrity/backups','.workbuddy','.roll-data/reconstructed19-v1','.roll-data/implementation-evidence/21','.roll-data/implementation-evidence/23','.roll-data/implementation-evidence/continuation-review-fixes/actual-corrected-copy','.roll-data/implementation-evidence/continuation-review-fixes/provider-approval-current')){
        $path=Join-Path $root $name;if(-not(Test-Path -LiteralPath $path)){throw 'Protected path missing'};$record.protected_paths+=@($path)
    }
    Save 'cleanup-solefix-preflight.json' $record
    Write-Output "PASS preflight: owned untracked $($record.own_untracked_paths.Count), entities $($record.owned_entity_file_paths.Count), required profiles $($record.profiles.Count), dependencies $($record.dependencies.Count), junctions $($junctions.Count)"
    exit
}
$proof=Get-Content -LiteralPath (Join-Path $scope 'cleanup-solefix-preflight.json') -Raw|ConvertFrom-Json
if([IO.Path]::GetFullPath($proof.target) -ne $target){throw 'Removal target mismatch'}
if(@(Git @('-C',$target,'rev-parse','HEAD'))[0] -ne $accepted -or @(Git @('-C',$target,'status','--porcelain=v1','--untracked-files=no')).Count){throw 'Source changed'}
Profiles|Out-Null
foreach($item in @($proof.dependencies)+@($proof.model_sources)){Check $item}
NoProcess
foreach($junction in $proof.junctions){
    $link=Get-Item -LiteralPath (Inside $junction.path $target)
    if($link.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath([string]$link.Target) -ne $junction.target){throw 'Junction changed'}
    [IO.Directory]::Delete($link.FullName,$false)
    if((Test-Path -LiteralPath $link.FullName) -or -not(Test-Path -LiteralPath $junction.target)){throw 'Junction unlink/root target failure'}
}
if(@(Get-ChildItem -LiteralPath $target -Recurse -Force -Attributes ReparsePoint).Count){throw 'Remaining link blocks recursive removal'}
$output=@(& $gitExecutable -C $root worktree remove --force -- $target 2>&1|ForEach-Object{[string]$_});$gitExit=$LASTEXITCODE
if(Test-Path -LiteralPath $target){
    if($target -ne [IO.Path]::GetFullPath((Join-Path $root '.scratch/worktrees/continuation-review-fixes')) -or (Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Unsafe residual target'}
    if(@(Get-ChildItem -LiteralPath $target -Recurse -Force -Attributes ReparsePoint).Count){throw 'Residual link'}
    Remove-Item -LiteralPath $target -Recurse -Force
}
if(Test-Path -LiteralPath $target){throw 'Worktree residual exists'}
if(@(Git @('worktree','list','--porcelain')) -contains ('worktree '+$target.Replace('\','/'))){Git @('worktree','remove','--force','--',$target)|Out-Null}
$profiles=Profiles -RootOnly
$after=Dependencies
if($after.Count -ne @($proof.dependencies).Count){throw 'Root dependency count changed'}
for($index=0;$index -lt $after.Count;$index++){if($after[$index].path -ne $proof.dependencies[$index].path -or $after[$index].sha256 -ne $proof.dependencies[$index].sha256 -or $after[$index].bytes -ne $proof.dependencies[$index].bytes){throw 'Root dependency changed'}}
foreach($item in $proof.model_sources){Check $item}
foreach($path in $proof.protected_paths){if(-not(Test-Path -LiteralPath $path)){throw 'Protected path removed'}}
$branches=@(Git @('branch','--list','codex/roll-p0-continuation-review-fixes'));if($branches.Count -ne 1){throw 'Fix branch missing'}
Save 'cleanup-solefix-results.json' ([ordered]@{status='PASS';target=$target;source_head=$accepted;absent=$true;native_git_exit=$gitExit;native_git_output=$output;
    owned_untracked_count=@($proof.own_untracked_paths).Count;owned_entities=@($proof.owned_entity_file_paths).Count;
    junction_count=@($proof.junctions).Count;unlink_method='Directory.Delete(link,false) only after exact root target verification; no links observed means no unlink';
    required_root_profiles=$profiles;dependency_files=$after.Count;dependencies_SHA_length_unchanged=$true;model_dependencies_unchanged=$true;
    protected_paths_present=$proof.protected_paths;branches_retained=$branches;worktrees_after=@(Git @('worktree','list','--porcelain'));
    credentials_copied=$false;provider_calls=0;original19_started=$false;tracker_unchanged=$true;no_push=$true})
Write-Output "PASS cleanup: exact solefix absent, $($after.Count) root dependency files and required root profiles unchanged; branch retained"
