[CmdletBinding()]
param(
    [switch]$Status,
    [switch]$Stop,
    [string]$DataDirectory = (Join-Path $env:LOCALAPPDATA 'Roll'),
    [ValidateRange(1024, 65535)][int]$ApiPort = 8010,
    [ValidateRange(1024, 65535)][int]$WebPort = 5173,
    [string]$EnvironmentFile,
    [string]$CodexAuthFile,
    [string]$AksharePython,
    [string]$TrafilaturaPython
)

$ErrorActionPreference = 'Stop'
$sourceRoot = Split-Path $PSScriptRoot -Parent
$DataDirectory = [IO.Path]::GetFullPath($DataDirectory)
$logDirectory = Join-Path $DataDirectory 'logs'
$receiptPath = Join-Path $logDirectory "services-$ApiPort-$WebPort.json"
$apiUrl = "http://127.0.0.1:$ApiPort"
$webUrl = "http://127.0.0.1:$WebPort"
if ($ApiPort -eq $WebPort) { throw 'API and web ports must differ.' }

function Get-Listener([int]$Port) {
    @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object LocalPort -eq $Port)
}

function Get-Identity([int]$ProcessId) {
    $process = Get-Process -Id $ProcessId -ErrorAction Stop
    @{ pid = $process.Id; started_ticks = $process.StartTime.ToUniversalTime().Ticks }
}

function Test-Identity($Identity) {
    if (-not $Identity) { return $false }
    try {
        $current = Get-Identity $Identity.pid
        return $current.started_ticks -eq $Identity.started_ticks
    } catch { return $false }
}

function Read-JsonUrl([string]$Url) {
    Invoke-RestMethod -Uri $Url -TimeoutSec 3
}

function Save-Receipt {
    $receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
}

function Wait-Service([scriptblock]$Probe, [string]$Name) {
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        try { if (& $Probe) { return } } catch { }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "$Name did not become ready within 30 seconds. Inspect logs in $logDirectory. Started processes are retained; rerun -Status before retrying."
}

