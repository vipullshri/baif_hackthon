<#
.SYNOPSIS
    BhashaSetu setup script for Windows.

.DESCRIPTION
    Creates the Python virtual environment, installs dependencies and starts
    BhashaSetu for local use.

    Run with NO arguments for the interactive menu: it detects whether an install
    already exists and offers Start / Reinstall (Demo or Live) for an existing setup,
    or Demo/Live install choices for a first-time setup. Passing any flag below skips
    the menu (useful for automation) and applies that flag directly.

.PARAMETER Live
    Also install the ML stack (requirements-ml.txt) and pre-download the open models
    for production-quality output.

.PARAMETER BuildFrontend
    Build the React/Vite/Tailwind UI (requires Node.js + internet).
    The new UI build is mandatory for runtime.

.PARAMETER NoRun
    Do not auto-start the app after setup.

.PARAMETER Reinstall
    Rebuild installation in the selected base directory.

.PARAMETER Force
    Alias for -Reinstall.

.EXAMPLE
    .\scripts\install.ps1             # interactive menu (recommended)
    .\scripts\install.ps1 -Live       # non-interactive Live install
    .\scripts\install.ps1 -Live -NoRun
    .\scripts\install.ps1 -Reinstall

.NOTES
    If script execution is blocked, run once with:
        powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
#>
[CmdletBinding()]
param(
    [switch]$Live,
    [switch]$BuildFrontend,
    [switch]$NoRun,
    [switch]$Run,
    [Alias("Force")]
    [switch]$Reinstall
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$envFile = Join-Path $backend ".env"
$defaultTargetRoot = $root
$effectiveRun = -not $NoRun
# Resolved runtime choices. These start from the flags but can be overridden by the
# interactive menu below when the script is launched with no arguments.
$liveMode = [bool]$Live
$reinstallMode = [bool]$Reinstall
$noFlagsPassed = ($PSBoundParameters.Count -eq 0)
$targetDirOverride = $null

if ($Run) {
    Write-Host "  Note: -Run is now default behavior. Use -NoRun to skip auto-start." -ForegroundColor Gray
}

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Green }
function Info($msg) { Write-Host "  $msg" -ForegroundColor Gray }
function Warn($msg) { Write-Host "  ! $msg" -ForegroundColor Yellow }

function Start-BhashaSetu([string]$pythonExe) {
    Push-Location $backend
    try {
        Start-Process "http://127.0.0.1:8000"
        & $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    } finally {
        Pop-Location
    }
}

function Test-CommandHealthy([string]$command, [string[]]$commandArgs) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        return $false
    }
    & $command @commandArgs | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Test-WebReachable([string]$hostName) {
    # Fast single TCP probe to :443 instead of a full HTTP GET (the old 12s-per-call
    # Invoke-WebRequest checks were the slow step). Test-NetConnection is a cmdlet, so it
    # stays safe under PowerShell Constrained Language Mode on this machine.
    try {
        return (Test-NetConnection -ComputerName $hostName -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue)
    } catch {
        return $false
    }
}


# -- GPU auto-detection --------------------------------------------------------
# Detects an NVIDIA GPU via nvidia-smi and returns the matching PyTorch CUDA wheel tag
# (e.g. "cu121"), or $null when no usable NVIDIA GPU/driver is found. CUDA is
# NVIDIA-only, so AMD / Intel / Apple GPUs (and no-GPU boxes) correctly get $null -> CPU.
function Get-TorchCudaTag {
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { return $null }
    try {
        $out = & nvidia-smi 2>$null
    } catch {
        return $null
    }
    if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
    # nvidia-smi's header prints the max supported toolkit, e.g. "CUDA Version: 12.4".
    $m = ($out | Select-String -Pattern 'CUDA Version:\s*([0-9]+)\.([0-9]+)' | Select-Object -First 1)
    if (-not $m) { return "cu121" } # GPU present but version unparsed: safe default.
    $major = [int]$m.Matches[0].Groups[1].Value
    $minor = [int]$m.Matches[0].Groups[2].Value
    if ($major -gt 12 -or ($major -eq 12 -and $minor -ge 4)) { return "cu124" }
    if ($major -eq 12) { return "cu121" }
    return $null # CUDA 11.x or older driver: fall back to CPU to avoid a bad combo.
}

