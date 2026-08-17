<#
.SYNOPSIS
    Start RetailVoice AI locally (Windows / PowerShell).

.DESCRIPTION
    Creates the Python virtual environment and installs both dependency sets on
    first run, then launches the API and the Vite dev server in new windows.

.EXAMPLE
    .\scripts\dev.ps1
    .\scripts\dev.ps1 -Reseed
    .\scripts\dev.ps1 -BackendOnly
#>
param(
    [switch]$Reseed,
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root '.venv\Scripts\python.exe'

function Write-Step($message) {
    Write-Host "`n==> $message" -ForegroundColor Cyan
}

# ---------------------------------------------------------------- backend ---
if (-not $FrontendOnly) {
    if (-not (Test-Path $python)) {
        Write-Step 'Creating the Python virtual environment'
        python -m venv .venv
    }

    if (-not $SkipInstall) {
        Write-Step 'Installing backend dependencies'
        & $python -m pip install --quiet --upgrade pip
        & $python -m pip install --quiet -r backend\requirements.txt
    }

    if ($Reseed) {
        Write-Step 'Rebuilding the demo database'
        Push-Location backend
        & $python -m app.db.seed --reset
        Pop-Location
    }
}

# --------------------------------------------------------------- frontend ---
if (-not $BackendOnly) {
    if (-not (Test-Path (Join-Path $root 'frontend\node_modules')) -and -not $SkipInstall) {
        Write-Step 'Installing frontend dependencies'
        npm --prefix frontend install
    }
}

# ------------------------------------------------------------------ launch --
if (-not $FrontendOnly) {
    Write-Step 'Starting the API on http://localhost:8000'
    Start-Process powershell -ArgumentList @(
        '-NoExit', '-Command',
        "Set-Location '$root\backend'; & '$python' -m uvicorn app.main:app --reload --port 8000"
    )
}

if (-not $BackendOnly) {
    Start-Sleep -Seconds 2
    Write-Step 'Starting the web app on http://localhost:5173'
    Start-Process powershell -ArgumentList @(
        '-NoExit', '-Command',
        "Set-Location '$root'; npm --prefix frontend run dev"
    )
}

Write-Host @'

  RetailVoice AI is starting.

    Web app    http://localhost:5173
    API docs   http://localhost:8000/docs

  Demo accounts (password shown):
    customer@retailvoice.ai    Demo@1234
    agent1@retailvoice.ai      Demo@1234
    admin@retailvoice.ai       Admin@123

'@ -ForegroundColor Green
