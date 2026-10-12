$taskProcesses = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'python.exe' -and $_.CommandLine -and
    ($_.CommandLine -match 'pytest.*t30q|30-sse-price-quotes')
} | Select-Object ProcessId,Name,CommandLine)
$taskReceipt = [ordered]@{owned_eighth_python_process_count=$taskProcesses.Count; processes=$taskProcesses; observed_at=[DateTimeOffset]::UtcNow.ToString('o'); other_processes_terminated=$false}
$taskReceipt | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'cim-final.json') -Encoding utf8
if ($taskProcesses.Count -ne 0) { throw 'OWNED_EIGHTH_PROCESS_REMAINS' }
Write-Output 'OWNED_EIGHTH_PYTHON_CIM_ZERO'
