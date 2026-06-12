# Tongdaxin Testing Platform full environment startup script for Windows PowerShell 5.1+
# Starts: Redis (if available and needed), Django backend, Celery worker, Vite frontend.

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $Root '.run-logs'
$PidFile = Join-Path $LogDir 'full-env-pids.json'
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Celery = Join-Path $Root '.venv\Scripts\celery.exe'

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

function Test-PortOpen {
    param(
        [string]$HostName = '127.0.0.1',
        [int]$Port
    )
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        $ok = $async.AsyncWaitHandle.WaitOne(500, $false)
        if ($ok) { $client.EndConnect($async) }
        $client.Close()
        return $ok
    } catch {
        return $false
    }
}

function Wait-PortOpen {
    param(
        [string]$Name,
        [int]$Port,
        [int]$Seconds = 15
    )
    for ($i = 0; $i -lt $Seconds; $i++) {
        if (Test-PortOpen -Port $Port) {
            Write-Host "[OK] $Name is listening on port $Port" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 1
    }
    Write-Host "[WARN] $Name is not listening on port $Port after $Seconds seconds" -ForegroundColor Yellow
    return $false
}

function Find-ProjectProcess {
    param([string]$Pattern)
    $escapedRoot = [Regex]::Escape($Root)
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and $_.CommandLine -match $escapedRoot -and $_.CommandLine -match $Pattern
    }
}

function Start-VisiblePowerShell {
    param(
        [string]$Title,
        [string]$Command
    )
    $windowCommand = "`$Host.UI.RawUI.WindowTitle = '$Title'; Set-Location -LiteralPath '$Root'; $Command"
    $p = Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', $windowCommand) -WorkingDirectory $Root -PassThru
    Write-Host "[START] $Title pid=$($p.Id)" -ForegroundColor Cyan
    return @{ name = $Title; pid = $p.Id; startedByScript = $true }
}

Write-Host '=== Tongdaxin Testing Platform full environment startup ===' -ForegroundColor Cyan
Write-Host "Root: $Root"

if (-not (Test-Path $Python)) { throw "Python virtualenv not found: $Python" }
if (-not (Test-Path $Celery)) { throw "Celery executable not found: $Celery" }
if (-not (Test-Path (Join-Path $Root 'manage.py'))) { throw 'manage.py not found. Run this script from project root.' }
if (-not (Test-Path (Join-Path $Root 'frontend\package.json'))) { throw 'frontend/package.json not found.' }

$started = @()

# Redis
$redisAvailable = Test-PortOpen -Port 6379
if ($redisAvailable) {
    Write-Host '[OK] Redis already listening on 127.0.0.1:6379' -ForegroundColor Green
} else {
    $redisCommand = Get-Command 'redis-server' -ErrorAction SilentlyContinue
    if ($redisCommand) {
        $started += Start-VisiblePowerShell -Title 'Tongdaxin Redis' -Command "& '$($redisCommand.Source)'"
        $redisAvailable = Wait-PortOpen -Name 'Redis' -Port 6379 -Seconds 15
    } else {
        Write-Host '[WARN] Redis is not running and redis-server was not found in PATH.' -ForegroundColor Yellow
        Write-Host '       APP automation execution needs Redis + Celery; install/start Redis, then rerun this script.' -ForegroundColor Yellow
    }
}

# Django backend
if (Test-PortOpen -Port 8000) {
    Write-Host '[OK] Django backend already listening on 127.0.0.1:8000' -ForegroundColor Green
} else {
    $started += Start-VisiblePowerShell -Title 'Tongdaxin Django Backend' -Command "& '$Python' manage.py runserver 127.0.0.1:8000"
    Wait-PortOpen -Name 'Django backend' -Port 8000 -Seconds 20 | Out-Null
}

# Celery worker
$celeryProcess = Find-ProjectProcess -Pattern 'celery.*-A\s+backend|celery.*backend\s+worker'
if ($celeryProcess) {
    Write-Host "[OK] Celery worker already running pid=$($celeryProcess[0].ProcessId)" -ForegroundColor Green
} elseif ($redisAvailable) {
    $started += Start-VisiblePowerShell -Title 'Tongdaxin Celery Worker' -Command "& '$Celery' -A backend worker -l info --pool=solo"
} else {
    Write-Host '[WARN] Celery worker was not started because Redis is unavailable.' -ForegroundColor Yellow
}

# Vite frontend
if (Test-PortOpen -Port 3000) {
    Write-Host '[OK] Vite frontend already listening on 127.0.0.1:3000' -ForegroundColor Green
} else {
    $started += Start-VisiblePowerShell -Title 'Tongdaxin Vite Frontend' -Command "npm --prefix frontend run dev -- --host 127.0.0.1 --port 3000"
    Wait-PortOpen -Name 'Vite frontend' -Port 3000 -Seconds 20 | Out-Null
}

# Save only processes launched by this script.
$state = [ordered]@{
    root = $Root
    startedAt = (Get-Date).ToString('s')
    processes = $started
}
$state | ConvertTo-Json -Depth 5 | Set-Content -Path $PidFile -Encoding UTF8

Write-Host ''
Write-Host '=== Startup summary ===' -ForegroundColor Cyan
Write-Host ("Redis 6379 : {0}" -f ($(if (Test-PortOpen -Port 6379) { 'OK' } else { 'NOT RUNNING' })))
Write-Host ("Backend 8000: {0}" -f ($(if (Test-PortOpen -Port 8000) { 'OK' } else { 'NOT RUNNING' })))
Write-Host ("Frontend 3000: {0}" -f ($(if (Test-PortOpen -Port 3000) { 'OK' } else { 'NOT RUNNING' })))
$celeryNow = Find-ProjectProcess -Pattern 'celery.*-A\s+backend|celery.*backend\s+worker'
Write-Host ("Celery      : {0}" -f ($(if ($celeryNow) { 'OK' } else { 'NOT RUNNING' })))
Write-Host "PID state   : $PidFile"
Write-Host ''
Write-Host 'Open http://127.0.0.1:3000 to use Tongdaxin Testing Platform.' -ForegroundColor Green
Write-Host 'Use .\stop-full-env.ps1 to stop processes launched by this script.' -ForegroundColor Green
