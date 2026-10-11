# Pure boundary helper; only callers explicitly invoke bounded CWD reads.
$CwdHelper = Join-Path $PSScriptRoot 'roll-cleanup-cwd-reader-v9.cs'
Add-Type -Path $CwdHelper
function ProcessIdentityMatch($p,$r){
 $null -ne $p -and [int]$p.ProcessId -eq [int]$r.pid -and $p.Name -eq $r.name -and $p.ExecutablePath -eq $r.executable_path -and [int]$p.ParentProcessId -eq [int]$r.parent_process_id -and ([datetime]$p.CreationDate).ToUniversalTime().ToString('o') -eq ([datetime]$r.creation_date_utc).ToUniversalTime().ToString('o')
}
function NoReparsePath($path){
 $current=[IO.Path]::GetFullPath($path)
 while($current){
  if(Test-Path -LiteralPath $current){$item=Get-Item -LiteralPath $current -Force;if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){return $false}}
  $parent=[IO.Directory]::GetParent($current);$current=if($parent){$parent.FullName}else{$null}
 };return $true
}
function ExactOutsideBoundary($p,$r,$all){
 if(-not(ProcessIdentityMatch $p $r)){return $false}
 if($r.disposition -ne 'OUTSIDE_DELETION_SCOPE'){return $false}
 foreach($ancestor in @($r.parent,$r.grandparent)){
  if($null -eq $ancestor){return $false};$live=@($all|Where-Object {[int]$_.ProcessId -eq [int]$ancestor.pid})
  if($live.Count -ne 1 -or -not(ProcessIdentityMatch $live[0] $ancestor)){return $false}
 }
 $proof=$r.source_owner_proof;$argv=[CwdExactArgv]::Get([string]$p.CommandLine)
 if($argv.Count -ne 2 -or $argv[0] -ne $p.ExecutablePath){return $false}
 $module=[IO.Path]::GetFullPath([string]$proof.expected_public_argument_path)
 if($proof.command_kind -eq 'EXACT_ABSOLUTE_PUBLIC_DAEMON_PATH'){
  if(-not[IO.Path]::IsPathFullyQualified($argv[1])){return $false}
  if([IO.Path]::GetFullPath($argv[1]) -ne $module){return $false}
 }elseif($proof.command_kind -eq 'EXACT_RELATIVE_MODULE_OUTSIDE_WITH_CWD'){
  if([IO.Path]::IsPathFullyQualified($argv[1]) -or [IO.Path]::GetFileName($argv[1].Replace([char]47,[char]92)) -ine 'server.mjs'){return $false}
  $read=[ExactCwdReader]::Get([int]$p.ProcessId)
  if($read.state -ne 'CWD_EXACT_READ'){return $false}
  $cwd=[IO.Path]::GetFullPath($read.cwd).TrimEnd('\')
  if($cwd -ne ([IO.Path]::GetFullPath([string]$proof.expected_cwd).TrimEnd('\'))){return $false}
  if($cwd -eq $Root -or $cwd.StartsWith($Root+'\',[StringComparison]::OrdinalIgnoreCase) -or -not(NoReparsePath $cwd)){return $false}
  if([IO.Path]::GetFullPath((Join-Path $cwd $argv[1])) -ne $module){return $false}
 }else{return $false}
 if($module -eq $Root -or $module.StartsWith($Root+'\',[StringComparison]::OrdinalIgnoreCase) -or -not(NoReparsePath $module)){return $false}
 foreach($receipt in @($r.source_receipt,$proof.public_daemon_provenance)){
  if(-not[IO.Path]::IsPathFullyQualified($receipt) -or -not(Test-Path -LiteralPath $receipt -PathType Leaf)){return $false}
 }
 return $true
}
