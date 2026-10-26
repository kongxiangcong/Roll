$ErrorActionPreference = 'Stop'
$sourceBase = 'D:\dsh-proj\Roll\.scratch\worktrees\t25-closed-funding'
$destinationBase = 'D:\dsh-proj\Roll\.roll-data\implementation-evidence\ticket25-closed-funding-20261014'
$receiptPath = 'D:\dsh-proj\Roll\.scratch\roll-p0\evidence\continuation-2026-10-14\ticket25-closed-funding-preservation.json'
if (Test-Path -LiteralPath $destinationBase) { throw 'Destination must be fresh' }
Push-Location -LiteralPath $sourceBase
try {
    $untracked = @(git -c core.quotepath=false ls-files --others --exclude-standard)
    $ignored = @(git -c core.quotepath=false ls-files --others --ignored --exclude-standard)
    $names = @($untracked + $ignored | Sort-Object -Unique)
    $trackedChanges = @(git status --short --untracked-files=no)
    if ($trackedChanges.Count) { throw 'Tracked source tree must be clean' }
} finally { Pop-Location }
$sourceExtended = '\\?\' + $sourceBase
$destinationExtended = '\\?\' + $destinationBase
$items = @()
foreach ($name in $names) {
    if ($name -notmatch '^\.scratch/(closed-(red|green)\.txt|t25-closed-(red|green)/)|^(backend/)?\.pytest_cache/|^backend/.*/__pycache__/|^backend/__pycache__/') { throw "Unexpected generated namespace: $name" }
    $relative = $name.Replace('/', '\')
    $file = $sourceExtended + '\' + $relative
    $info = [IO.FileInfo]::new($file)
    if ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Unexpected reparse point' }
    if ($info.Name -match '^\.env($|\.)|^auth\.json$|credential|token') { throw 'Potential private file requires separate handling' }
    $items += [PSCustomObject]@{relative=$relative; bytes=$info.Length; before_sha256=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash; source=$file}
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
$receipt = [PSCustomObject]@{timestamp_utc=[DateTime]::UtcNow.ToString('o');source=$sourceBase;destination=$destinationBase;head='7311e68508a9f7d54043210f40f98da92f696d87';file_count=$verified.Count;bytes=($verified|Measure-Object bytes -Sum).Sum;untracked_count=$untracked.Count;ignored_count=$ignored.Count;mismatches=0;source_deleted=$false;worktree_removed=$false;exact_owned_python_process_count=0;process_metadata_check='Elevated CIM Python command metadata matching t25-closed-funding/t25-closed-red/t25-closed-green returned zero; none killed.';known_links=@();link_metadata='frontend/node_modules and backend/.venv absent; no junctions created for this tree';files=$verified}
$receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $receiptPath -Encoding utf8
[PSCustomObject]@{receipt=$receiptPath;file_count=$receipt.file_count;bytes=$receipt.bytes;mismatches=0;source_deleted=$false} | ConvertTo-Json
