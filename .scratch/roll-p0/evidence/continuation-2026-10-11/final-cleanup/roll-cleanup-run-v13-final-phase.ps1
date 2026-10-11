param([ValidateSet('Preflight','Execute','Post')][string]$Phase,[string]$Executor)
$ErrorActionPreference='Stop'
$v=$PSScriptRoot
$log=Join-Path $v ('roll-cleanup-final-'+$Phase.ToLowerInvariant()+'-run.log')
$failure=Join-Path $v ('roll-cleanup-final-'+$Phase.ToLowerInvariant()+'-failure.json')
$release=Join-Path $v 'roll-cleanup-release-v13-exact3802.json'
try {
  & (Join-Path $v $Executor) -Phase $Phase -ReleaseFile $release -RootExecutionWindow *> $log
  Write-Output ('ACTUAL_'+$Phase.ToUpperInvariant()+'_RETURNED_SUCCESS')
} catch {
  [IO.File]::WriteAllText($failure,(@{phase=$Phase;executor=$Executor;release=$release;error=$_.Exception.Message;script_stack=$_.ScriptStackTrace;utc=[datetime]::UtcNow.ToString('o');success=$false}|ConvertTo-Json -Depth 6)+"`n")
  Write-Error $_
  exit 1
}