# Installs torch with the correct build: the CUDA wheel + cuDNN/cuBLAS runtime (needed by
# faster-whisper's CTranslate2 for GPU ASR) when an NVIDIA GPU is present, otherwise the
# CPU-only wheel. Returns "cuda" or "cpu" so the caller can persist BHASHASETU_DEVICE.
function Install-Torch([string]$pythonExe) {
    $cudaTag = Get-TorchCudaTag
    if ($cudaTag) {
        Info "NVIDIA GPU detected. Installing CUDA build of PyTorch ($cudaTag)..."
        & $pythonExe -m pip install torch --index-url "https://download.pytorch.org/whl/$cudaTag"
        if ($LASTEXITCODE -ne 0) {
            Warn "CUDA torch install failed; falling back to the CPU build."
            & $pythonExe -m pip install torch --index-url "https://download.pytorch.org/whl/cpu"
            return "cpu"
        }
        Info "Installing cuDNN / cuBLAS runtime for GPU ASR (fixes 'cublas64_12.dll not found')..."
        & $pythonExe -m pip install nvidia-cudnn-cu12 nvidia-cublas-cu12
        if ($LASTEXITCODE -ne 0) {
            Warn "cuDNN/cuBLAS install failed; GPU ASR may not work until you retry."
        }
        return "cuda"
    }
    Info "No NVIDIA GPU detected (AMD/Intel/none). Installing CPU build of PyTorch..."
    & $pythonExe -m pip install torch --index-url "https://download.pytorch.org/whl/cpu"
    return "cpu"
}

