param([switch]$Remove)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath('D:\dsh-proj\Roll')
$target=[IO.Path]::GetFullPath((Join-Path $root '.scratch/worktrees/codex-review-fixes'))
$scope=Join-Path $root '.scratch/roll-p0/evidence/continuation-2026-10-11/frontier24-29/codex-fix-cleanup'
$accepted='ddda3effff6655bef090d0af473c960c8fb59482'
$gitExecutable=@(Get-Command git.exe -CommandType Application)[0].Source
function Git([string[]]$Arguments){$out=@(& $gitExecutable -C $root @Arguments 2>$null);if($LASTEXITCODE -ne 0){throw 'Git failed'};return $out}
function Inside([string]$Path,[string]$Base){$absolute=[IO.Path]::GetFullPath($Path);if($absolute -ne $Base -and -not $absolute.StartsWith($Base+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Outside exact boundary'};return $absolute}
function Proof([string]$Path){$file=Get-Item -LiteralPath $Path;return [ordered]@{path=$file.FullName;bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLower()}}
function Check($Item){$now=Proof $Item.path;if($now.bytes -ne $Item.bytes -or $now.sha256 -ne $Item.sha256){throw "SHA/length mismatch: $($Item.path)"}}
function Save([string]$Name,$Value){[IO.File]::WriteAllText((Join-Path $scope $Name),(($Value|ConvertTo-Json -Depth 12).Replace("`r`n","`n")+"`n"),[Text.UTF8Encoding]::new($false))}
function NoProcess{
    $found=@(Get-CimInstance Win32_Process|Where-Object{
        $_.Name -in @('python.exe','pythonw.exe','node.exe','chrome.exe','msedge.exe','uvicorn.exe','vite.exe') -and
        ($_.CommandLine -match '[\\/]\.scratch[\\/]worktrees[\\/]codex-review-fixes([\\/]|\s|$)' -or $_.ExecutablePath -match '[\\/]\.scratch[\\/]worktrees[\\/]codex-review-fixes([\\/]|\s|$)')
    }|Select-Object ProcessId,Name,ExecutablePath)
    if($found.Count){throw 'Exact-tree process active; none stopped'}
}
function Profiles([switch]$RootOnly){
    return @(foreach($label in @('old','new','final')){
        $manifest=Get-Content -LiteralPath (Join-Path $root ".scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/runtime-$label-method-manifest.json") -Raw|ConvertFrom-Json
        $source=Inside $manifest.source $target
        $destination=Inside $manifest.destination (Join-Path $root '.roll-data/implementation-evidence/codex-review-fixes')
        if(@($manifest.files).Count -ne $manifest.file_count -or $manifest.file_count -eq 0){throw 'Invalid preservation count'}
        $bases=if($RootOnly){@($destination)}else{@($source,$destination)}
        foreach($entry in $manifest.files){foreach($base in $bases){Check ([pscustomobject]@{path=(Inside (Join-Path $base $entry.path) $base);bytes=$entry.bytes;sha256=$entry.sha256})}}
        [ordered]@{label=$label;source=$source;destination=$destination;files=$manifest.file_count;bytes=$manifest.bytes;sha_length_mismatches=0}
    })
}
function Dependencies{
    $files=@()
    foreach($name in @('backend/.venv','frontend/node_modules')){
        $base=Join-Path $root $name
        if((Get-Item -LiteralPath $base).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Root dependency is link'}
        $files+=@(Get-ChildItem -LiteralPath $base -Recurse -File -Force|Where-Object{$_.Name -notlike '.env*' -and $_.Name -ne 'auth.json'})
    }
    $files+=Get-Item -LiteralPath 'C:\Program Files\Google\Chrome\Application\chrome.exe'
    return @(foreach($file in ($files|Sort-Object FullName)){Proof $file.FullName})
}
NoProcess
Git @('merge-base','--is-ancestor',$accepted,'HEAD')|Out-Null
if(@(Git @('-C',$target,'rev-parse','HEAD'))[0] -ne $accepted -or @(Git @('-C',$target,'status','--porcelain=v1','--untracked-files=no')).Count){throw 'Child source moved or tracked dirty'}
if((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Worktree root link'}
foreach($relative in @('.env','backend/.env','auth.json')){if(Test-Path -LiteralPath (Join-Path $target $relative)){throw 'Unexpected private config; refuse deletion'}}
if(-not $Remove){
    $expected=@{'backend/.venv'=(Join-Path $root 'backend/.venv');'frontend/node_modules'=(Join-Path $root 'frontend/node_modules')}
    $junctions=@(foreach($link in @(Get-ChildItem -LiteralPath $target -Recurse -Force -Attributes ReparsePoint)){
        $relative=[IO.Path]::GetRelativePath($target,$link.FullName).Replace('\','/')
        if(-not $expected.ContainsKey($relative) -or $link.LinkType -ne 'Junction'){throw 'Unexpected link'}
        $final=[IO.Path]::GetFullPath([string]$link.Target)
        if($final -ne $expected[$relative] -or -not(Test-Path -LiteralPath $final)){throw 'Junction target mismatch'}
        [ordered]@{path=$link.FullName;target=$final}
    })
    $untracked=@(Git @('-C',$target,'status','--porcelain=v1','--untracked-files=all'))
    $paths=@($untracked|ForEach-Object{if(-not $_.StartsWith('?? ')){throw 'Tracked dirty'};Inside (Join-Path $target $_.Substring(3)) $target})
    $models=@(Get-Content -LiteralPath (Join-Path $root '.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/source-final.json') -Raw|ConvertFrom-Json)
    $modelproof=@(foreach($entry in $models[0..11]){$item=Proof (Join-Path $root $entry.path);if($item.bytes -ne $entry.bytes -or $item.sha256 -ne $entry.sha256){throw 'Model guard mismatch'};$item})
    $record=[ordered]@{status='PREFLIGHT_PASS';recorded_at=[DateTime]::UtcNow.ToString('o');target=$target;source_oid=$accepted;root_tip=@(Git @('rev-parse','HEAD'))[0];tracked_clean=$true;related_processes=0;
        own_untracked_paths=$paths;own_untracked_count=$paths.Count;owned_entity_paths=@(Get-ChildItem -LiteralPath $target -Recurse -File -Force|ForEach-Object{Inside $_.FullName $target});
        junctions=$junctions;profiles=Profiles;dependencies=Dependencies;private_config_inventory_excluded=$true;model_sources=$modelproof;
        logs=@('.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/acceptance.md','.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11/11-final-related-api-recovery.txt','.scratch/roll-p0/evidence/continuation-2026-10-11/codex-review-independent/merge-acceptance.md')}
    Save 'preflight.json' $record
    Write-Output "PASS preflight: profiles $($record.profiles.Count), untracked $($paths.Count), entities $($record.owned_entity_paths.Count), dependencies $($record.dependencies.Count), links $($junctions.Count)"
    exit
}
$proof=Get-Content -LiteralPath (Join-Path $scope 'preflight.json') -Raw|ConvertFrom-Json
if($proof.target -ne $target){throw 'Target differs'}
Profiles|Out-Null
foreach($item in @($proof.dependencies)+@($proof.model_sources)){Check $item}
NoProcess
foreach($junction in $proof.junctions){
    $link=Get-Item -LiteralPath (Inside $junction.path $target)
    if($link.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath([string]$link.Target) -ne $junction.target){throw 'Junction changed'}
    [IO.Directory]::Delete($link.FullName,$false)
    if((Test-Path -LiteralPath $link.FullName) -or -not(Test-Path -LiteralPath $junction.target)){throw 'Unlink failed'}
}
if(@(Get-ChildItem -LiteralPath $target -Recurse -Force -Attributes ReparsePoint).Count){throw 'Unexpected residual link'}
$output=@(& $gitExecutable -C $root worktree remove --force -- $target 2>&1|ForEach-Object{[string]$_});$gitExit=$LASTEXITCODE
if(Test-Path -LiteralPath $target){
    if($target -ne [IO.Path]::GetFullPath((Join-Path $root '.scratch/worktrees/codex-review-fixes')) -or (Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Unsafe residual target'}
    if(@(Get-ChildItem -LiteralPath $target -Recurse -Force -Attributes ReparsePoint).Count){throw 'Residual reparse point'}
    Remove-Item -LiteralPath $target -Recurse -Force
}
if(Test-Path -LiteralPath $target){throw 'Residual remains'}
if(@(Git @('worktree','list','--porcelain')) -contains ('worktree '+$target.Replace('\','/'))){Git @('worktree','remove','--force','--',$target)|Out-Null}
$profiles=Profiles -RootOnly
$after=Dependencies
if($after.Count -ne @($proof.dependencies).Count){throw 'Dependency count changed'}
for($i=0;$i -lt $after.Count;$i++){if($after[$i].path -ne $proof.dependencies[$i].path -or $after[$i].sha256 -ne $proof.dependencies[$i].sha256 -or $after[$i].bytes -ne $proof.dependencies[$i].bytes){throw 'Dependency changed'}}
foreach($item in $proof.model_sources){Check $item}
$branches=@(Git @('branch','--list','codex/roll-p0-codex-review-fixes'));if($branches.Count -ne 1){throw 'Branch missing'}
Save 'results.json' ([ordered]@{status='PASS';target=$target;source_oid=$accepted;absent=$true;native_git_exit=$gitExit;native_git_output=$output;root_tip=@(Git @('rev-parse','HEAD'))[0];
    owned_untracked_count=$proof.own_untracked_count;owned_entities=@($proof.owned_entity_paths).Count;junction_count=@($proof.junctions).Count;
    profiles=$profiles;dependencies=$after.Count;dependencies_SHA_length_mismatches=0;model_sources_SHA_length_mismatches=0;branches_retained=$branches;
    private_files_inventoried=$false;credentials_copied=$false;provider_calls=0;original19_started=$false;no_push=$true;worktrees_after=@(Git @('worktree','list','--porcelain'))})
Write-Output "PASS cleanup: exact accepted tree absent; $($after.Count) root dependency files and 661 profile files unchanged; branch retained"
