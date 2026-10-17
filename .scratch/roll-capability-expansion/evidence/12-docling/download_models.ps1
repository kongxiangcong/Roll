$ErrorActionPreference='Continue'
$exe='D:\dsh-proj\Roll\.scratch\rce-runtime\docling\Scripts\docling-tools.exe'
$art='D:\dsh-proj\Roll\.scratch\rce-runtime\docling-cache\artifacts'
$log='D:\dsh-proj\Roll\.scratch\roll-capability-expansion\evidence\12-docling\model-prefetch02.log'
New-Item -ItemType Directory -Force -Path $art | Out-Null
$env:HTTPS_PROXY='http://127.0.0.1:7890'; $env:HTTP_PROXY='http://127.0.0.1:7890'; $env:NO_PROXY='127.0.0.1,localhost'
$env:HF_HOME='D:\dsh-proj\Roll\.scratch\rce-runtime\docling-cache\hf'
$env:HF_HUB_DISABLE_TELEMETRY='1'
$started=Get-Date
"STARTED=$($started.ToString('o'))" | Out-File -FilePath $log -Encoding utf8
& $exe models download layout tableformer -o $art *>> $log
"EXIT=$LASTEXITCODE ELAPSED=$(((Get-Date)-$started).TotalSeconds)" | Out-File -FilePath $log -Append -Encoding utf8
