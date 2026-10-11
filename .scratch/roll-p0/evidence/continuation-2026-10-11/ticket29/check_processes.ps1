$tree='D:\dsh-proj\Roll\.scratch\worktrees\ticket29'
$factory='report_'+'method_app:factory'
$config='playwright.'+'reports.config.ts'
$processes=@(Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and $_.CommandLine -and
    (($_.CommandLine.Contains($tree) -and $_.Name -match 'python|node|chrome') -or
     $_.CommandLine.Contains($factory) -or
     ($_.Name -match 'node' -and ($_.CommandLine.Contains($config) -or $_.CommandLine -match '--port\s+5291')))
} | Select-Object ProcessId,ParentProcessId,Name,CommandLine)
$out=Join-Path $tree '.scratch/roll-p0/evidence/continuation-2026-10-11/ticket29/cim-final.json'
[pscustomobject]@{checked_at=[DateTime]::UtcNow.ToString('o');exact_owned_matches=$processes.Count;processes=$processes} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $out
if ($processes.Count -ne 0) { throw 'Owned processes still active; preserve only after stop.' }
Write-Output 'Exact owned CIM process matches: 0'
