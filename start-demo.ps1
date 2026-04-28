$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Missing virtual environment at $python" -ForegroundColor Red
    Write-Host "Create/install it first, then rerun this script."
    exit 1
}

$port = if ($env:PORT) { $env:PORT } else { "8001" }
$health = "http://127.0.0.1:$port/api/health"
$url = "http://127.0.0.1:$port"

Write-Host "Starting RapidX Voice OS demo..." -ForegroundColor Cyan
Write-Host "Demo URL: $url" -ForegroundColor Green
Write-Host "Health:   $health" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Keep this PowerShell window open while using the demo." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""

& $python -m uvicorn backend.main:app --host 127.0.0.1 --port $port
