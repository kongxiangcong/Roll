$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath('D:\dsh-proj\Roll')
$gitExecutable=@(Get-Command git.exe -CommandType Application)[0].Source
$receipt=Join-Path $root '.scratch/roll-p0/evidence/continuation-2026-10-11'
$proof=Get-Content -LiteralPath (Join-Path $receipt 'cleanup20-21-preflight.json') -Raw|ConvertFrom-Json
function AssertFile($value){
    $item=Get-Item -LiteralPath $value.path
    if($item.Length -ne $value.bytes -or (Get-FileHash -LiteralPath $item.FullName).Hash -ne $value.sha256){throw "Saved file changed: $($value.path)"}
}
foreach($f in @($proof.root_tools_before)+@($proof.upstream19)+@($proof.actual_current_archives)){AssertFile $f}
$processes=@(Get-CimInstance Win32_Process|Where-Object{$_.Name -in @('python.exe','pythonw.exe','node.exe','chrome.exe','uvicorn.exe','vite.exe') -and ($_.CommandLine -match '[\\/]\.scratch[\\/]worktrees[\\/]ticket(20|21)([\\/]|\s|$)' -or $_.ExecutablePath -match '[\\/]\.scratch[\\/]worktrees[\\/]ticket(20|21)([\\/]|\s|$)')}|Select-Object ProcessId,Name,ExecutablePath)
if($processes.Count){throw 'Related process still alive; none stopped'}
foreach($tree in $proof.worktrees){
    $path=[IO.Path]::GetFullPath($tree.path)
    if($path -notin @((Join-Path $root '.scratch/worktrees/ticket20'),(Join-Path $root '.scratch/worktrees/ticket21'))){throw 'Outside exact authorized worktrees'}
    if(Test-Path -LiteralPath $path){
        if((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Worktree root became a reparse point'}
        foreach($junction in $tree.junctions){
            if(Test-Path -LiteralPath $junction.path){
                $link=Get-Item -LiteralPath $junction.path
                if($link.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath([string]$link.Target) -ne $junction.target){throw 'Junction target changed'}
                [IO.Directory]::Delete($junction.path,$false)
            }
            if(-not(Test-Path -LiteralPath $junction.target)){throw 'Root dependency target missing'}
        }
        if(@(Get-ChildItem -LiteralPath $path -Recurse -Force -Attributes ReparsePoint).Count){throw 'Unexpected remaining reparse point'}
        # Paths are native, literal and constrained above; no other shell receives them.
        Remove-Item -LiteralPath $path -Recurse -Force
        if(Test-Path -LiteralPath $path){throw 'Residual worktree files remain'}
    }
    $registered=@(& $gitExecutable -C $root worktree list --porcelain)
    $registration='worktree '+$path.Replace('\','/')
    if($registered -contains $registration){
        & $gitExecutable -C $root worktree remove --force -- $path
        if($LASTEXITCODE -ne 0){throw 'Cannot remove exact worktree registration'}
    }
}
$rootProfiles=@()
foreach($record in $proof.preserved_profiles){
    $m=Get-Content -LiteralPath (Join-Path $root $record.manifest) -Raw|ConvertFrom-Json
    $entries=if($m.entries){@($m.entries)}else{@($m.files)}
    $destination=if($m.destination){$m.destination}elseif($m.directory){$m.directory}else{$m.profile}
    foreach($e in $entries){AssertFile ([pscustomobject]@{path=(Join-Path $destination $e.path);bytes=$e.bytes;sha256=$e.sha256})}
    if(@(Get-ChildItem -LiteralPath $destination -Recurse -File -Force).Count -ne $entries.Count){throw 'Root profile count changed'}
    $rootProfiles+=@([ordered]@{path=$destination;files=$entries.Count;sha_and_length_matches=$true})
}
foreach($f in @($proof.root_tools_before)+@($proof.upstream19)+@($proof.actual_current_archives)){AssertFile $f}
foreach($path in $proof.protected_paths){if(-not(Test-Path -LiteralPath $path)){throw 'Protected or ongoing work missing'}}
$branches=@(& $gitExecutable -C $root branch --list codex/roll-p0-ticket20 codex/roll-p0-ticket21)
if($branches.Count -ne 2){throw 'Accepted implementation branches missing'}
$result=[ordered]@{status='PASS';recorded_at=[DateTime]::UtcNow.ToString('o');preflight='cleanup20-21-preflight.json';
    removed_worktrees=@($proof.worktrees|ForEach-Object{$_.path});untracked_fixture_files_removed=@($proof.worktrees|ForEach-Object{$_.untracked_count});
    related_live_processes=0;junction_unlink_method='System.IO.Directory.Delete(path,false), exact root targets verified';
    native_removal='Remove-Item -LiteralPath exact authorized worktree -Recurse -Force; exact native Git registration removal';
    first_native_git_partial_removal='Ticket20 registration removed, residual entity directory required native PowerShell cleanup';
    root_profiles=$rootProfiles;root_tools_before=$proof.root_tools_before;root_tools_after_verified=$true;
    upstream19=$proof.upstream19;upstream19_unchanged=$true;actual_diagnostic_archives=$proof.actual_current_archives;
    protected_paths_present=$proof.protected_paths;worktrees_after=@(& $gitExecutable -C $root worktree list --porcelain);
    implementation_branches_retained=$branches;no_push=$true;tracker_unchanged=$true;production19_not_opened=$true}
[IO.File]::WriteAllText((Join-Path $receipt 'cleanup20-21-results.json'),(($result|ConvertTo-Json -Depth 9).Replace("`r`n","`n")+"`n"),[Text.UTF8Encoding]::new($false))
Write-Output 'PASS: exact ticket20/21 worktrees absent; root profiles/tools/model dependencies and protected/ongoing work unchanged'
