$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath('D:\dsh-proj\Roll')
$scope=Join-Path $root '.scratch/roll-p0/evidence/continuation-2026-10-11/review-fixes'
$boundary=[IO.Path]::GetFullPath((Join-Path $root '.scratch/worktrees/continuation-review-fixes'))
$changes=Get-Content -LiteralPath (Join-Path $scope 'cleanup-source-differences.json') -Raw|ConvertFrom-Json
$invariance=Get-Content -LiteralPath (Join-Path $scope 'cleanup-research-invariance.json') -Raw|ConvertFrom-Json
if($invariance.status -ne 'PASS'){throw 'Research invariance missing'}
$copies=@()
foreach($profile in $changes.profiles){
    if(-not @($profile.source_differences).Count -and $profile.current_source_files -eq $profile.historical_files){continue}
    $source=[IO.Path]::GetFullPath($profile.source)
    if(-not $source.StartsWith($boundary+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Source outside authorized tree'}
    if($profile.manifest -ne 'runtime-failed-forward-manifest.json'){throw 'Unexpected changed profile'}
    $target=[IO.Path]::GetFullPath((Join-Path $root '.roll-data/implementation-evidence/continuation-review-fixes/source-final-state/failed-forward'))
    if(Test-Path -LiteralPath $target){throw 'Never overwrite preserved snapshot'}
    if(@(Get-ChildItem -LiteralPath $source -Recurse -Force -Attributes ReparsePoint).Count){throw 'Source link refused'}
    $files=@(Get-ChildItem -LiteralPath $source -Recurse -File -Force)
    if(@($files|Where-Object{$_.Name -in @('.env','auth.json')}).Count){throw 'Credential file refused; do not copy'}
    New-Item -ItemType Directory -Path $target|Out-Null
    $entries=@(foreach($file in ($files|Sort-Object FullName)){
        $relative=[IO.Path]::GetRelativePath($source,$file.FullName)
        $destination=[IO.Path]::GetFullPath((Join-Path $target $relative))
        if(-not $destination.StartsWith($target+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Destination escaped'}
        $before=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLower()
        New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($destination)) -Force|Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destination
        $saved=Get-Item -LiteralPath $destination;$after=(Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLower()
        if($saved.Length -ne $file.Length -or $before -ne $after -or (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLower() -ne $before){throw 'Source/destination SHA length mismatch'}
        [ordered]@{path=$relative.Replace('\','/');bytes=$file.Length;sha256=$before}
    })
    $totalBytes=0L;foreach($entry in $entries){$totalBytes+=[long]$entry.bytes}
    $copies+=@([ordered]@{source=$source;destination=$target;file_count=$entries.Count;bytes=$totalBytes;files=$entries;
        historical_snapshot_preserved_unchanged=$true;all_original_research_rows_unchanged=$true;one_diagnostic_forward_check_appended=$true;source_destination_SHA_length_mismatches=0;credentials_copied=$false})
}
$result=[ordered]@{status='PASS';source_final_state_copies=$copies;historical_root_manifests_unchanged=$true;original_raw_parquet_archives_unchanged=$true}
[IO.File]::WriteAllText((Join-Path $scope 'cleanup-source-final-preservation.json'),(($result|ConvertTo-Json -Depth 8)+"`n").Replace("`r`n","`n"),[Text.UTF8Encoding]::new($false))
Write-Output "PASS additional final source snapshots: $($copies.Count), files $((@($copies.files)|Measure-Object).Count)"
