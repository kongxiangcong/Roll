$ErrorActionPreference = 'Stop'
$rollRoot = 'D:\dsh-proj\Roll'
$rollEvidence = Join-Path $rollRoot '.scratch\roll-p0\evidence\continuation-2026-10-08'
$rollNames = @('12-live', '13-switch', 'fuyao-data', 'review-fixes-live')
$rollWorkspace = [System.IO.Path]::GetFullPath((Join-Path $rollRoot '.scratch\worktrees'))
foreach ($rollParent in @($rollRoot, (Join-Path $rollRoot '.scratch'), $rollWorkspace)) {
    if ((Get-Item -LiteralPath $rollParent).Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        throw 'WORKTREE_PARENT_IS_LINK'
    }
}
$rollDependencies = @(
    (Join-Path $rollRoot 'backend\.venv\Scripts\python.exe'),
    (Join-Path $rollRoot 'frontend\node_modules\@playwright\test\cli.js')
)
Set-Location -LiteralPath $rollRoot
if ((git branch --show-current) -ne 'codex/roll-p0-integration') { throw 'WRONG_INTEGRATION_BRANCH' }
$rollSuite = Get-Content -LiteralPath (Join-Path $rollEvidence 'final-backend-db9ef0c.txt') -Raw
if ($rollSuite -notmatch '=+ 372 passed in [0-9.]+s') { throw 'FINAL_SUITE_NOT_COMPLETE_GREEN' }
$rollProof = Get-Content -LiteralPath (Join-Path $rollEvidence 'final-preservation.json') -Raw | ConvertFrom-Json
if ($rollProof.verification_scope -ne 'SOURCE_AND_DESTINATION' -or $rollProof.files -ne 851 -or
    $rollProof.both_tree_sha_length_mismatches -ne 0 -or $rollProof.credential_matches -ne 0 -or
    -not $rollProof.env_unchanged -or -not $rollProof.env_ignored -or $rollProof.env_tracked) {
    throw 'PRESERVATION_NOT_VERIFIED'
}
$rollBefore = @($rollDependencies | ForEach-Object {
    @{ path = $_; sha256 = (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash }
})
$rollChecked = @()
foreach ($rollName in $rollNames) {
    $rollTree = [System.IO.Path]::GetFullPath((Join-Path $rollWorkspace $rollName))
    if ($rollTree -ne "$rollWorkspace\$rollName" -or -not $rollTree.StartsWith("$rollWorkspace\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'WORKTREE_OUTSIDE_EXACT_OWNED_PATH'
    }
    $rollItem = Get-Item -LiteralPath $rollTree
    if ($rollItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw 'TOP_WORKTREE_IS_LINK' }
    $rollDirty = @(git -C $rollTree status --porcelain --untracked-files=all)
    if ($LASTEXITCODE -ne 0 -or $rollDirty.Count -ne 0) { throw "WORKTREE_NOT_CLEAN: $rollName" }
    $rollHead = git -C $rollTree rev-parse HEAD
    if ($LASTEXITCODE -ne 0) { throw 'WORKTREE_HEAD_FAILED' }
    git merge-base --is-ancestor $rollHead HEAD
    if ($LASTEXITCODE -ne 0) { throw "WORKTREE_NOT_MERGED: $rollName" }
    $rollBranch = git -C $rollTree branch --show-current
    $rollLinks = @()
    foreach ($rollSuffix in @('backend\.venv', 'frontend\node_modules')) {
        $rollLinkPath = Join-Path $rollTree $rollSuffix
        if (-not (Test-Path -LiteralPath $rollLinkPath)) { continue }
        $rollLink = Get-Item -LiteralPath $rollLinkPath
        if ($rollLink.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            $rollExpectedTarget = [System.IO.Path]::GetFullPath((Join-Path $rollRoot $rollSuffix))
            $rollTargets = @($rollLink.Target)
            if ($rollLink.LinkType -ne 'Junction' -or $rollTargets.Count -ne 1 -or
                [System.IO.Path]::GetFullPath($rollTargets[0]) -ne $rollExpectedTarget) {
                throw 'UNEXPECTED_DEPENDENCY_LINK'
            }
            $rollLinks += @{ path = $rollLinkPath; target = $rollExpectedTarget }
        }
    }
    $rollChecked += @{ path = $rollTree; branch = $rollBranch; head = $rollHead; dirty_count = 0; merged = $true; links = $rollLinks }
}
$rollActive = @(Get-CimInstance Win32_Process | Where-Object {
    $rollProcess = $_
    ($rollProcess.Name -match '^(python|node|codex).*') -and
    (@($rollChecked | Where-Object { $rollProcess.CommandLine -and $rollProcess.CommandLine.Contains($_.path) }).Count -gt 0)
})
if ($rollActive.Count -gt 0) { throw 'OWNED_WORKTREE_HAS_ACTIVE_RUNTIME' }
$rollStarted = [DateTime]::UtcNow.ToString('o')
foreach ($rollRecord in $rollChecked) {
    # The exact root dependency target was verified above. Delete only the link itself.
    foreach ($rollLink in $rollRecord.links) {
        [System.IO.Directory]::Delete($rollLink.path, $false)
        if (Test-Path -LiteralPath $rollLink.path) { throw 'JUNCTION_NOT_DETACHED' }
    }
    git -c core.longpaths=true worktree remove $rollRecord.path
    if ($LASTEXITCODE -ne 0) {
        # Only this clean, merged, exact owned checkout; necessary ignored archives are verified in the proof.
        git -c core.longpaths=true worktree remove --force $rollRecord.path
        if ($LASTEXITCODE -ne 0) { throw 'OWNED_WORKTREE_REMOVE_FAILED' }
        $rollRecord.force_for_ignored_files = $true
    } else { $rollRecord.force_for_ignored_files = $false }
    $rollRecord.removed = -not (Test-Path -LiteralPath $rollRecord.path)
    if (-not $rollRecord.removed) { throw 'OWNED_WORKTREE_REMAINS' }
    Write-Output "Removed owned worktree: $($rollRecord.path)"
}
$rollAfter = @($rollDependencies | ForEach-Object {
    @{ path = $_; sha256 = (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash }
})
for ($rollIndex = 0; $rollIndex -lt $rollBefore.Count; $rollIndex++) {
    if ($rollBefore[$rollIndex].sha256 -ne $rollAfter[$rollIndex].sha256) { throw 'ROOT_DEPENDENCY_CHANGED' }
}
$rollRemaining = @(git worktree list --porcelain)
if ($LASTEXITCODE -ne 0) { throw 'WORKTREE_LIST_FAILED' }
$rollResult = @{
    started_at = $rollStarted; completed_at = [DateTime]::UtcNow.ToString('o');
    checked_git_head = (git rev-parse HEAD); worktrees = $rollChecked;
    root_dependency_before = $rollBefore; root_dependency_after = $rollAfter;
    root_dependency_sha_mismatches = 0; remaining_worktrees = $rollRemaining;
    preserved_runtime_files = $rollProof.files; preserved_runtime_bytes = $rollProof.bytes;
    preserved_runtime_source_destination_mismatches = 0; credential_matches = 0
}
$rollResult | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $rollEvidence 'worktree-cleanup-final.json') -Encoding utf8
