# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for BhashaSetu (Lite / demo build).

Builds from ``backend/launcher.py``:
  * onedir -> dist/BhashaSetu/     (canonical; what the installer packages)
  * onefile -> dist/BhashaSetu.exe  (portable single file)

Select onefile by setting the env var ``BHASHASETU_ONEFILE=1`` before building.
Build via ``scripts/build_exe.ps1`` or directly::

    pyinstaller installer/bhashasetu.spec

This Lite build deliberately EXCLUDES the heavy ML stack (torch/transformers/...)
so the executable stays small and runs the full UI in demo/mock mode. See
docs/INSTALLATION.md for the Full (live-models) build recipe.
"""
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

# PyInstaller injects SPECPATH (the directory holding this spec file).
PROJECT_ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 - provided by PyInstaller
BACKEND = PROJECT_ROOT / "backend"

ONEFILE = os.environ.get("BHASHASETU_ONEFILE", "0") == "1"

# --- Bundled, read-only resources -------------------------------------------
datas = [
    (str(BACKEND / "app" / "webui"), "app/webui"),
    (str(BACKEND / "app" / "seed"), "app/seed"),
]
_static = BACKEND / "app" / "static"
if _static.exists():  # ship the compiled React UI too, if it was built
    datas.append((str(_static), "app/static"))

_ffmpeg = PROJECT_ROOT / "installer" / "bin" / "ffmpeg.exe"
if _ffmpeg.exists():  # optional: bundle ffmpeg for the media pipeline
    datas.append((str(_ffmpeg), "bin"))

# --- Hidden imports (dynamic / plugin-style imports static analysis misses) ---
hiddenimports = [
    "multipart",  # python-multipart, imported as "multipart"
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.logging",
]
hiddenimports += collect_submodules("app")

uv_datas, uv_binaries, uv_hidden = collect_all("uvicorn")
datas += uv_datas
hiddenimports += uv_hidden
binaries = list(uv_binaries)

# --- Keep the Lite build lean: never pull in heavy ML libraries ---
excludes = [
    "torch",
    "transformers",
    "faster_whisper",
    "ctranslate2",
    "sentencepiece",
    "tokenizers",
    "IndicTransToolkit",
    "parler_tts",
]

# --- FULL (live-models) BUILD -----------------------------------------------
# To package the real offline pipeline (Whisper, IndicTrans2, MMS/Parler TTS),
# build in a venv that also has ``backend/requirements-ml.txt`` installed, then:
#   1. Empty the ``excludes`` list above (set ``excludes = []``).
#   2. Pull each ML package's data/binaries/hidden imports in via collect_all,
#      e.g. uncomment the block below.
#   3. Drop ``ffmpeg.exe`` at ``installer/bin/ffmpeg.exe`` (auto-bundled above).
# Expect a multi-GB artifact. See docs/INSTALLATION.md §12.5 for the full recipe.
#
# for _pkg in ("torch", "transformers", "ctranslate2", "sentencepiece",
#              "tokenizers", "soundfile", "numpy"):
#     _d, _b, _h = collect_all(_pkg)
#     datas += _d
#     binaries += _b
#     hiddenimports += _h

_icon_path = PROJECT_ROOT / "installer" / "bhashasetu.ico"
icon = str(_icon_path) if _icon_path.exists() else None

a = Analysis(
    [str(BACKEND / "launcher.py")],
    pathex=[str(BACKEND)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="BhashaSetu",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="BhashaSetu",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon,
    )
    coll = COLLECT(
        exe,