# --- .env helpers -------------------------------------------------------------
# Read a single BHASHASETU_* key from backend/.env (returns $null if absent).
function Get-EnvValue([string]$key) {
    if (-not (Test-Path $envFile)) { return $null }
    foreach ($line in Get-Content $envFile) {
        if ($line -match "^\s*$key\s*=\s*(.*)$") {
            return $matches[1].Trim().Trim('"')
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
    # Config.py reads .env as utf-8-sig, so a BOM here is harmless.
    Set-Content -Path $envFile -Value $lines -Encoding UTF8
}

# --- Existing-install detection -----------------------------------------------
# An install counts as "existing" when its virtual environment is healthy. The React
# build is tracked separately: a missing UI is repaired (rebuilt) rather than forcing a
# full fresh setup.
function Get-ExistingInstallPython {
    $savedBase = Get-EnvValue "BHASHASETU_BASE_DIR"
    if (-not $savedBase) { return $null }
    $savedVenv = if ($env:BHASHASETU_VENV_DIR) { $env:BHASHASETU_VENV_DIR } else { Join-Path $savedBase ".venv" }
    $savedPy = Join-Path $savedVenv "Scripts\python.exe"
    if ((Test-Path $savedPy) -and (Test-CommandHealthy $savedPy @("--version"))) { return $savedPy }
    return $null
}

function Test-FrontendBuilt {
    return (Test-Path (Join-Path $backend "app\static\index.html"))
}

function Invoke-FrontendBuild {
    Step "Building React frontend"
    Push-Location $frontend
    npm install
    npm run build
    Pop-Location
    Info "React UI built into backend/app/static."
}

# Adaptive menu shown only for a bare `install.ps1` (no flags, not env-driven). Returns a
# hashtable describing the chosen action.
function Show-InstallMenu {
    $existingPy = Get-ExistingInstallPython
    if ($existingPy) {
        $modeVal = Get-EnvValue "BHASHASETU_ENABLE_MODELS"
        $modeText = if ($modeVal -eq "true") { "LIVE (real ML models)" } else { "DEMO (no heavy ML)" }
        $savedBase = Get-EnvValue "BHASHASETU_BASE_DIR"
        Write-Host "`n=== BhashaSetu - existing install detected ===" -ForegroundColor Green
        Write-Host "  Base dir : $savedBase" -ForegroundColor Gray
        Write-Host "  Mode     : $modeText" -ForegroundColor Gray
        Write-Host ""
        Write-Host "  [1] Start the server (default)" -ForegroundColor White
        Write-Host "  [2] Reinstall - Demo mode" -ForegroundColor White
        Write-Host "  [3] Reinstall - Live mode (real ML models, needs internet)" -ForegroundColor White
        Write-Host "  [Q] Quit" -ForegroundColor White
        $choice = Read-Host "Choose an option [1]"
        switch ($choice.Trim().ToUpper()) {
            "2" { return @{ Action = "reinstall"; Live = $false } }
            "3" { return @{ Action = "reinstall"; Live = $true } }
            "Q" { return @{ Action = "quit" } }
            default { return @{ Action = "start" } }
        }
    } else {
        Write-Host "`n=== BhashaSetu - first-time setup ===" -ForegroundColor Green
        Write-Host ""
        Write-Host "  [1] Install Demo mode and start (default, no heavy ML)" -ForegroundColor White
        Write-Host "  [2] Install Live mode and start (real ML models, needs internet)" -ForegroundColor White
        Write-Host "  [3] Install Demo mode without starting" -ForegroundColor White
        Write-Host "  [Q] Quit" -ForegroundColor White
        $choice = Read-Host "Choose an option [1]"
        switch ($choice.Trim().ToUpper()) {
            "2" { return @{ Action = "install"; Live = $true; Run = $true } }
            "3" { return @{ Action = "install"; Live = $false; Run = $false } }
            "Q" { return @{ Action = "quit" } }
            default { return @{ Action = "install"; Live = $false; Run = $true } }
        }
    }
}

if ($noFlagsPassed -and -not $env:BHASHASETU_TARGET_DIR) {
    # --- Interactive menu path (bare `install.ps1`) ---
    $menu = Show-InstallMenu
    switch ($menu.Action) {
        "quit" {
            Write-Host "  Cancelled." -ForegroundColor Yellow
            exit 0
        }
        "start" {
            $existingPy = Get-ExistingInstallPython
            if (-not (Test-FrontendBuilt)) {
                Warn "Frontend build missing; rebuilding the UI before starting..."
                Invoke-FrontendBuild
            }
            Write-Host "`n=== Starting BhashaSetu ===" -ForegroundColor Green
            Start-BhashaSetu $existingPy
            exit 0
        }
        "reinstall" {
            $reinstallMode = $true
            $liveMode = [bool]$menu.Live
            $effectiveRun = $true
            # Reuse the existing install location instead of re-prompting for it.
            $savedBase = Get-EnvValue "BHASHASETU_BASE_DIR"
            if ($savedBase) { $targetDirOverride = Split-Path -Parent $savedBase }
        }
        "install" {
            $liveMode = [bool]$menu.Live
            $effectiveRun = [bool]$menu.Run
        }
    }
} elseif ((-not $reinstallMode) -and (-not $liveMode) -and (-not $BuildFrontend)) {
    # --- Flag/automation fast-launch: a healthy existing install just starts ---
    $existingPy = Get-ExistingInstallPython
    if ($existingPy -and (Test-FrontendBuilt)) {
        Write-Host "`n=== Existing install detected ===" -ForegroundColor Green
        if ($effectiveRun) {
            Write-Host "  Starting BhashaSetu (use -Reinstall to redo setup)..." -ForegroundColor Cyan
            Start-BhashaSetu $existingPy
        } else {
            Write-Host "  Existing install is healthy. Start was skipped because -NoRun was used." -ForegroundColor Cyan
        }
        exit 0
    }
}

$targetDir = $null
if ($targetDirOverride) {
    $targetDir = $targetDirOverride
} elseif ($env:BHASHASETU_TARGET_DIR) {
    $targetDir = $env:BHASHASETU_TARGET_DIR
} else {
    $targetDir = Read-Host "Choose a directory for the installation (press Enter to use the project folder: $defaultTargetRoot)"
}
$targetDir = $targetDir.Trim().Trim('"')
if (-not $targetDir -or $targetDir -match '^\s*$') {
    # Default to the project root so a plain Enter just works.
    $targetDir = $defaultTargetRoot
}
# Normalize a bare drive letter ("D" or "D:") to a rooted path ("D:\").
# Without this, Join-Path treats it as relative and resolves against the current
# directory (usually the C: checkout), silently installing on the wrong drive.
if ($targetDir -match '^[A-Za-z]$') {
    $targetDir = "$targetDir" + ":\"
} elseif ($targetDir -match '^[A-Za-z]:$') {
    $targetDir = "$targetDir" + "\"
}
if (-not ($targetDir -match '^[A-Za-z]:\\') -or $targetDir -match '\\\\') {
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
# Single source of truth: the app derives data/models/tmp/logs from BASE_DIR alone.
# These locals are only for install-time dir creation and the summary display.
$modelsDir = Join-Path $baseDir "models"
$dataDir = Join-Path $baseDir "data"
$tmpDir = if ($env:BHASHASETU_TMP_DIR) { $env:BHASHASETU_TMP_DIR } else { Join-Path $baseDir "tmp" }

$env:PIP_CACHE_DIR = $cacheDir
$env:PIP_DOWNLOAD_CACHE = $cacheDir
if ($env:BHASHASETU_TMP_DIR) {
    $env:TEMP = $env:BHASHASETU_TMP_DIR
    $env:TMP = $env:BHASHASETU_TMP_DIR
} else {
    $env:TEMP = $tmpDir
    $env:TMP = $tmpDir
}

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

# -- 1b. Node.js / npm ---------------------------------------------------------
Step "Checking Node.js"
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Warn "Node.js not found. The new UI build is required."
    Warn "Install Node.js 18+ from https://nodejs.org and rerun this script."
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Warn "npm not found. The new UI build is required."
    Warn "Install Node.js 18+ from https://nodejs.org and rerun this script."
    exit 1
}
Info "Node.js and npm are available."

# -- 2. Virtual environment ----------------------------------------------------
Step "Creating virtual environment"
$driveInfo = Get-PSDrive $targetDrive -ErrorAction SilentlyContinue
if ($driveInfo) {
    $freeGb = "{0:N2}" -f ($driveInfo.Free / 1GB)
    Info "Selected drive $($driveInfo.Name): has $freeGb GB free space."
    $minRequiredGb = if ($liveMode) { 12 } else { 5 }
    if ($driveInfo.Free -lt ($minRequiredGb * 1GB)) {
        Warn "Drive $($driveInfo.Name): has less than $minRequiredGb GB free space."
        Warn "Please choose a different drive with more free space."
        exit 1
    }
}

if ($liveMode) {
    Step "Live mode preflight"
    Info "Checking internet reachability for package/model downloads..."
    $pypiOk = Test-WebReachable "pypi.org"
    $hfOk = Test-WebReachable "huggingface.co"
    if (-not $pypiOk -or -not $hfOk) {
        Warn "Live mode requires internet access to both pypi.org and huggingface.co."
        Warn "Please connect to internet or rerun without -Live for demo mode."
        exit 1
    }
    Info "Internet checks passed for live mode."
}

if ($reinstallMode) {
    Step "Preparing reinstall"
    if (Test-Path $venv) {
        Info "Removing existing virtual environment: $venv"
        Remove-Item -Recurse -Force $venv
    }
    if (Test-Path $cacheDir) {
        Info "Clearing pip cache: $cacheDir"
        Remove-Item -Recurse -Force $cacheDir
    }
}

if (Test-Path $py) {
    Info "venv already exists at $venv"
} else {
    New-Item -ItemType Directory -Force -Path (Split-Path $venv -Parent) | Out-Null
    New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
    New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null
    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
    New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
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

# -- 4. Core dependencies ------------------------------------------------------
Step "Installing core dependencies"
& $py -m pip install --upgrade pip | Out-Null
# Prefer prebuilt wheels so pydantic-core etc. never compile (avoids needing Rust).
& $py -m pip install --only-binary=:all: -r (Join-Path $backend "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Warn "Wheel-only install failed; retrying with source builds allowed (may need Rust)..."
    & $py -m pip install -r (Join-Path $backend "requirements.txt")
}
Info "Core API dependencies installed."

# -- 5. FFmpeg -----------------------------------------------------------------
Step "Checking FFmpeg (needed for real audio/video)"
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    ffmpeg -version | Select-Object -First 1 | ForEach-Object { Info "Found $_" }
} elseif (Get-Command winget -ErrorAction SilentlyContinue) {
    Info "FFmpeg not found. Installing via winget..."
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        ffmpeg -version | Select-Object -First 1 | ForEach-Object { Info "Installed $_" }
    } else {
        Warn "FFmpeg install may need a new terminal session to refresh PATH."
    }
} else {
    Warn "FFmpeg not found and winget unavailable. Install manually: https://www.gyan.dev/ffmpeg/builds/"
}

# -- 6. Live mode (optional) ---------------------------------------------------
if ($liveMode) {
    Step "Installing ML stack (live mode)"
    # Install torch with the best available build for the detected GPU (or CPU-only if none). Returns "cuda" or "cpu".
    $torchBuild = Install-Torch $py
    Info "PyTorch build: $torchBuild"
    & $py -m pip install -r (Join-Path $backend "requirements-ml.txt")
    Step "Downloading open models"
    Info "Models will be stored in $modelsDir"
    & $py (Join-Path $PSScriptRoot "download_models.py")
}

# -- Persist install paths + mode to backend/.env ------------------------------
Step "Saving configuration"
$enableModels = if ($liveMode) { "true" } else { "false" }
# Single source of truth: everything (data, models, tmp) derives from BASE_DIR.
Set-EnvValues @{
    "BHASHASETU_BASE_DIR"     = $baseDir
    "BHASHASETU_ENABLE_MODELS" = $enableModels
    "BHASHASETU_OFFLINE"      = "false"
    "BHASHASETU_DEVICE"        = "auto"
}
Info "Wrote settings to $envFile"

# -- 7. Frontend build ---------------------------------------------------------
Step "Building React frontend"
Push-Location $frontend
npm install
npm run build
Pop-Location
Info "React UI built into backend/app/static."

$reactIndex = Join-Path $backend "app\static\index.html"
if (-not (Test-Path $reactIndex)) {
    Warn "React build completed, but backend/app/static/index.html was not found."
    Warn "Please check frontend build output and rerun install."
    exit 1
}

# -- 8. Smoke check ------------------------------------------------------------
Step "Smoke check"
& $py -c "import fastapi, uvicorn; print('Python env check: OK')"
if ($LASTEXITCODE -ne 0) {
    Warn "Environment smoke check failed. Re-run with -Reinstall after checking Python and network access."
    exit 1
}

$modeLabel = if ($liveMode) { "LIVE" } else { "DEMO" }
$uiLabel = "React build"
$startLabel = if ($effectiveRun) { "Auto-start" } else { "Manual start" }

# -- Done ----------------------------------------------------------------------
Step "Setup complete"
Write-Host ""
Write-Host "  Mode         : $modeLabel" -ForegroundColor White
Write-Host "  UI           : $uiLabel" -ForegroundColor White
Write-Host "  Start mode   : $startLabel" -ForegroundColor White
Write-Host ""
Write-Host "  Install base : $baseDir" -ForegroundColor Gray
Write-Host "  Data folder  : $dataDir" -ForegroundColor Gray
Write-Host "  Models folder: $modelsDir" -ForegroundColor Gray
Write-Host "  (Rerun this script anytime to relaunch the API.)" -ForegroundColor Gray
Write-Host ""

# -- 9. Auto-start -------------------------------------------------------------
if ($effectiveRun) {
    Step "Starting BhashaSetu"
    Start-BhashaSetu $py
} else {
    Write-Host "  Start BhashaSetu manually:" -ForegroundColor Green
    Write-Host "    cd backend" -ForegroundColor White
    $startupCmd = "    & '" + $py + "' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
    Write-Host $startupCmd -ForegroundColor White
    Write-Host ""
    Write-Host "  Then open http://127.0.0.1:8000" -ForegroundColor Cyan
    Write-Host "  Optional check after start: http://127.0.0.1:8000/api/health" -ForegroundColor Gray
}