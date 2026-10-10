param([switch]$Remove)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath('D:\dsh-proj\Roll')
$gitExecutable=@(Get-Command git.exe -CommandType Application)[0].Source
$evidence=Join-Path $root '.scratch/roll-p0/evidence/continuation-2026-10-11'
$targets=@(
    [ordered]@{path=Join-Path $root '.scratch/worktrees/ticket20';commit='4a099d891360b5f428de4ea6063826b7bcf1524e'},
    [ordered]@{path=Join-Path $root '.scratch/worktrees/ticket21';commit='aef9b27bd32bb9983fcce77ab642a17c2dfcf3e0'}
)
function Git([string[]]$Arguments) {
    $output=@(& $gitExecutable -C $root @Arguments 2>$null)
    if($LASTEXITCODE -ne 0){throw "Git failed: $($Arguments -join ' ')"}
    return $output
}
function FileProof([string]$Path) {
    $item=Get-Item -LiteralPath $Path
    return [ordered]@{path=$item.FullName;bytes=$item.Length;sha256=(Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLower()}
}
function WriteRecord([string]$Name,$Value) {
    [IO.File]::WriteAllText((Join-Path $evidence $Name),(($Value|ConvertTo-Json -Depth 12).Replace("`r`n","`n")+"`n"),[Text.UTF8Encoding]::new($false))
}
$tools=@('backend/.venv/Scripts/python.exe','backend/.venv/pyvenv.cfg','frontend/node_modules/playwright/package.json',
    'frontend/node_modules/playwright/cli.js','frontend/node_modules/playwright-core/package.json',
    'frontend/node_modules/playwright-core/lib/server/registry/index.js','frontend/node_modules/@playwright/test/package.json')
$toolProof=@(foreach($relative in $tools){FileProof (Join-Path $root $relative)})
$toolProof+=FileProof 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$record=[ordered]@{mode=$(if($Remove){'REMOVE'}else{'VERIFY'});root=$root;integration=@(Git @('rev-parse','HEAD'))[0];recorded_at=[DateTime]::UtcNow.ToString('o');root_tools_before=$toolProof;worktrees=@();preserved_profiles=@();upstream19=@();processes=@();protected_paths=@()}
if(@(Git @('diff','--name-only')).Count -or @(Git @('diff','--cached','--name-only')).Count){throw 'Root tracked work is dirty'}
$processes=@(Get-CimInstance Win32_Process)
$related=@($processes|Where-Object{
    $_.Name -in @('python.exe','pythonw.exe','node.exe','chrome.exe','uvicorn.exe','vite.exe') -and
    ($_.CommandLine -match '[\\/]\.scratch[\\/]worktrees[\\/]ticket(20|21)([\\/]|\s|$)' -or $_.ExecutablePath -match '[\\/]\.scratch[\\/]worktrees[\\/]ticket(20|21)([\\/]|\s|$)')
}|Select-Object ProcessId,Name,ExecutablePath)
if($related.Count){throw 'A live process references ticket20/21; no process was stopped'}
$record.processes=$related
$expectedLinks=@{'backend/.venv'=(Join-Path $root 'backend/.venv');'frontend/node_modules'=(Join-Path $root 'frontend/node_modules')}
foreach($tree in $targets){
    $absolute=[IO.Path]::GetFullPath($tree.path)
    if($absolute -notin @((Join-Path $root '.scratch/worktrees/ticket20'),(Join-Path $root '.scratch/worktrees/ticket21'))){throw 'Outside exact authorized targets'}
    $item=Get-Item -LiteralPath $absolute
    if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Worktree itself is a reparse point'}
    Git @('merge-base','--is-ancestor',$tree.commit,'HEAD')|Out-Null
    if(@(Git @('-C',$absolute,'rev-parse','HEAD'))[0] -ne $tree.commit){throw 'Worktree HEAD differs from accepted commit'}
    $status=@(Git @('-C',$absolute,'status','--porcelain=v1','--untracked-files=all'))
    if(@($status|Where-Object{-not $_.StartsWith('?? ')}).Count){throw 'Worktree tracked state is dirty'}
    $allowed=if($absolute.EndsWith('ticket20')){
        '^\?\? backend/\.(test-statistics-(red|green)|test-tmp-(accepted20|browser20|browser20b|browser20delivery|browser20final|browser20holding|browser20last|conditional20red|corrupt20red|delivery20|final-hash20|final20|green20a|green20b|green20c|green20d|green20f|holding20green|holding20red|last20|red20|red20b|red20e|upstream20|zero20red))/'
    }else{'^\?\? \.test-tmp-validation-(red|green|delay-green|delay-red|monitor-green|monitor-red|negative-green|negative-red|partial-red)/'}
    if(@($status|Where-Object{$_ -notmatch $allowed}).Count){throw 'Unexpected untracked path outside exact authorized fixture list'}
    $untrackedPaths=@(foreach($line in $status){
        $path=[IO.Path]::GetFullPath((Join-Path $absolute $line.Substring(3)))
        if(-not $path.StartsWith($absolute+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Untracked path escapes exact worktree'}
        $path
    })
    $links=@(Get-ChildItem -LiteralPath $absolute -Recurse -Force -Attributes ReparsePoint)
    if($links.Count -ne 2){throw 'Unexpected reparse point count'}
    $verified=@(foreach($link in $links){
        $relative=[IO.Path]::GetRelativePath($absolute,$link.FullName).Replace('\','/')
        if(-not $expectedLinks.ContainsKey($relative) -or $link.LinkType -ne 'Junction'){throw 'Unexpected reparse point'}
        $final=[IO.Path]::GetFullPath([string]$link.Target)
        if($final -ne $expectedLinks[$relative] -or -not(Test-Path -LiteralPath $final)){throw 'Junction target mismatch'}
        [ordered]@{path=$link.FullName;target=$final;relative=$relative;unlink_method='System.IO.Directory.Delete(path,false)'}
    })
    $record.worktrees+=@([ordered]@{path=$absolute;head=$tree.commit;merged=$true;tracked_clean=$true;untracked_count=$status.Count;
        untracked_fixture_directories=@($status|ForEach-Object{($_.Substring(3)-split '/')[0..1]-join '/'}|Sort-Object -Unique);
        untracked_file_paths=$untrackedPaths;saved_evidence=@('.scratch/roll-p0/evidence/20/acceptance.md','.scratch/roll-p0/evidence/21/acceptance.md','.scratch/roll-p0/evidence/continuation-2026-10-11/merge20.md','.scratch/roll-p0/evidence/continuation-2026-10-11/merge21.md');junctions=$verified})
}
$manifests=@(
    '.scratch/roll-p0/evidence/continuation-2026-10-11/browser20-profile-manifest.json',
    '.scratch/roll-p0/evidence/continuation-2026-10-11/browser20-fixed-profile-manifest.json',
    '.scratch/roll-p0/evidence/21/browser-runtime-preservation.json',
    '.scratch/roll-p0/evidence/continuation-2026-10-11/independent20-profile-manifest.json',
    '.scratch/roll-p0/evidence/continuation-2026-10-11/independent21-profile-manifest.json'
)
foreach($relative in $manifests){
    $manifest=Get-Content -LiteralPath (Join-Path $root $relative) -Raw|ConvertFrom-Json
    $entries=if($manifest.entries){@($manifest.entries)}else{@($manifest.files)}
    $bases=if($manifest.source){@($manifest.source,$manifest.destination)}elseif($manifest.directory){@($manifest.directory)}else{@($manifest.profile)}
    $bytes=0
    foreach($entry in $entries){
        foreach($base in $bases){
            $base=[IO.Path]::GetFullPath($base)
            if(-not $base.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Profile outside workspace'}
            $file=[IO.Path]::GetFullPath((Join-Path $base $entry.path))
            if(-not $file.StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Unsafe profile entry'}
            $proof=FileProof $file
            if($proof.bytes -ne $entry.bytes -or $proof.sha256 -ne $entry.sha256){throw "Preserved file mismatch: $file"}
        }
        $bytes+=$entry.bytes
    }
    foreach($base in $bases){if(@(Get-ChildItem -LiteralPath $base -Recurse -File -Force).Count -ne $entries.Count){throw 'Profile file count differs from manifest'}}
    $record.preserved_profiles+=@([ordered]@{manifest=$relative;source=$manifest.source;destination=$manifest.destination;root_profile=$(if($manifest.directory){$manifest.directory}else{$manifest.profile});files=$entries.Count;bytes=$bytes;sha_and_length_matches=$true})
}
$upstream=Get-Content -LiteralPath (Join-Path $evidence 'upstream19-before20.json') -Raw|ConvertFrom-Json
foreach($entry in $upstream){
    $proof=FileProof (Join-Path $root $entry.path)
    if($proof.bytes -ne $entry.bytes -or $proof.sha256 -ne $entry.sha256){throw 'Upstream19 changed'}
    $record.upstream19+=@($proof)
}
# Only current21 diagnostic archives; original19 and SEALED contents are not opened.
$actual=Get-Content -LiteralPath (Join-Path $root '.scratch/roll-p0/evidence/21/actual-current-results.json') -Raw|ConvertFrom-Json
$actualCopy=Join-Path $root '.roll-data/implementation-evidence/21/actual-current-copy'
$record.actual_current_archives=@(foreach($archive in @($actual.full_freeze.archive,$actual.validation.input_archive,$actual.validation.manifest_archive)){
    $file=[IO.Path]::GetFullPath((Join-Path $actualCopy $archive.path))
    if(-not $file.StartsWith($actualCopy+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Unsafe actual-copy archive path'}
    $proof=FileProof $file
    if($proof.bytes -ne $archive.bytes -or $proof.sha256 -ne $archive.sha256){throw 'Actual21 diagnostic archive mismatch'}
    $proof
})
foreach($relative in @('.scratch/local-commit-20261011','.scratch/roll-p0/evidence/19-reconstruction-2026-10-10/negative-real-integrity/.startup.lock','.scratch/roll-p0/evidence/19-reconstruction-2026-10-10/negative-real-integrity/backups','.workbuddy','.scratch/worktrees/ticket23','.scratch/worktrees/ticket30')){
    $path=Join-Path $root $relative
    if(-not(Test-Path -LiteralPath $path)){throw 'Protected or ongoing work path missing'}
    $record.protected_paths+=@($path)
}
WriteRecord 'cleanup20-21-preflight.json' $record
if(-not $Remove){Write-Output 'PASS: clean merged worktrees, no related live process, all required root preservation verified';exit}
foreach($tree in $record.worktrees){
    foreach($junction in $tree.junctions){
        $link=Get-Item -LiteralPath $junction.path
        if($link.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath([string]$link.Target) -ne $junction.target){throw 'Junction changed before unlink'}
        [IO.Directory]::Delete($junction.path,$false)
        if(Test-Path -LiteralPath $junction.path){throw 'Junction still present'}
        if(-not(Test-Path -LiteralPath $junction.target)){throw 'Root junction target missing'}
    }
    # Native Git worktree lifecycle, exact prevalidated absolute path, same PowerShell session.
    Git @('worktree','remove','--force','--',$tree.path)|Out-Null
    if(Test-Path -LiteralPath $tree.path){throw 'Worktree removal incomplete'}
}
$after=@(foreach($entry in $toolProof){FileProof $entry.path})
for($i=0;$i -lt $toolProof.Count;$i++){if($toolProof[$i].bytes -ne $after[$i].bytes -or $toolProof[$i].sha256 -ne $after[$i].sha256){throw 'Root tool changed'}}
$record.root_tools_after=$after
$record.root_tools_unchanged=$true
$record.worktrees_after=Git @('worktree','list','--porcelain')
foreach($path in $record.protected_paths){if(-not(Test-Path -LiteralPath $path)){throw 'Protected or ongoing work disappeared'}}
$record.status='PASS'
$record.no_branches_deleted=$true
$record.no_push=$true
WriteRecord 'cleanup20-21-results.json' $record
Write-Output 'PASS: ticket20 and ticket21 removed; root dependencies, protected work and ticket23/ticket30 retained'
