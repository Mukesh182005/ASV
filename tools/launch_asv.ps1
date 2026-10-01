#!/usr/bin/env pwsh
<#
.SYNOPSIS
    ASV — One-Click System Launcher
    Starts backend + frontend together, with optional live GUI.

.USAGE
    # Start everything (backend + frontend)
    .\tools\launch_asv.ps1

    # Also open the live detector GUI (requires ESP32 on COM5)
    .\tools\launch_asv.ps1 -LiveGUI

    # Specify a different COM port for the live GUI
    .\tools\launch_asv.ps1 -LiveGUI -Port COM3

.NOTES
    Run from the repo root. Keep this window open — closing it stops the servers.
    Frontend: http://localhost:3000
    Backend:  http://localhost:8000
#>
param(
    [switch]$LiveGUI,
    [string]$Port = "COM8",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000
)

$REPO = Split-Path -Parent $PSScriptRoot
$ErrorActionPreference = "Stop"

function Write-Header($text) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
}

function Kill-Port($port) {
    $procId = (netstat -ano | Select-String ":$port\s.*LISTENING" | 
            ForEach-Object { ($_ -split "\s+")[-1] } | Select-Object -First 1)
    if ($procId) {
        try { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }
        catch {}
        Write-Host "  Freed port $port (was PID $procId)" -ForegroundColor Yellow
    }
}

Write-Header "ASV — A Silent Voice | System Launcher"
Write-Host ""
Write-Host "  Repo:     $REPO" -ForegroundColor Gray
Write-Host "  Backend:  http://localhost:$BackendPort" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:$FrontendPort" -ForegroundColor Green
if ($LiveGUI) {
    Write-Host "  Live GUI: enabled (port $Port)" -ForegroundColor Magenta
}
Write-Host ""

# ─── Free ports ──────────────────────────────────────────────────────────────
Write-Host "Freeing ports..." -ForegroundColor Gray
Kill-Port $BackendPort
Kill-Port $FrontendPort

# ─── Backend ─────────────────────────────────────────────────────────────────
Write-Header "Starting Backend (FastAPI / uvicorn)"
$backendLog = "$REPO\scratch\backend.log"
New-Item -ItemType Directory -Force -Path "$REPO\scratch" | Out-Null

$backendJob = Start-Job -ScriptBlock {
    param($repo, $port, $log)
    Set-Location $repo
    python -m uvicorn backend.main:app --port $port --log-level info 2>&1 | Tee-Object -FilePath $log
} -ArgumentList $REPO, $BackendPort, $backendLog

Write-Host "  Backend job started (ID $($backendJob.Id))" -ForegroundColor Green
Write-Host "  Logs → $backendLog" -ForegroundColor Gray

# Wait for backend to be ready (up to 15 s)
Write-Host "  Waiting for backend..." -ForegroundColor Gray
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:$BackendPort/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
}
if ($ready) {
    Write-Host "  Backend READY ✓" -ForegroundColor Green
} else {
    Write-Host "  Backend didn't respond in 15 s — check scratch\backend.log" -ForegroundColor Yellow
}

# Verify model status
try {
    $status = Invoke-WebRequest -Uri "http://localhost:$BackendPort/model/status" -UseBasicParsing -ErrorAction Stop
    $json = $status.Content | ConvertFrom-Json
    Write-Host "  Model: $($json.status)  labels: $($json.labels -join ', ')" -ForegroundColor Green
} catch {
    Write-Host "  Could not reach /model/status" -ForegroundColor Yellow
}

# ─── Frontend ────────────────────────────────────────────────────────────────
Write-Header "Starting Frontend (Next.js)"
$frontendLog = "$REPO\scratch\frontend.log"

$frontendJob = Start-Job -ScriptBlock {
    param($repo, $log)
    Set-Location "$repo\frontend"
    npm run dev 2>&1 | Tee-Object -FilePath $log
} -ArgumentList $REPO, $frontendLog

Write-Host "  Frontend job started (ID $($frontendJob.Id))" -ForegroundColor Green
Write-Host "  Logs → $frontendLog" -ForegroundColor Gray

# Wait for frontend to be ready (up to 30 s)
Write-Host "  Waiting for frontend (Next.js compiles on first request)..." -ForegroundColor Gray
$fready = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:$FrontendPort" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $fready = $true; break }
    } catch {}
}
if ($fready) {
    Write-Host "  Frontend READY ✓" -ForegroundColor Green
} else {
    Write-Host "  Frontend not ready yet — it may still be compiling." -ForegroundColor Yellow
}

# ─── Live GUI (optional) ─────────────────────────────────────────────────────
if ($LiveGUI) {
    Write-Header "Starting Live Detector GUI"
    Write-Host ""
    Write-Host "  IMPORTANT: The ESP32 reboots when the serial port opens." -ForegroundColor Yellow
    Write-Host "  Pair the phone app AFTER this window shows 'Ready'." -ForegroundColor Yellow
    Write-Host ""
    Start-Sleep -Seconds 2
    Start-Process python -ArgumentList "$REPO\tools\predict_live_gui.py --port $Port" -NoNewWindow
    Write-Host "  Live GUI launched." -ForegroundColor Green
}

# ─── Summary ────────────────────────────────────────────────────────────────
Write-Header "All systems up"
Write-Host ""
Write-Host "  Frontend  →  http://localhost:$FrontendPort" -ForegroundColor Green
Write-Host "  Backend   →  http://localhost:$BackendPort" -ForegroundColor Green
Write-Host "  API docs  →  http://localhost:$BackendPort/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Dataset status:" -ForegroundColor Gray
python "$REPO\tools\manage_dataset.py" status
Write-Host ""
Write-Host "  To collect S02 data (ESP32 on $Port):" -ForegroundColor Gray
Write-Host "    python tools/manage_dataset.py collect-all --reps 10 --port $Port --subject S02" -ForegroundColor White
Write-Host ""
Write-Host "  To retrain after collection:" -ForegroundColor Gray
Write-Host "    python ml/refined/train_refined.py" -ForegroundColor White
Write-Host ""
Write-Host "  Press CTRL+C to stop all servers." -ForegroundColor Yellow
Write-Host ""

# Keep alive — stream logs until user interrupts
try {
    while ($true) {
        Start-Sleep -Seconds 5
        # Restart backend if it crashed
        if ($backendJob.State -eq "Failed" -or $backendJob.State -eq "Completed") {
            Write-Host "  [!] Backend stopped — restarting..." -ForegroundColor Yellow
            $backendJob = Start-Job -ScriptBlock {
                param($repo, $port, $log)
                Set-Location $repo
                python -m uvicorn backend.main:app --port $port --log-level info 2>&1 | Tee-Object -FilePath $log
            } -ArgumentList $REPO, $BackendPort, $backendLog
        }
    }
} finally {
    Write-Host ""
    Write-Host "Shutting down..." -ForegroundColor Yellow
    Stop-Job $backendJob -ErrorAction SilentlyContinue
    Stop-Job $frontendJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob -Force -ErrorAction SilentlyContinue
    Remove-Job $frontendJob -Force -ErrorAction SilentlyContinue
    Write-Host "Done." -ForegroundColor Gray
}
