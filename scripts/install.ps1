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
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

$targetDir = $null
if ($env:BHASHASETU_TARGET_DIR) {
    $targetDir = $env:BHASHASETU_TARGET_DIR
} else {
    $targetDir = Read-Host "Choose a directory for the installation (for example: D:\ or D:\apps)"
}
$targetDir = $targetDir.Trim().Trim('"')
if ([string]::IsNullOrWhiteSpace($targetDir)) {
    throw "No directory was provided. Please enter a directory like D:\ or D:\apps."
}

# Everything lives under a single "translationService" parent folder inside the
# directory the user chose.
$baseDir = Join-Path $targetDir "translationService"
New-Item -ItemType Directory -Force -Path $baseDir | Out-Null
$baseDir = (Resolve-Path $baseDir).Path
Write-Host "  Installing into: $baseDir" -ForegroundColor Gray

# Derive the drive from the resolved base dir for the free-space check.
$targetDrive = ($baseDir -replace '^([A-Za-z]):.*$', '$1')

$venv = if ($env:BHASHASETU_VENV_DIR) { $env:BHASHASETU_VENV_DIR } else { Join-Path $baseDir ".venv" }
$py = Join-Path $venv "Scripts\python.exe"
$cacheDir = if ($env:BHASHASETU_PIP_CACHE_DIR) { $env:BHASHASETU_PIP_CACHE_DIR } else { Join-Path $baseDir "pip-cache" }
$modelsDir = if ($env:BHASHASETU_MODELS_DIR) { $env:BHASHASETU_MODELS_DIR } else { Join-Path $baseDir "models" }

$env:PIP_CACHE_DIR = $cacheDir
$env:PIP_DOWNLOAD_CACHE = $cacheDir
$env:BHASHASETU_MODELS_DIR = $modelsDir
if ($env:BHASHASETU_TMP_DIR) {
    $env:TEMP = $env:BHASHASETU_TMP_DIR
    $env:TMP = $env:BHASHASETU_TMP_DIR
} else {
    $tmpDir = Join-Path $baseDir "tmp"
    $env:TEMP = $tmpDir
    $env:TMP = $tmpDir
}

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Green }
function Info($msg) { Write-Host "  $msg" -ForegroundColor Gray }
function Warn($msg) { Write-Host "  ! $msg" -ForegroundColor Yellow }

Write-Host @"
 ____  _               _           ____       _
| __ )| |__   __ _ ___| |__   __ _/ ___|  ___| |_ _   _
|  _ \| '_ \ / _` / __| '_ \ / _` \___ \ / _ \ __| | | |
| |_) | | | | (_| \__ \ | | | (_| |___) |  __/ |_| |_| |
|____/|_| |_|\__,_|___/_| |_|\__,_|____/ \___|\__|\__,_|
  Language Bridge for BAIF - Marathi . Hindi . English
"@ -ForegroundColor Cyan

# -- 1. Python -----------------------------------------------------------------
Step "Checking Python"
$pythonCmd = $null
foreach ($c in @("py", "python")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) {
        $pythonCmd = $c
        break
    }
}
if (-not $pythonCmd) {
    Warn "Python not found. Install Python 3.10-3.13 from https://www.python.org/downloads/ (tick 'Add to PATH')."
    exit 1
}

# Verify the Python command actually works
$pyver = & $pythonCmd --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Warn "Python installation appears to be corrupted: $pyver"
    Warn "Install Python 3.10-3.13 from https://www.python.org/downloads/ or try: winget install Python.Python.3.12"
    exit 1
}
Info "Found $pyver"

# Get the version number
$pyVersionOutput = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Warn "Could not determine Python version. Python may be corrupted."
    Warn "Try reinstalling Python from https://www.python.org/downloads/"
    exit 1
}

if (-not $pyVersionOutput) {
    Warn "Could not determine Python version. Please install Python 3.10-3.13."
    exit 1
}

# Trim and parse version more robustly
$pyVersionOutput = $pyVersionOutput.Trim()
$versionParts = $pyVersionOutput -split '\.'
if ($versionParts.Count -lt 2) {
    Warn "Could not parse Python version: $pyVersionOutput"
    exit 1
}

$pyMajor = [int]$versionParts[0]
$pyMinor = [int]$versionParts[1]

if ($pyMajor -ne 3 -or $pyMinor -lt 10 -or $pyMinor -gt 13) {
    Warn "Unsupported Python version: $pyVersionOutput"
    Warn "This project needs Python 3.10, 3.11, 3.12 or 3.13."
    Warn "Install a supported version and rerun the script."
    Warn "Example: py -3.12 -m venv 'D:\translationService\.venv'"
    exit 1
}
Info "Python version $pyVersionOutput is supported."

# -- 2. Virtual environment ----------------------------------------------------
Step "Creating virtual environment"
$driveInfo = Get-PSDrive $targetDrive -ErrorAction SilentlyContinue
if ($driveInfo) {
    $freeGb = [math]::Round(($driveInfo.Free / 1GB), 2)
    Info "Selected drive $($driveInfo.Name): has $freeGb GB free space."
    if ($driveInfo.Free -lt 5GB) {
        Warn "Drive $($driveInfo.Name): has less than 5GB free space."
        Warn "Please choose a different drive with more free space."
        exit 1
    }
}
if (Test-Path $py) {
    Info "venv already exists at $venv"
} else {
    New-Item -ItemType Directory -Force -Path (Split-Path $venv -Parent) | Out-Null
    New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
    New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null
    New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
    & $pythonCmd -m venv $venv
    Info "Created $venv"
}

# -- 3. Rust toolchain check ---------------------------------------------------
Step "Checking Rust toolchain"
if (-not (Get-Command cargo -ErrorAction SilentlyContinue) -or -not (Get-Command rustc -ErrorAction SilentlyContinue)) {
    Warn "Rust is required to build pydantic-core from source."
    Warn "Install it from https://rustup.rs/ or run: winget install Rustlang.Rustup"
    Warn "Then reopen this terminal and run: rustup default stable"
    exit 1
}
Info "Rust toolchain detected."

# -- 4. Core dependencies ------------------------------------------------------
Step "Installing core dependencies"
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install -r (Join-Path $backend "requirements.txt")
Info "Core API dependencies installed."

# -- 5. FFmpeg check -----------------------------------------------------------
Step "Checking FFmpeg (optional in demo mode)"
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Info "FFmpeg is available."
} else {
    Warn "FFmpeg not found. Needed for real audio/video. Install with: winget install Gyan.FFmpeg"
}

# -- 6. Live mode (optional) ---------------------------------------------------
if ($Live) {
    Step "Installing ML stack (live mode)"
    & $py -m pip install -r (Join-Path $backend "requirements-ml.txt")
    Step "Downloading open models"
    Info "Models will be stored in $modelsDir"
    & $py (Join-Path $PSScriptRoot "download_models.py")
}

# -- 7. Frontend build (optional) ----------------------------------------------
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

# -- Done ----------------------------------------------------------------------
Step "Setup complete"
Write-Host ""
Write-Host "  Start BhashaSetu:" -ForegroundColor Green
Write-Host "    cd backend" -ForegroundColor White
if ($Live) {
    Write-Host "    $env:BHASHASETU_ENABLE_MODELS = 'true'" -ForegroundColor White
}

$startupCmd = '  & ""' + $py + '"" -m uvicorn app.main:app --host 127.0.0.1 --port 8000'
Write-Host $startupCmd -ForegroundColor White
Write-Host ""
Write-Host "  Then open http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host ""