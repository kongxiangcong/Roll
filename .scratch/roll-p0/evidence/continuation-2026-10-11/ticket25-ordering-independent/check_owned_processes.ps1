$ErrorActionPreference='Stop'
$receiptDir='D:/dsh-proj/Roll/.scratch/roll-p0/evidence/continuation-2026-10-11/ticket25-ordering-independent'
$exactPaths=@('D:/dsh-proj/Roll/.scratch/worktrees/ticket25-ordering','D:\dsh-proj\Roll\.scratch\worktrees\ticket25-ordering','D:/dsh-proj/Roll/.roll-data/t25oi-first','D:\dsh-proj\Roll\.roll-data\t25oi-first')
$hits=@(Get-CimInstance Win32_Process | Where-Object {
  $line=$_.CommandLine
  $match=$false
  if($line){foreach($path in $exactPaths){if($line -match [regex]::Escape($path)){$match=$true}}
    if($line -match 'test_public.py' -and $line -match 'ticket25-ordering-independent'){$match=$true}}
  $match -and $_.ProcessId -ne $PID
} | Select-Object Name,ProcessId,ParentProcessId,CreationDate)
@{observed_utc=[DateTime]::UtcNow.ToString('o');count=$hits.Count;processes=$hits;command_lines_saved=$false;exact_owned_tree_and_harness=$true;only_observer_pid_excluded=$true} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath ($receiptDir+'/cim-final.json') -Encoding utf8
if($hits.Count -ne 0){throw 'Owned process still live'}
Get-Content -LiteralPath ($receiptDir+'/cim-final.json')
