[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location (Join-Path $root 'backend')
try { & uv sync --frozen; if ($LASTEXITCODE -ne 0) { throw 'Locked backend install failed' } } finally { Pop-Location }
Push-Location (Join-Path $root 'frontend')
try {
    & npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Locked frontend install failed' }
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
} finally { Pop-Location }
Write-Output 'Installed. Run ./scripts/start-roll.ps1; optional providers are configured separately.'
