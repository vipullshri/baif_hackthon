<#
.SYNOPSIS
    BhashaSetu setup script for Windows.

.DESCRIPTION
    Creates the Python virtual environment, installs dependencies and prints the
    command to start the app. By default it sets up DEMO mode (no heavy ML models),
    which runs the whole workflow instantly with realistic mock output.

.PARAMETER Live
    Also install the ML stack (requirements-ml.txt) and pre-download the open models
    for production-quality output.

.PARAMETER BuildFrontend
    Build the React/Vite/Tailwind UI (requires Node.js + internet). Optional - a
    polished, zero-build UI ships ready to run.

.EXAMPLE
    ./scripts/install.ps1
    ./scripts/install.ps1 -Live
    ./scripts/install.ps1 -BuildFrontend
#>
[CmdletBinding()]
param(
    [switch]$Live,
    [switch]$BuildFrontend
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot          # project root
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$venv = Join-Path $backend ".venv"
$py = Join-Path $venv "Scripts\python.exe"

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Green }
function Info($msg) { Write-Host "  $msg" -ForegroundColor Gray }
function Warn($msg) { Write-Host "  ! $msg" -ForegroundColor Yellow }

Write-Host @"

 ___ _               _           ___     _       
| _ ) |_  __ _ ___| |_  __ _ / __| ___| |_ _  _ 
| _ \ ' \/ _` / __| ' \/ _` |\__ \/ -_)  _| || |
|___/_||_\__,_\___|_||_\__,_||___/\___|\__|\_,_|
                                         
  Language Bridge for BAIF - Marathi . Hindi . English
"@ -ForegroundColor Cyan

# -- 1. Python ---------------------------------------------------
Step "Checking Python"
$pythonCmd = $null
foreach ($c in @("python", "py")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) { $pythonCmd = $c; break }
}
if (-not $pythonCmd) {
    Warn "Python not found. Install Python 3.10+ from https://www.python.org/downloads/ (tick 'Add to PATH')."
    exit 1
}
$pyver = & $pythonCmd --version
Info "Found $pyver"

# -- 2. Virtual environment --------------------------------------
Step "Creating virtual environment"
if (Test-Path $py) {
    Info "venv already exists at $venv"
} else {
    & $pythonCmd -m venv $venv
    Info "Created $venv"
}

# -- 3. Core dependencies ----------------------------------------
Step "Installing core dependencies"
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install -r (Join-Path $backend "requirements.txt")
Info "Core API dependencies installed."

# -- 4. FFmpeg check ---------------------------------------------
Step "Checking FFmpeg (optional in demo mode)"
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Info "FFmpeg is available."
} else {
    Warn "FFmpeg not found. Needed for real audio/video. Install with: winget install Gyan.FFmpeg"
}

# -- 5. Live mode (optional) -------------------------------------
if ($Live) {
    Step "Installing ML stack (live mode)"
    & $py -m pip install -r (Join-Path $backend "requirements-ml.txt")
    Step "Downloading open models"
    & $py (Join-Path $PSScriptRoot "download_models.py")
}

# -- 6. Frontend build (optional) --------------------------------
if ($BuildFrontend) {
    Step "Building React frontend"
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Push-Location $frontend
        npm install
        npm run build
        Pop-Location
        Info "React UI built into backend/app/static."
    } else {
        Warn "npm not found. Skipping. The bundled UI will be served instead."
    }
}

# -- Done --------------------------------------------------------
Step "Setup complete"
Write-Host ""
Write-Host "  Start BhashaSetu:" -ForegroundColor Green
Write-Host "    cd backend" -ForegroundColor White
if ($Live) {
    Write-Host "    `$env:BHASHASETU_ENABLE_MODELS = 'true'" -ForegroundColor White
}
Write-Host "    .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000" -ForegroundColor White
Write-Host ""
Write-Host "  Then open http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host ""