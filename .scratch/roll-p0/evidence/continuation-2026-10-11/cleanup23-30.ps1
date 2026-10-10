param([switch]$Remove)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath('D:\dsh-proj\Roll')
$evidence=Join-Path $root '.scratch/roll-p0/evidence/continuation-2026-10-11'
$gitExecutable=@(Get-Command git.exe -CommandType Application)[0].Source
$targets=@(
    [ordered]@{path=Join-Path $root '.scratch/worktrees/ticket23';commit='09a5b7959c6fe6b292f4ec5712015180106de5fc'},
    [ordered]@{path=Join-Path $root '.scratch/worktrees/ticket30';commit='c8a2ca2c6a76fd3dcabd24380e7d96b697b69dfc'}
)
function RunGit([string[]]$Arguments){
    $output=@(& $gitExecutable -C $root @Arguments 2>$null)
    if($LASTEXITCODE -ne 0){throw "Git failed: $($Arguments -join ' ')"}
    return $output
}
function FileProof([string]$Path){
    $item=Get-Item -LiteralPath $Path
    return [ordered]@{path=$item.FullName;bytes=$item.Length;sha256=(Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLower()}
}
function WriteRecord([string]$Name,$Value){
    [IO.File]::WriteAllText((Join-Path $evidence $Name),(($Value|ConvertTo-Json -Depth 12).Replace("`r`n","`n")+"`n"),[Text.UTF8Encoding]::new($false))
}
function AssertInside([string]$Path,[string]$Base){
    $absolute=[IO.Path]::GetFullPath($Path)
    if($absolute -ne $Base -and -not $absolute.StartsWith($Base+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Path outside exact boundary'}
    return $absolute
}
function RootDependencies{
    $files=@(Get-Item -LiteralPath (Join-Path $root '.env'))
    foreach($relative in @('backend/.venv','frontend/node_modules')){
        $directory=Join-Path $root $relative
        if((Get-Item -LiteralPath $directory).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Root dependency directory is a reparse point'}
        $files+=@(Get-ChildItem -LiteralPath $directory -Recurse -File -Force)
    }
    $files+=Get-Item -LiteralPath 'C:\Program Files\Google\Chrome\Application\chrome.exe'
    return @(foreach($file in ($files|Sort-Object FullName)){FileProof $file.FullName})
}
function AssertProof($Proof){
    $now=FileProof $Proof.path
    if($now.bytes -ne $Proof.bytes -or $now.sha256 -ne $Proof.sha256){throw "Saved file mismatch: $($Proof.path)"}
}
function AssertNoProcess{
    $related=@(Get-CimInstance Win32_Process|Where-Object{
        $_.Name -in @('python.exe','pythonw.exe','node.exe','chrome.exe','msedge.exe','uvicorn.exe','vite.exe') -and
        ($_.CommandLine -match '[\\/]\.scratch[\\/]worktrees[\\/]ticket(23|30)([\\/]|\s|$)' -or $_.ExecutablePath -match '[\\/]\.scratch[\\/]worktrees[\\/]ticket(23|30)([\\/]|\s|$)')
    }|Select-Object ProcessId,Name,ExecutablePath)
    if($related.Count){throw 'Related exact-tree live process found; none stopped'}
}
function PreservedProfiles([switch]$RootOnly){
    $m23=Get-Content -LiteralPath (Join-Path $root '.scratch/roll-p0/evidence/23/preservation-manifest.json') -Raw|ConvertFrom-Json
    $m30=Get-Content -LiteralPath (Join-Path $root '.scratch/roll-p0/evidence/30/runtime-preservation-manifest.json') -Raw|ConvertFrom-Json
    $items=@($m23.browser,$m23.provider_approval_local_only)+@($m30.profiles)
    return @(foreach($item in $items){
        $target=if($item.destination){$item.destination}else{$item.target}
        $target=AssertInside $target (Join-Path $root '.roll-data/implementation-evidence')
        $bases=if($RootOnly){@($target)}else{@($item.source,$target)}
        $bytes=0
        foreach($entry in $item.files){
            $size=if($null -ne $entry.bytes){$entry.bytes}else{$entry.length}
            foreach($base in $bases){
                $path=[IO.Path]::GetFullPath((Join-Path $base $entry.path))
                if($base -eq $target){
                    $b23=Join-Path $root '.roll-data/implementation-evidence/23';$b30=Join-Path $root '.roll-data/implementation-evidence/30'
                    $boundary=if($target.StartsWith($b23+'\',[StringComparison]::OrdinalIgnoreCase)){$b23}elseif($target.StartsWith($b30+'\',[StringComparison]::OrdinalIgnoreCase)){$b30}else{throw 'Unexpected root profile namespace'}
                }else{
                    $boundary=if($base.StartsWith($targets[0].path+'\',[StringComparison]::OrdinalIgnoreCase)){$targets[0].path}elseif($base.StartsWith($targets[1].path+'\',[StringComparison]::OrdinalIgnoreCase)){$targets[1].path}else{throw 'Source profile outside owned worktrees'}
                }
                AssertInside $path $boundary|Out-Null
                AssertProof ([pscustomobject]@{path=$path;bytes=$size;sha256=$entry.sha256})
            }
            $bytes+=$size
        }
        if(@($item.files).Count -ne $item.file_count){throw 'Preserved manifest count mismatch'}
        [ordered]@{source=$item.source;destination=$target;files=@($item.files).Count;bytes=$bytes;sha_and_length_matches=$true}
    })
}
AssertNoProcess
if(@(RunGit @('diff','--name-only')).Count -or @(RunGit @('diff','--cached','--name-only')).Count){throw 'Root tracked changes present'}
if(-not $Remove){
    $record=[ordered]@{status='PREFLIGHT_PASS';recorded_at=[DateTime]::UtcNow.ToString('o');root=$root;integration=@(RunGit @('rev-parse','HEAD'))[0];worktrees=@();related_live_processes=0;preserved_profiles=@();root_dependencies_before=@();upstream19=@();protected_paths=@()}
    $expectedLinks=@{'backend/.venv'=(Join-Path $root 'backend/.venv');'frontend/node_modules'=(Join-Path $root 'frontend/node_modules')}
    foreach($tree in $targets){
        $absolute=[IO.Path]::GetFullPath($tree.path)
        if($absolute -notin @($targets[0].path,$targets[1].path)){throw 'Outside exact authorized worktrees'}
        if((Get-Item -LiteralPath $absolute).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Worktree root is a link'}
        RunGit @('merge-base','--is-ancestor',$tree.commit,'HEAD')|Out-Null
        if(@(RunGit @('-C',$absolute,'rev-parse','HEAD'))[0] -ne $tree.commit){throw 'Unexpected final worktree HEAD'}
        $status=@(RunGit @('-C',$absolute,'status','--porcelain=v1','--untracked-files=all'))
        if(@($status|Where-Object{-not $_.StartsWith('?? ')}).Count){throw 'Worktree tracked state dirty'}
        $paths=@(foreach($line in $status){AssertInside (Join-Path $absolute $line.Substring(3)) $absolute})
        $links=@(Get-ChildItem -LiteralPath $absolute -Recurse -Force -Attributes ReparsePoint)
        $verified=@(foreach($link in $links){
            $relative=[IO.Path]::GetRelativePath($absolute,$link.FullName).Replace('\','/')
            if(-not $expectedLinks.ContainsKey($relative) -or $link.LinkType -ne 'Junction'){throw 'Unexpected reparse point'}
            $final=[IO.Path]::GetFullPath([string]$link.Target)
            if($final -ne $expectedLinks[$relative] -or -not(Test-Path -LiteralPath $final)){throw 'Junction target mismatch'}
            [ordered]@{path=$link.FullName;relative=$relative;target=$final}
        })
        foreach($envPath in @((Join-Path $absolute '.env'),(Join-Path $absolute 'backend/.env'))){if(Test-Path -LiteralPath $envPath){throw 'Unexpected worktree .env; do not copy or remove credentials'}}
        $record.worktrees+=@([ordered]@{path=$absolute;head=$tree.commit;merged=$true;tracked_clean=$true;untracked_count=$paths.Count;untracked_file_paths=$paths;
            untracked_groups=@($status|ForEach-Object{($_.Substring(3)-split '/')[0..1]-join '/'}|Sort-Object -Unique);junctions=$verified;
            saved_logs=@('.scratch/roll-p0/evidence/23/acceptance.md','.scratch/roll-p0/evidence/30/acceptance.md','.scratch/roll-p0/evidence/continuation-2026-10-11/merge23.md','.scratch/roll-p0/evidence/continuation-2026-10-11/merge30.md')})
    }
    $record.preserved_profiles=PreservedProfiles
    $record.root_dependencies_before=RootDependencies
    $upstream=Get-Content -LiteralPath (Join-Path $evidence 'upstream19-before20.json') -Raw|ConvertFrom-Json
    foreach($entry in $upstream){$proof=FileProof (Join-Path $root $entry.path);if($proof.bytes -ne $entry.bytes -or $proof.sha256 -ne $entry.sha256){throw 'Upstream19 dependency changed'};$record.upstream19+=@($proof)}
    foreach($relative in @('.scratch/local-commit-20261011','.scratch/roll-p0/evidence/19-reconstruction-2026-10-10/negative-real-integrity/.startup.lock','.scratch/roll-p0/evidence/19-reconstruction-2026-10-10/negative-real-integrity/backups','.workbuddy','.scratch/worktrees/continuation-review-fixes','.roll-data/implementation-evidence/21','.roll-data/implementation-evidence/23','.roll-data/implementation-evidence/continuation-review-fixes/actual-corrected-copy')){
        $path=Join-Path $root $relative;if(-not(Test-Path -LiteralPath $path)){throw 'Protected path missing'};$record.protected_paths+=@($path)
    }
    WriteRecord 'cleanup23-30-preflight.json' $record
    Write-Output "PASS preflight: untracked $($record.worktrees[0].untracked_count)/$($record.worktrees[1].untracked_count), profiles $($record.preserved_profiles.Count), root dependency files $($record.root_dependencies_before.Count)"
    exit
}
$proof=Get-Content -LiteralPath (Join-Path $evidence 'cleanup23-30-preflight.json') -Raw|ConvertFrom-Json
foreach($tree in $proof.worktrees){
    $path=[IO.Path]::GetFullPath($tree.path)
    if($path -notin @($targets[0].path,$targets[1].path)){throw 'Outside exact removal targets'}
    RunGit @('merge-base','--is-ancestor',$tree.head,'HEAD')|Out-Null
    if(@(RunGit @('-C',$path,'rev-parse','HEAD'))[0] -ne $tree.head){throw 'Source HEAD changed'}
    if(@(RunGit @('-C',$path,'status','--porcelain=v1','--untracked-files=no')).Count){throw 'Tracked worktree changed'}
    # Native enumeration does not follow junctions. Record ignored METHOD/runtime
    # and cache entities too, without reading their credential or archive contents.
    $entities=@(Get-ChildItem -LiteralPath $path -Recurse -File -Force|ForEach-Object{AssertInside $_.FullName $path})
    $tree|Add-Member -Force -NotePropertyName owned_entity_file_count -NotePropertyValue $entities.Count
    $tree|Add-Member -Force -NotePropertyName owned_entity_file_paths -NotePropertyValue $entities
}
WriteRecord 'cleanup23-30-preflight.json' $proof
PreservedProfiles|Out-Null
foreach($f in @($proof.root_dependencies_before)+@($proof.upstream19)){AssertProof $f}
AssertNoProcess
$removals=@()
foreach($tree in $proof.worktrees){
    $path=[IO.Path]::GetFullPath($tree.path)
    foreach($junction in $tree.junctions){
        $link=Get-Item -LiteralPath $junction.path
        if($link.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath([string]$link.Target) -ne $junction.target){throw 'Junction changed before unlink'}
        [IO.Directory]::Delete($junction.path,$false)
        if((Test-Path -LiteralPath $junction.path) -or -not(Test-Path -LiteralPath $junction.target)){throw 'Junction unlink or root target failure'}
    }
    if(@(Get-ChildItem -LiteralPath $path -Recurse -Force -Attributes ReparsePoint).Count){throw 'Unexpected remaining link; no recursive removal'}
    $gitOutput=@(& $gitExecutable -C $root worktree remove --force -- $path 2>&1|ForEach-Object{[string]$_})
    $gitExit=$LASTEXITCODE
    if(Test-Path -LiteralPath $path){
        if($path -notin @($targets[0].path,$targets[1].path) -or (Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Unsafe residual worktree target'}
        if(@(Get-ChildItem -LiteralPath $path -Recurse -Force -Attributes ReparsePoint).Count){throw 'Residual tree has link'}
        Remove-Item -LiteralPath $path -Recurse -Force
    }
    if(Test-Path -LiteralPath $path){throw 'Residual owned worktree exists'}
    $registered=@(RunGit @('worktree','list','--porcelain'))
    if($registered -contains ('worktree '+$path.Replace('\','/'))){RunGit @('worktree','remove','--force','--',$path)|Out-Null}
    $removals+=@([ordered]@{path=$path;native_git_exit=$gitExit;native_git_output=$gitOutput;absent=$true})
}
$rootProfiles=PreservedProfiles -RootOnly
$after=RootDependencies
if($after.Count -ne $proof.root_dependencies_before.Count){throw 'Root dependency file count changed'}
for($i=0;$i -lt $after.Count;$i++){
    if($after[$i].path -ne $proof.root_dependencies_before[$i].path -or $after[$i].bytes -ne $proof.root_dependencies_before[$i].bytes -or $after[$i].sha256 -ne $proof.root_dependencies_before[$i].sha256){throw 'Root dependency inventory changed'}
}
foreach($f in $proof.upstream19){AssertProof $f}
foreach($path in $proof.protected_paths){if(-not(Test-Path -LiteralPath $path)){throw 'Protected path disappeared'}}
$branches=@(RunGit @('branch','--list','codex/roll-p0-ticket23','codex/roll-p0-ticket30'))
if($branches.Count -ne 2){throw 'Accepted implementation branch missing'}
$result=[ordered]@{status='PASS';recorded_at=[DateTime]::UtcNow.ToString('o');preflight='cleanup23-30-preflight.json';removals=$removals;
    junction_unlink='System.IO.Directory.Delete(path,false), exact root targets verified';root_profiles=$rootProfiles;
    root_dependency_file_count=$after.Count;root_dependencies_SHA_length_unchanged=$true;upstream19_unchanged=$true;
    protected_paths_present=$proof.protected_paths;worktrees_after=@(RunGit @('worktree','list','--porcelain'));branches_retained=$branches;
    credentials_copied=$false;old_packet_preserved_as_history=$true;actual_copy_preserved=$true;corrected_copy_preserved=$true;
    tracker_unchanged=$true;no_push=$true;no_original19_or_SEALED_opened=$true}
WriteRecord 'cleanup23-30-results.json' $result
Write-Output "PASS cleanup: exact ticket23/30 absent; $($after.Count) root dependency files, protected paths, model dependencies and required root profiles unchanged"
