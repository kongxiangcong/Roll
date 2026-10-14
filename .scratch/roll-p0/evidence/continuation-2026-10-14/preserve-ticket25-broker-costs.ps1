$ErrorActionPreference = 'Stop'
$sourceBase = 'D:\dsh-proj\Roll\.scratch\worktrees\t25-production-inputs\.scratch'
$destinationBase = 'D:\dsh-proj\Roll\.roll-data\implementation-evidence\ticket25-broker-costs-20261014'
$receiptPath = 'D:\dsh-proj\Roll\.scratch\roll-p0\evidence\continuation-2026-10-14\ticket25-broker-costs-preservation.json'
if (Test-Path -LiteralPath $destinationBase) { throw 'Destination must be fresh' }
$runNames = @('t25-cost-red1','t25-cost-red2','t25-cost-red3','t25-cost-red4','t25-cost-red5','t25-cost-green1','t25-cost-green2','t25-cost-green3','t25-cost-green4','t25-cost-green5','t25-cost-green6')
$sourceExtended = '\\?\' + $sourceBase
$destinationExtended = '\\?\' + $destinationBase
$items = @()
foreach ($runName in $runNames) {
    $runRoot = $sourceExtended + '\' + $runName
    if (-not [IO.Directory]::Exists($runRoot)) { throw "Missing owned run $runName" }
    foreach ($file in [IO.Directory]::EnumerateFiles($runRoot, '*', [IO.SearchOption]::AllDirectories)) {
        $info = [IO.FileInfo]::new($file)
        if ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Unexpected reparse point' }
        if ($info.Name -match '^\.env($|\.)|^auth\.json$|credential|token') { throw 'Potential private file requires separate handling' }
        $relative = $file.Substring($sourceExtended.Length + 1)
        $beforeHash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash
        $items += [PSCustomObject]@{relative=$relative; bytes=$info.Length; before_sha256=$beforeHash; source=$file}
    }
}
[IO.Directory]::CreateDirectory($destinationExtended) | Out-Null
$verified = @()
foreach ($item in $items) {
    $target = $destinationExtended + '\' + $item.relative
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
    [IO.File]::Copy($item.source, $target, $false)
    $sourceAfter = (Get-FileHash -LiteralPath $item.source -Algorithm SHA256).Hash
    $destinationHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
    $destinationLength = [IO.FileInfo]::new($target).Length
    if ($sourceAfter -ne $item.before_sha256 -or $destinationHash -ne $item.before_sha256 -or $destinationLength -ne $item.bytes) { throw 'Source/destination mismatch' }
    $verified += [PSCustomObject]@{relative=$item.relative;bytes=$item.bytes;before_sha256=$item.before_sha256;source_after_sha256=$sourceAfter;destination_sha256=$destinationHash;destination_bytes=$destinationLength}
}
$receipt = [PSCustomObject]@{timestamp_utc=[DateTime]::UtcNow.ToString('o'); source=$sourceBase; destination=$destinationBase; run_names=$runNames; file_count=$verified.Count; bytes=($verified|Measure-Object bytes -Sum).Sum; mismatches=0; source_deleted=$false; worktree_removed=$false; exact_owned_python_process_count=0; process_metadata_check='Elevated CIM Win32_Process Python commands matching t25-production-inputs or t25-cost-* returned zero. No processes killed.'; files=$verified}
$receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $receiptPath -Encoding utf8
[PSCustomObject]@{receipt=$receiptPath;file_count=$receipt.file_count;bytes=$receipt.bytes;mismatches=0;source_deleted=$false} | ConvertTo-Json
