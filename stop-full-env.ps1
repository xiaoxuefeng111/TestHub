# Tongdaxin Testing Platform full environment stop script for Windows PowerShell 5.1+
# Stops processes started by start-full-env.ps1 and project-local Django/Celery/Vite processes.

$ErrorActionPreference = 'Continue'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $Root '.run-logs'
$PidFile = Join-Path $LogDir 'full-env-pids.json'

function Stop-PidSafe {
    param(
        [int]$ProcessId,
        [string]$Name = ''
    )
    try {
        $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "[STOP] $Name pid=$ProcessId" -ForegroundColor Yellow
            Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        }
    } catch {
        Write-Host "[WARN] Failed to stop pid=$ProcessId : $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

function Find-ProjectProcess {
    param([string]$Pattern)
    $escapedRoot = [Regex]::Escape($Root)
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and $_.CommandLine -match $escapedRoot -and $_.CommandLine -match $Pattern
    }
}

Write-Host '=== Tongdaxin Testing Platform full environment stop ===' -ForegroundColor Cyan
Write-Host "Root: $Root"

# Stop processes recorded by start-full-env.ps1.
if (Test-Path $PidFile) {
    try {
        $state = Get-Content -Path $PidFile -Raw | ConvertFrom-Json
        foreach ($p in $state.processes) {
            if ($p.pid) {
                Stop-PidSafe -ProcessId ([int]$p.pid) -Name $p.name
            }
        }
    } catch {
        Write-Host "[WARN] Could not read PID state: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host '[INFO] PID state file not found; using project process fallback.'
}

# Fallback: stop project-local Django, Celery and Vite commands.
$patterns = @(
    @{ name = 'Tongdaxin Django Backend'; pattern = 'manage\.py\s+runserver\s+127\.0\.0\.1:8000' },
    @{ name = 'Tongdaxin Celery Worker'; pattern = 'celery.*-A\s+backend|celery.*backend\s+worker' },
    @{ name = 'Tongdaxin Vite Frontend'; pattern = 'vite.*--host\s+127\.0\.0\.1\s+--port\s+3000|npm.*run\s+dev.*--host\s+127\.0\.0\.1\s+--port\s+3000' }
)

foreach ($item in $patterns) {
    $matches = Find-ProjectProcess -Pattern $item.pattern
    foreach ($m in $matches) {
        Stop-PidSafe -ProcessId ([int]$m.ProcessId) -Name $item.name
    }
}

# Redis is intentionally not killed by fallback because it may be shared by other projects.
# If Redis was launched in its own visible window by start-full-env.ps1, the recorded PowerShell window PID is stopped above.

if (Test-Path $PidFile) {
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

Write-Host 'Done.' -ForegroundColor Green
