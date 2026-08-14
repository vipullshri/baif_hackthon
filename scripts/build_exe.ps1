<#
.SYNOPSIS
    Build the BhashaSetu Windows executable (Lite / demo build) with PyInstaller.

.DESCRIPTION
    Creates an isolated build virtual environment containing ONLY the core
    runtime dependencies plus PyInstaller (no heavy ML libraries), so the
    resulting executable stays small and launches the full UI in demo mode.

    Outputs:
        dist\BhashaSetu\BhashaSetu.exe  (onedir - default; packaged by installer)
        dist\BhashaSetu.exe             (onefile - portable; -Onefile or -Both)

.PARAMETER Onefile
    Build the portable single-file executable instead of the onedir folder.

.PARAMETER Both
    Build both the onedir folder and the portable single-file executable.

.PARAMETER Clean
    Recreate the build virtual environment from scratch.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1 -Both
#>
[CmdletBinding()]
param(
    [switch]$Onefile,
    [switch]$Both,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$root      = Split-Path -Parent $PSScriptRoot
$spec      = Join-Path $root "installer\bhashasetu.spec"
$reqs      = Join-Path $root "backend\requirements.txt"
$buildVenv = Join-Path $root "build\venv-build"
$venvPy    = Join-Path $buildVenv "Scripts\python.exe"
$distPath  = Join-Path $root "dist"
$workPath  = Join-Path $root "build\pyinstaller"

Write-Host ""
Write-Host "==========================================================" -ForegroundColor DarkGreen
Write-Host " BhashaSetu - Windows EXE builder (Lite / demo)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor DarkGreen
Write-Host ""

# -- 1. Locate a base Python interpreter -------------------------
$basePython = $null
$cmd = Get-Command python -ErrorAction SilentlyContinue
if ($cmd) { $basePython = $cmd.Source }
if (-not $basePython) {
    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if ($cmd) { $basePython = $cmd.Source }
}
if (-not $basePython) {
    Write-Host "ERROR: Python was not found on PATH. Install Python 3.10+ first." -ForegroundColor Red
    exit 1
}
Write-Host "Using base Python: $basePython"

# -- 2. Create / refresh the isolated build venv -----------------
if ($Clean -and (Test-Path $buildVenv)) {
    Write-Host "Removing existing build venv (-Clean)..."
    Remove-Item -Recurse -Force $buildVenv
}
if (-not (Test-Path $venvPy)) {
    Write-Host "Creating build venv at $buildVenv ..."
    & $basePython -m venv $buildVenv
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: venv creation failed." -ForegroundColor Red; exit 1 }
}

# -- 3. Install core dependencies + PyInstaller (no ML stack) ----
Write-Host "Installing core dependencies + PyInstaller..."
& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install -r $reqs
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: dependency install failed." -ForegroundColor Red; exit 1 }
& $venvPy -m pip install "pyinstaller>=6.6,<7"
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: PyInstaller install failed." -ForegroundColor Red; exit 1 }

# -- 4. Build target(s) ------------------------------------------
function Invoke-Build([string]$mode) {
    if ($mode -eq "onefile") {
        $env:BHASHASETU_ONEFILE = "1"
        Write-Host ""
        Write-Host ">> Building PORTABLE single-file exe ..." -ForegroundColor Cyan
    } else {
        $env:BHASHASETU_ONEFILE = "0"
        Write-Host ""
        Write-Host ">> Building ONEDIR application folder ..." -ForegroundColor Cyan
    }
    & $venvPy -m PyInstaller --noconfirm --clean `
        --distpath $distPath --workpath $workPath `
        $spec
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: PyInstaller build failed ($mode)." -ForegroundColor Red; exit 1 }
}

Push-Location $root
try {
    if ($Both) {
        Invoke-Build "onedir"
        Invoke-Build "onefile"
    } elseif ($Onefile) {
        Invoke-Build "onefile"
    } else {
        Invoke-Build "onedir"
    }
}
finally {
    Pop-Location
    Remove-Item Env:\BHASHASETU_ONEFILE -ErrorAction SilentlyContinue
}

# -- 5. Report ---------------------------------------------------
Write-Host ""
Write-Host "==========================================================" -ForegroundColor DarkGreen
Write-Host " Build complete." -ForegroundColor Green
$onedirExe = Join-Path $distPath "BhashaSetu\BhashaSetu.exe"
$onefileExe = Join-Path $distPath "BhashaSetu.exe"
if (Test-Path $onedirExe) { Write-Host "  App folder : $onedirExe" }
if (Test-Path $onefileExe) { Write-Host "  Portable   : $onefileExe" }
Write-Host "  Runtime data lives in: %LOCALAPPDATA%\BhashaSetu" -ForegroundColor DarkGray
Write-Host "==========================================================" -ForegroundColor DarkGreen
Write-Host ""
Write-Host "Next: double-click the exe, or build the installer with Inno Setup:" -ForegroundColor Yellow
Write-Host "  ISCC.exe installer\bhashasetu.iss" -ForegroundColor Yellow
Write-Host ""