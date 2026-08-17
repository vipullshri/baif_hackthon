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

.PARAMETER Run
    Start the server automatically when setup finishes and open the browser.

.EXAMPLE
    .\scripts\install.ps1
    .\scripts\install.ps1 -Live
    .\scripts\install.ps1 -BuildFrontend
    .\scripts\install.ps1 -Live -Run

.NOTES
    If script execution is blocked, run once with:
        powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
#>
[CmdletBinding()]
param(
    [switch]$Live,
    [switch]$BuildFrontend,
    [switch]$Run,
    [switch]$Reinstall
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$envFile = Join-Path $backend ".env"

# --- .env helpers ----------------------------------------------------------------
# Read a single BHASHASETU_* key from backend/.env (returns $null if absent).
function Get-EnvValue([string]$key) {
    if (-not (Test-Path $envFile)) { return $null }
    foreach ($line in Get-Content $envFile) {
        if ($line -match "^\s*$key\s*=\s*(.*)$") {
            return $matches[1].Trim().Trim("'""")
        }
    }
    return $null
}

# Merge (upsert) a set of key/value pairs into backend/.env, preserving other keys.
function Set-EnvValues([hashtable]$values) {
    $lines = @()
    if (Test-Path $envFile) { $lines = @(Get-Content $envFile) }
    foreach ($key in $values.Keys) {
        $entry = "$key=$($values[$key])"
        $replaced = $false
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match "^\s*$key\s*=") {
                $lines[$i] = $entry
                $replaced = $true
                break
            }
        }
        if (-not $replaced) { $lines += $entry }
    }
    Set-Content -Path $envFile -Value $lines -Encoding UTF8
}

# --- Rerun detection -------------------------------------------------------------
# If a previous install recorded a base dir whose venv still exists, skip setup
# and just start the API (unless -Reinstall forces a fresh setup).
if (-not $Reinstall) {
    $savedBase = Get-EnvValue "BHASHASETU_BASE_DIR"
    if ($savedBase) {
        $savedVenv = if ($env:BHASHASETU_VENV_DIR) { $env:BHASHASETU_VENV_DIR } else { Join-Path $savedBase ".venv" }
        $savedPy = Join-Path $savedVenv "Scripts\python.exe"
        if (Test-Path $savedPy) {
            Write-Host "`n=== Existing install detected ===" -ForegroundColor Green
            Write-Host "  Base dir : $savedBase" -ForegroundColor Gray
            Write-Host "  Python   : $savedPy" -ForegroundColor Gray
            Write-Host "  Starting BhashaSetu (use -Reinstall to redo setup)..." -ForegroundColor Cyan
            Push-Location $backend
            try {
                Start-Process "http://127.0.0.1:8000"
                & $savedPy -m uvicorn app.main:app --host 127.0.0.1 --port 8000
            } finally {
                Pop-Location
            }
            exit 0
        }
    }
}

$targetDir = $null
if ($env:BHASHASETU_TARGET_DIR) {
    $targetDir = $env:BHASHASETU_TARGET_DIR
} else {
    $targetDir = Read-Host "Choose a directory for the installation (press Enter to use the project folder: $root)"
}
$targetDir = $targetDir.Trim().Trim("'""")
if (-not $targetDir -or $targetDir -match '^\s*$') {
    # Default to the project root so a plain Enter just works.
    $targetDir = $root
}

# Normalize a bare drive letter ("D" or "D:") to a rooted path ("D:\").
# Without this, Join-Path treats it as relative and resolves against the current
# directory (usually the C: checkout), silently installing on the wrong drive.
if ($targetDir -match '^[A-Za-z]$') {
    $targetDir = $targetDir + ":\"
} elseif ($targetDir -match '^[A-Za-z]:$') {
    $targetDir = $targetDir + "\"
}

