<#
.SYNOPSIS
    Start kb — backend (FastAPI) and frontend (Vite) with one command.
.DESCRIPTION
    Finds Python, verifies packages, kills port conflicts,
    launches both services, and prints the URL when ready.
.PARAMETER OpenBrowser
    Open the browser automatically after startup.
.PARAMETER SkipWatch
    Skip file watcher even if watch_dir is configured.
.PARAMETER BackendPort
    Override backend port (default 8420).
.PARAMETER FrontendPort
    Override frontend port (default 3030).
.EXAMPLE
    .\scripts\start.ps1
    .\scripts\start.ps1 -OpenBrowser -SkipWatch
#>

param(
    [switch]$OpenBrowser,
    [switch]$SkipWatch,
    [int]$BackendPort = 8420,
    [int]$FrontendPort = 3030
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProjectRoot ".kb\logs"
$null = New-Item -ItemType Directory -Force -Path $LogDir

# ── 1. Find Python ──────────────────────────────────────────────
function Find-Python {
    $candidates = @(
        (Get-Command python -ErrorAction SilentlyContinue | ForEach-Object Source),
        (Get-Command python3 -ErrorAction SilentlyContinue | ForEach-Object Source),
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:APPDATA\uv\python\cpython-3.13.*-windows-x86_64-none\bin\python3.exe",
        "C:\Python313\python.exe"
    )

    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) {
            $result = & $p --version 2>&1
            if ($LASTEXITCODE -eq 0) { return $p }
        }
    }

    $installed = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
    if ($installed) { return $installed.FullName }

    throw "Python not found. Install from https://www.python.org/downloads/"
}

$Python = Find-Python
Write-Host "[kb] Python: $Python" -ForegroundColor Cyan

# ── 2. Verify packages ──────────────────────────────────────────
$required = @("uvicorn", "fastapi", "typer", "rich")
$missing = @()
foreach ($pkg in $required) {
    & $Python -c "import $pkg" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { $missing += $pkg }
}
if ($missing) {
    Write-Host "[kb] Missing packages: $($missing -join ', ')" -ForegroundColor Yellow
    Write-Host "[kb] Run: pip install -r requirements.txt" -ForegroundColor Yellow
}

# ── 3. Kill stale processes on target ports ─────────────────────
function Free-Port($port) {
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
        Where-Object { $_.OwningProcess -ne 0 }
    if (-not $conn) { return }
    $pids = $conn | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($id in $pids) {
        $proc = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "[kb] Port $port occupied by $($proc.ProcessName) (PID $id). Killing..." -ForegroundColor Yellow
            Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Milliseconds 500
}

Free-Port $BackendPort
Free-Port $FrontendPort

# ── 4. Start backend ────────────────────────────────────────────
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$ServerLog = Join-Path $LogDir "server.log"

$ServeScript = Join-Path $PSScriptRoot "_serve.py"
$backendArgList = @($ServeScript, "serve", "--host", "127.0.0.1", "--port", $BackendPort)
if ($SkipWatch) { $backendArgList += "--skip-watch" }

Write-Host "[kb] Starting backend on port ${BackendPort}..." -ForegroundColor Cyan

$backendProc = Start-Process -FilePath $Python `
    -ArgumentList $backendArgList `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput $ServerLog `
    -RedirectStandardError "$LogDir\server-error.log" `
    -WindowStyle Hidden `
    -PassThru

# ── 5. Start frontend ───────────────────────────────────────────
$ViteLog = Join-Path $LogDir "vite.log"

$NpxCmd = if (Get-Command npx.cmd -ErrorAction SilentlyContinue) {
    (Get-Command npx.cmd).Source
} elseif (Get-Command npx -ErrorAction SilentlyContinue) {
    (Get-Command npx).Source
} else {
    throw "npx not found. Install Node.js from https://nodejs.org/"
}

Write-Host "[kb] Starting frontend on port ${FrontendPort}..." -ForegroundColor Cyan

$frontendProc = Start-Process -FilePath $NpxCmd `
    -ArgumentList @("vite", "--host", "127.0.0.1", "--port", $FrontendPort, "--strictPort") `
    -WorkingDirectory (Join-Path $ProjectRoot "web") `
    -RedirectStandardOutput $ViteLog `
    -RedirectStandardError "$LogDir\vite-error.log" `
    -WindowStyle Hidden `
    -PassThru

# ── 6. Health check ─────────────────────────────────────────────
Write-Host "[kb] Waiting for services..." -ForegroundColor Cyan

$backendUp = $false
$frontendUp = $false
$timeout = 60
$elapsed = 0

while ((-not $backendUp -or -not $frontendUp) -and $elapsed -lt $timeout) {
    Start-Sleep -Seconds 2
    $elapsed += 2

    if (-not $backendUp) {
        try {
            $null = Invoke-WebRequest -Uri "http://127.0.0.1:${BackendPort}" -TimeoutSec 2 -ErrorAction SilentlyContinue
            $backendUp = $true
            Write-Host "[kb] Backend ready (${elapsed}s)" -ForegroundColor Green
        } catch {}
    }
    if (-not $frontendUp) {
        try {
            $null = Invoke-WebRequest -Uri "http://127.0.0.1:${FrontendPort}" -TimeoutSec 2 -ErrorAction SilentlyContinue
            $frontendUp = $true
            Write-Host "[kb] Frontend ready (${elapsed}s)" -ForegroundColor Green
        } catch {}
    }

    if ($backendProc.HasExited -and -not $backendUp) {
        Write-Host "[kb] Backend failed to start. Check $ServerLog" -ForegroundColor Red
        # Print last lines of error log
        if (Test-Path "$LogDir\server-error.log") {
            Get-Content "$LogDir\server-error.log" -Tail 10 | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        }
        break
    }
    if ($frontendProc.HasExited -and -not $frontendUp) {
        Write-Host "[kb] Frontend failed to start. Check $ViteLog" -ForegroundColor Red
        if (Test-Path "$LogDir\vite-error.log") {
            Get-Content "$LogDir\vite-error.log" -Tail 10 | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        }
        break
    }
}

# ── 7. Report ────────────────────────────────────────────────────
if ($backendUp -and $frontendUp) {
    Write-Host ""
    Write-Host "  kb is running!" -ForegroundColor Green
    Write-Host "  Frontend : http://127.0.0.1:${FrontendPort}" -ForegroundColor White
    Write-Host "  Backend  : http://127.0.0.1:${BackendPort}" -ForegroundColor White
    Write-Host "  Logs     : $LogDir" -ForegroundColor DarkGray
    Write-Host ""

    if ($OpenBrowser) {
        Start-Process "http://127.0.0.1:${FrontendPort}"
    }
} elseif ($backendUp) {
    Write-Host "[kb] Backend running, frontend did not start." -ForegroundColor Yellow
} elseif ($frontendUp) {
    Write-Host "[kb] Frontend running, backend did not start." -ForegroundColor Yellow
} else {
    Write-Host "[kb] Neither service started. Check logs in $LogDir" -ForegroundColor Red
    exit 1
}
