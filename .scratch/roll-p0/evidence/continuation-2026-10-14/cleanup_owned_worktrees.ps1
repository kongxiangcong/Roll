$ErrorActionPreference = 'Stop'
$taskRoot = 'D:\dsh-proj\Roll'
$taskEvidence = Join-Path $taskRoot '.scratch\roll-p0\evidence\continuation-2026-10-14'
$taskAudit = Get-Content -LiteralPath (Join-Path $taskEvidence 'cleanup-content-audit.json') -Raw | ConvertFrom-Json
$taskBase = Join-Path $taskRoot '.scratch\worktrees'
$taskTarget = Join-Path $taskRoot '.roll-data\implementation-evidence\worktree-cleanup-20261014'
$taskNames = @('t25-production-inputs','t30-action-window','t25-input-settings','t20-policy-successor')
if ($taskAudit.mismatches -ne 0 -or $taskAudit.worktrees.Count -ne 4) { throw 'Incomplete preservation audit' }
$taskOwned = @(Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and $_.CommandLine -and
    ($_.CommandLine -match '\.scratch[\\/]worktrees[\\/](t25-production-inputs|t30-action-window|t25-input-settings|t20-policy-successor)' -or $_.CommandLine -match 'vite.*--port\s+5914')
})
if ($taskOwned.Count) { throw 'Owned processes remain; retain all worktrees' }
foreach ($taskTree in $taskAudit.worktrees) {
    if ($taskTree.name -notin $taskNames) { throw 'Unexpected tree name' }
    $taskExpected = [IO.Path]::GetFullPath((Join-Path $taskBase $taskTree.name))
    if ([IO.Path]::GetFullPath($taskTree.path) -ne $taskExpected -or [IO.Path]::GetDirectoryName($taskExpected) -ne $taskBase) { throw 'Target outside exact owned worktree base' }
    $taskDirty = git -C $taskExpected status --porcelain=v1 --untracked-files=no
    if ($taskDirty) { throw 'Tracked changes remain' }
    git merge-base --is-ancestor $taskTree.head HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Worktree head is not integrated' }
    foreach ($taskFile in $taskTree.untracked_and_ignored_files) {
        $taskSource = [IO.Path]::GetFullPath((Join-Path $taskExpected $taskFile.path))
        $taskDestination = [IO.Path]::GetFullPath((Join-Path (Join-Path $taskTarget $taskTree.name) $taskFile.path))
        if (-not $taskSource.StartsWith($taskExpected+'\',[StringComparison]::OrdinalIgnoreCase) -or $taskDestination -ne [IO.Path]::GetFullPath($taskFile.destination) -or -not $taskDestination.StartsWith($taskTarget+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected preservation path' }
        foreach ($taskCheck in @($taskSource,$taskDestination)) {
            $taskLong = '\\?\' + $taskCheck
            $taskInfo = Get-Item -LiteralPath $taskLong -Force
            if ($taskInfo.Length -ne $taskFile.bytes -or (Get-FileHash -LiteralPath $taskLong -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskFile.sha256) { throw 'Preservation changed; retain source' }
        }
    }
    foreach ($taskLink in $taskTree.excluded_dependency_junctions) {
        $taskLinkPath = [IO.Path]::GetFullPath((Join-Path $taskExpected $taskLink.path))
        if (-not $taskLinkPath.StartsWith($taskExpected+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Link outside owned tree' }
        if ($taskLink.kind -eq 'JUNCTION') {
            $taskLinkInfo = Get-Item -LiteralPath $taskLinkPath -Force
            if ($taskLinkInfo.LinkType -ne 'Junction' -or $taskLinkInfo.Target -ne $taskLink.target) { throw 'Dependency link target changed' }
        } elseif ($taskLink.kind -ne 'GENERATED_INTERNAL_LINK' -or -not $taskLink.target.StartsWith($taskExpected+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unverified generated link' }
    }
}
# All four trees and every preserved file are verified before any removal.
foreach ($taskTree in $taskAudit.worktrees) {
    foreach ($taskLink in $taskTree.excluded_dependency_junctions | Where-Object kind -eq 'JUNCTION') {
        Remove-Item -LiteralPath (Join-Path $taskTree.path $taskLink.path) -Force
    }
    git -c core.longpaths=true worktree remove --force -- $taskTree.path
    if ($LASTEXITCODE -ne 0) { throw 'Worktree removal failed; inspect retained state' }
}
@{worktrees_removed=4;preserved_files=($taskAudit.worktrees | Measure-Object -Property file_count -Sum).Sum;preserved_bytes=($taskAudit.worktrees | Measure-Object -Property bytes -Sum).Sum;source_destination_mismatches=0;owned_processes=0;shared_dependency_targets_preserved=$true;accepted_branches_retained=$true} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskEvidence 'cleanup-result.json') -Encoding UTF8
git worktree list
