$ErrorActionPreference = 'Stop'
$taskRoot = 'D:\dsh-proj\Roll'
$taskEvidence = Join-Path $taskRoot '.scratch\roll-p0\evidence\continuation-2026-10-14'
$taskAudit = Get-Content -LiteralPath (Join-Path $taskEvidence 'ticket25-closed-funding-preservation.json') -Raw | ConvertFrom-Json
$taskTree = 'D:\dsh-proj\Roll\.scratch\worktrees\t25-closed-funding'
$taskDestinationRoot = 'D:\dsh-proj\Roll\.roll-data\implementation-evidence\ticket25-closed-funding-20261014'
if ([IO.Path]::GetFullPath($taskAudit.source) -ne $taskTree -or [IO.Path]::GetFullPath($taskAudit.destination) -ne $taskDestinationRoot -or [IO.Path]::GetDirectoryName($taskTree) -ne 'D:\dsh-proj\Roll\.scratch\worktrees') { throw 'Unexpected exact target' }
if ($taskAudit.mismatches -ne 0 -or $taskAudit.files.Count -ne 281 -or $taskAudit.known_links.Count -ne 0) { throw 'Incomplete preservation' }
if (git -C $taskTree status --porcelain=v1 --untracked-files=no) { throw 'Tracked changes remain' }
git merge-base --is-ancestor $taskAudit.head HEAD
if ($LASTEXITCODE -ne 0) { throw 'Head not integrated' }
$taskOwned = @(Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -and $_.Name -match '^(python|pythonw|node)\.exe$' -and $_.CommandLine -match 't25-closed-(funding|red|green)' })
if ($taskOwned.Count) { throw 'Owned processes remain' }
$taskPaths = @(git -C $taskTree ls-files --others --exclude-standard) + @(git -C $taskTree ls-files --others --ignored --exclude-standard)
$taskRecorded = @($taskAudit.files | ForEach-Object { $_.relative.Replace('\','/') })
if (@(Compare-Object ($taskPaths | Sort-Object) ($taskRecorded | Sort-Object)).Count) { throw 'Untracked or ignored inventory changed' }
foreach ($taskFile in $taskAudit.files) {
    $taskSource = [IO.Path]::GetFullPath((Join-Path $taskTree $taskFile.relative))
    $taskDestination = [IO.Path]::GetFullPath((Join-Path $taskDestinationRoot $taskFile.relative))
    if (-not $taskSource.StartsWith($taskTree+'\',[StringComparison]::OrdinalIgnoreCase) -or -not $taskDestination.StartsWith($taskDestinationRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Path outside exact roots' }
    foreach ($taskPath in @($taskSource,$taskDestination)) {
        $taskInfo = Get-Item -LiteralPath ('\\?\'+$taskPath) -Force
        if ($taskInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Unexpected link' }
        if ($taskInfo.Length -ne $taskFile.bytes -or (Get-FileHash -LiteralPath ('\\?\'+$taskPath) -Algorithm SHA256).Hash -ne $taskFile.before_sha256) { throw 'Preservation mismatch' }
    }
}
git -c core.longpaths=true worktree remove --force -- $taskTree
if ($LASTEXITCODE -ne 0) { throw 'Removal failed' }
@{worktree_removed=$taskTree;preserved_files=281;preserved_bytes=$taskAudit.bytes;mismatches=0;owned_processes=0;branches_retained=$true} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskEvidence 'closed-funding-cleanup-result.json') -Encoding UTF8
git worktree list