function Show-Status {
    $api = $null
    $worker = $null
    $webReady = $false
    if ((Test-Identity $receipt.api) -and (@(Get-Listener $ApiPort).OwningProcess -contains $receipt.api.pid)) {
        try {
            $api = Read-JsonUrl "$apiUrl/api/health"
            $worker = Read-JsonUrl "$apiUrl/api/reviews/health"
        } catch { }
    }
    if ((Test-Identity $receipt.web) -and (@(Get-Listener $WebPort).OwningProcess -contains $receipt.web.pid)) {
        try { $webReady = (Invoke-WebRequest $webUrl -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch { }
    }
    [pscustomobject]@{
        url = $webUrl
        data_directory = $DataDirectory
        api = if ($api.status -eq 'ok' -and $api.runtime_role -eq 'API') { 'RUNNING' } else { 'NOT_READY' }
        worker = if ($worker) { $worker.worker_state } else { 'UNKNOWN' }
        web = if ($webReady) { 'RUNNING' } else { 'NOT_READY' }
        receipt = $receiptPath
    }
}

$receipt = @{ source_root = $sourceRoot; data_directory = $DataDirectory; api = $null; worker = $null; web = $null }
if (Test-Path -LiteralPath $receiptPath) {
    $saved = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
    if ($saved.source_root -ne $sourceRoot -or $saved.data_directory -ne $DataDirectory) {
        throw 'Receipt belongs to another source checkout or data directory.'
    }
    foreach ($name in 'api', 'worker', 'web') { $receipt[$name] = $saved.$name }
}
if ($Status) { Show-Status; return }
if ($Stop) {
    # Only terminate verified process trees owned by this launch receipt.
    foreach ($role in 'worker', 'api', 'web') {
        if (Test-Identity $receipt[$role]) {
            & taskkill.exe /PID $receipt[$role].pid /T /F | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Could not stop recorded $role process." }
        }
    }
    Show-Status
    return
}

$python = Join-Path $sourceRoot 'backend/.venv/Scripts/python.exe'
$vite = Join-Path $sourceRoot 'frontend/node_modules/vite/bin/vite.js'
foreach ($path in $python, $vite) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing dependency: $path. Follow README installation instructions." }
}
$node = (Get-Command node -ErrorAction Stop).Source
if (-not $AksharePython -and -not $env:ROLL_AKSHARE_PYTHON) {
    $candidate = Join-Path $sourceRoot '.scratch/rce-runtime/akshare/Scripts/python.exe'
    if (Test-Path -LiteralPath $candidate -PathType Leaf) { $AksharePython = $candidate }
}
if (-not $TrafilaturaPython -and -not $env:ROLL_TRAFILATURA_PYTHON) {
    $candidate = Join-Path $sourceRoot '.scratch/rce-runtime/trafilatura/Scripts/python.exe'
    if (Test-Path -LiteralPath $candidate -PathType Leaf) { $TrafilaturaPython = $candidate }
}
foreach ($path in $AksharePython, $TrafilaturaPython) {
    if ($path -and -not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing observation runtime: $path" }
}
foreach ($path in $EnvironmentFile, $CodexAuthFile) {
    if ($path -and -not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Configured file does not exist: $path" }
}
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
# Serialize launch attempts for this account directory. The application still owns its worker lease.
$launchLock = [IO.File]::Open((Join-Path $logDirectory 'launcher.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
$environmentNames = @('ROLL_ENV', 'ROLL_DATA_DIR', 'ROLL_RUNTIME_ROLE', 'ROLL_API_PORT', 'ROLL_ENV_FILE', 'ROLL_CODEX_AUTH_FILE', 'ROLL_AKSHARE_PYTHON', 'ROLL_TRAFILATURA_PYTHON')
$previous = @{}
foreach ($name in $environmentNames) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    foreach ($entry in @(@{ role='api'; port=$ApiPort }, @{ role='web'; port=$WebPort })) {
        foreach ($listener in (Get-Listener $entry.port)) {
            if (-not (Test-Identity $receipt[$entry.role]) -or $listener.OwningProcess -ne $receipt[$entry.role].pid) {
                throw "Port $($entry.port) is already occupied by a process not recorded by this launcher. No process was stopped."
            }
        }
    }
    $env:ROLL_ENV = 'local'
    $env:ROLL_DATA_DIR = $DataDirectory
    $env:ROLL_API_PORT = [string]$ApiPort
    if ($EnvironmentFile) { $env:ROLL_ENV_FILE = [IO.Path]::GetFullPath($EnvironmentFile) }
    if ($CodexAuthFile) { $env:ROLL_CODEX_AUTH_FILE = [IO.Path]::GetFullPath($CodexAuthFile) }
    if ($AksharePython) { $env:ROLL_AKSHARE_PYTHON = [IO.Path]::GetFullPath($AksharePython) }
    if ($TrafilaturaPython) { $env:ROLL_TRAFILATURA_PYTHON = [IO.Path]::GetFullPath($TrafilaturaPython) }
    $stamp = [DateTime]::Now.ToString('yyyyMMdd-HHmmss-fff')
    if (-not (Test-Identity $receipt.api)) {
        $env:ROLL_RUNTIME_ROLE = 'API'
        $process = Start-Process $python -ArgumentList @('-m','uvicorn','roll.app:create_app','--factory','--host','127.0.0.1','--port',"$ApiPort") -WorkingDirectory (Join-Path $sourceRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory "api-$stamp.out.log") -RedirectStandardError (Join-Path $logDirectory "api-$stamp.err.log") -PassThru
        $receipt.api = Get-Identity $process.Id
        Save-Receipt
    }
    Wait-Service { $health = Read-JsonUrl "$apiUrl/api/health"; $health.status -eq 'ok' -and $health.runtime_role -eq 'API' } 'API'
    # On Windows the venv launcher may spawn the Python process that owns the socket.
    $receipt.api = Get-Identity (@(Get-Listener $ApiPort)[0].OwningProcess)
    Save-Receipt
    $workerHealth = Read-JsonUrl "$apiUrl/api/reviews/health"
    if ($workerHealth.worker_state -ne 'RUNNING') {
        if (-not (Test-Identity $receipt.worker)) {
            $env:ROLL_RUNTIME_ROLE = 'WORKER'
            $process = Start-Process $python -ArgumentList @('-m','roll.worker') -WorkingDirectory (Join-Path $sourceRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory "worker-$stamp.out.log") -RedirectStandardError (Join-Path $logDirectory "worker-$stamp.err.log") -PassThru
            $receipt.worker = Get-Identity $process.Id
            Save-Receipt
        }
        Wait-Service { (Read-JsonUrl "$apiUrl/api/reviews/health").worker_state -eq 'RUNNING' } 'Worker'
    }
    $workerHealth = Read-JsonUrl "$apiUrl/api/reviews/health"
    $receipt.worker = Get-Identity $workerHealth.worker.host_owner.pid
    Save-Receipt
    if (-not (Test-Identity $receipt.web)) {
        $process = Start-Process $node -ArgumentList @(('"'+$vite+'"'),'--host','127.0.0.1','--port',"$WebPort",'--strictPort') -WorkingDirectory (Join-Path $sourceRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory "web-$stamp.out.log") -RedirectStandardError (Join-Path $logDirectory "web-$stamp.err.log") -PassThru
        $receipt.web = Get-Identity $process.Id
        Save-Receipt
    }
    Wait-Service { (Invoke-WebRequest $webUrl -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } 'Web'
    Show-Status
} finally {
    foreach ($name in $environmentNames) {
        if ($null -eq $previous[$name]) { Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue }
        else { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    }
    $launchLock.Dispose()
}
