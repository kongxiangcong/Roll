# Pure bounded worker pool. Input paths have already passed parent AddExpected/private gates.
function VerifyExpectedParallel($rows,[string]$SourceFile){
 $tokens=$null;$parseErrors=$null
 $ast=[Management.Automation.Language.Parser]::ParseFile($SourceFile,[ref]$tokens,[ref]$parseErrors)
 if($parseErrors.Count){throw 'Bound executor parser refused'}
 $names=@('N','Ancestors','Stat','Proof','VerifyExpected')
 $functions=@($ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -in $names},$true))
 if($functions.Count -ne 5 -or @($functions.Name|Sort-Object -Unique).Count -ne 5){throw 'Exact five worker function definitions required'}
 $definitions=@($functions|ForEach-Object {$_.Extent.Text})
 $parts=@([Collections.Generic.List[object]]::new(),[Collections.Generic.List[object]]::new(),[Collections.Generic.List[object]]::new(),[Collections.Generic.List[object]]::new())
 $index=0;foreach($row in $rows){$parts[$index % 4].Add($row);$index++}
 $pool=[RunspaceFactory]::CreateRunspacePool(1,4);$pool.Open()
 $jobs=[Collections.Generic.List[object]]::new();$collected=[Collections.Generic.List[object]]::new()
 try{
  foreach($part in $parts){
   if(-not $part.Count){continue}
   $ps=[powershell]::Create();$ps.RunspacePool=$pool
   $null=$ps.AddScript('param($defs,$part) $ErrorActionPreference="Stop";Set-StrictMode -Version 3;foreach($d in $defs){. ([scriptblock]::Create($d))};VerifyExpected $part').AddArgument($definitions).AddArgument($part.ToArray())
   $jobs.Add(@{ps=$ps;handle=$ps.BeginInvoke();count=$part.Count})
  }
  foreach($job in $jobs){
   $result=@($job.ps.EndInvoke($job.handle))
   if($job.ps.Streams.Error.Count -or $result.Count -ne $job.count){throw 'Bounded byte worker failed or returned wrong count'}
   foreach($entry in $result){$collected.Add($entry)}
  }
  if($collected.Count -ne $index){throw 'Bounded byte proof union count differs'}
  $collected.ToArray()
 }finally{
  foreach($job in $jobs){$job.ps.Dispose()}
  $pool.Close();$pool.Dispose()
 }
}
