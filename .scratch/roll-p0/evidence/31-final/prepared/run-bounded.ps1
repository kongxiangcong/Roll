# Preparation only by default. No process/test/benchmark until accepted fix release.
param([ValidateSet('Reviews','Benchmark')][string]$Stage='Reviews',[switch]$Execute,[string]$AcceptedFixOID)
$ErrorActionPreference='Stop'
$Tree=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../../..'))
$Python=Join-Path $Tree 'backend/.venv/Scripts/python.exe'
$Expected='D:\dsh-proj\Roll\.scratch\worktrees\ticket31-final'
if($Tree.TrimEnd('\') -ne $Expected){throw 'Wrong final31 owned tree'}
if(-not $Execute){Write-Output 'PREPARED_ONLY: requires root accepted final-fix OID and execution release';exit 0}
if($AcceptedFixOID -notmatch '^[0-9a-f]{40}$'){throw 'Exact independently accepted final-fix OID required'}
& git -C $Tree merge-base --is-ancestor $AcceptedFixOID HEAD
if($LASTEXITCODE -ne 0){throw 'Accepted fix not merged into own final31 tree'}
$env:ROLL_FINAL31_BEHAVIOR_RELEASE='1'
$env:ROLL_FINAL31_ACCEPTED_FIX_OID=$AcceptedFixOID
$env:ROLL_ENV='test'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH=(Join-Path $Tree 'backend/src')+';'+(Join-Path $Tree 'backend/tests/support')
$Run=[Guid]::NewGuid().ToString('N')
$Runtime=Join-Path $Tree ('.roll-data/final31-bounded-'+$Run)
$Receipt=Join-Path $PSScriptRoot ('../runs/'+$Run)
New-Item -ItemType Directory -Path $Receipt -Force|Out-Null
Push-Location $Tree
try{
 if($Stage -eq 'Reviews'){
  # Windows archived filenames plus pytest case names need a short owned path.
  $Runtime=Join-Path $Tree ('.scratch/f31r-'+$Run.Substring(0,8))
  New-Item -ItemType Directory -Path $Runtime -Force|Out-Null
  [IO.File]::WriteAllText((Join-Path $Receipt 'runtime-path.txt'),$Runtime,[Text.UTF8Encoding]::new($false))
  Push-Location (Join-Path $Tree 'backend')
  try{
   & $Python -B -X utf8 -m pytest tests/application/test_reviews.py::test_intraday_current_bar_cannot_replace_last_complete_daily_or_refresh_old_quote_time tests/application/test_reviews.py::test_persistent_worker_retries_with_backoff_once_per_identity_and_preserves_partial_facts -q --basetemp $Runtime 2>&1|Tee-Object (Join-Path $Receipt 'two-exact-reviews.log')
   $Result=$LASTEXITCODE
  }finally{Pop-Location}
 }else{
  $env:ROLL_FINAL31_NUMERIC_RUNTIME=Join-Path $Runtime 'numeric'
  $env:ROLL_FINAL31_NUMERIC_RECEIPT=Join-Path $Receipt 'numeric-p95.json'
  & $Python -B -X utf8 (Join-Path $PSScriptRoot 'numeric-benchmark.py') 2>&1|Tee-Object (Join-Path $Receipt 'numeric-p95.log')
  $Result=$LASTEXITCODE
 }
 [IO.File]::WriteAllText((Join-Path $Receipt 'exit.txt'),[string]$Result,[Text.UTF8Encoding]::new($false))
 if($Result -ne 0){throw "Bounded stage failed ($Result); preserve failure, no automatic retry"}
}finally{Pop-Location}