if (-not ($targetDir -match '^[A-Za-z]:\\' -or $targetDir -match '^\\\\')) {
    throw "The installation path '$targetDir' is not an absolute path. Enter a full path like D:\ or D:\apps."
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
$dataDir = if ($env:BHASHASETU_DATA_DIR) { $env:BHASHASETU_DATA_DIR } else { Join-Path $baseDir "data" }

$env:PIP_CACHE_DIR = $cacheDir
$env:PIP_DOWNLOAD_CACHE = $cacheDir
$env:BHASHASETU_BASE_DIR = $baseDir
$env:BHASHASETU_MODELS_DIR = $modelsDir
$env:BHASHASETU_DATA_DIR = $dataDir
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
 _     _               _               _
| |   | |             | |             | |
| |__ | |__   __ _ ___| |__   __ _ ___| |_ _   _
| '_ \| '_ \ / _` / __| '_ \ / _` / __| __| | | |
| |_) | | | | (_| \__ \ | | | (_| \__ \ |_| |_| |
|_.__/|_| |_|\__,_|___/_| |_|\__,_|___/\__|\__,_|

  Language Bridge for BAIF - Marathi . Hindi . English
"@ -ForegroundColor Cyan

# -- 1. Python ------------------------------------------------------------------
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
$pyVer = & $pythonCmd --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Warn "Python installation appears to be corrupted: $pyVer"
    Warn "Install Python 3.10-3.13 from https://www.python.org/downloads/ or try: winget install Python.Python.3.12"
    exit 1
}
Info "Found $pyVer"

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

# -- 2. Virtual environment -----------------------------------------------------
Step "Creating virtual environment"
$driveInfo = Get-PSDrive $targetDrive -ErrorAction SilentlyContinue
if ($driveInfo) {
    $freeGb = "{0:N2}" -f ($driveInfo.Free / 1GB)
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
    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
    New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
    & $pythonCmd -m venv $venv
    Info "Created $venv"
}

# -- 3. Rust toolchain (only needed if a wheel must be built) ----
Step "Checking Rust toolchain"
if ((Get-Command cargo -ErrorAction SilentlyContinue) -and (Get-Command rustc -ErrorAction SilentlyContinue)) {
    Info "Rust toolchain detected."
} elseif (Get-Command winget -ErrorAction SilentlyContinue) {
    Warn "Rust not found. Installing via winget (needed only if prebuilt wheels are unavailable)..."
    winget install --id Rustlang.Rustup -e --accept-source-agreements --accept-package-agreements
} else {
    Warn "Rust not found and winget unavailable. If pip needs to build from source,"
    Warn "install Rust from https://rustup.rs/ then rerun this script."
}

# -- 4. Core dependencies -------------------------------------------------------
Step "Installing core dependencies"
& $py -m pip install --upgrade pip | Out-Null
# Prefer prebuilt wheels so pydantic-core etc. never compile (avoids needing Rust).
& $py -m pip install --only-binary=:all: -r (Join-Path $backend "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Warn "Wheel-only install failed; retrying with source builds allowed (may need Rust)..."
    & $py -m pip install -r (Join-Path $backend "requirements.txt")
}
Info "Core API dependencies installed."

# -- 5. FFmpeg ------------------------------------------------------------------
Step "Checking FFmpeg (needed for real audio/video)"
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Info "FFmpeg is available."
} elseif (Get-Command winget -ErrorAction SilentlyContinue) {
    Info "FFmpeg not found. Installing via winget..."
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
} else {
    Warn "FFmpeg not found and winget unavailable. Install manually: https://www.gyan.dev/ffmpeg/builds/"
}

# -- 6. Live mode (optional) ----------------------------------------------------
if ($Live) {
    Step "Installing ML stack (Live mode)"
    & $py -m pip install -r (Join-Path $backend "requirements-ml.txt")
    Step "Downloading open models"
    Info "Models will be stored in $modelsDir"
    & $py (Join-Path $PSScriptRoot "download_models.py")
}

# -- Persist install paths + mode to backend/.env -------------------------------
Step "Saving configuration"
$enableModels = if ($Live) { "true" } else { "false" }
Set-EnvValues @{
    "BHASHASETU_BASE_DIR"      = $baseDir
    "BHASHASETU_ENABLE_MODELS" = $enableModels
    "BHASHASETU_OFFLINE"       = "false"
}
Info "Wrote settings to $envFile"

# -- 7. Frontend build (optional) -----------------------------------------------
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

# -- Done -----------------------------------------------------------------------
Step "Setup complete"
Write-Host ""
Write-Host "  Start BhashaSetu:" -ForegroundColor Green
Write-Host "      cd backend" -ForegroundColor White
if ($Live) {
    Write-Host "      `$env:BHASHASETU_ENABLE_MODELS = 'true'" -ForegroundColor White
}
$startupCmd = '      & "' + $py + '" -m uvicorn app.main:app --host 127.0.0.1 --port 8000'
Write-Host $startupCmd -ForegroundColor White
Write-Host ""
Write-Host "  Then open http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Install base : $baseDir" -ForegroundColor Gray
Write-Host "  Data folder  : $dataDir" -ForegroundColor Gray
Write-Host "  Models folder: $modelsDir" -ForegroundColor Gray
Write-Host "  (Rerun this script anytime to relaunch the API.)" -ForegroundColor Gray
Write-Host ""

# -- 8. Auto-start (optional) ---------------------------------------------------
if ($Run) {
    Step "Starting BhashaSetu"
    if ($Live) { $env:BHASHASETU_ENABLE_MODELS = "true" }
    Push-Location $backend
    Start-Process "http://127.0.0.1:8000"
    & $py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    Pop-Location
}