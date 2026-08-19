"""
Application configuration.

All settings are read from environment variables (prefixed ``BHASHASETU_``)
or an optional ``.env`` file. See ``.env.example`` for the full list.
"""
from __future__ import annotations

import os
import re
import sys
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# backend/ directory (two levels up from this file: app/config.py -> app -> backend).
# When frozen by PyInstaller the bundled, read-only resources (app/seed, app/webui)
# are unpacked under sys._MEIPASS, so resolve against that root instead of __file__.
if getattr(sys, "frozen", False):
    BACKEND_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
else:
    BACKEND_DIR = Path(__file__).resolve().parent.parent

# --- Storage layout - single source of truth --------------------------------
# Every runtime artifact lives under exactly one base directory, split into two
# roots: ``data`` (mutable app state) and ``models`` (downloaded weights/caches).
# The sub-folders below are the ONLY place these names are defined; both the path
# properties and ``ensure_dirs()`` derive from them.
DATA_ROOT = "data"
MODELS_ROOT = "models"
# Project-local (portable/demo) fallback when no base_dir is configured. Models
# sit beside backend/ at the repo root (../models); data lives under backend/.
LOCAL_MODELS_DIR = "../models"
# Sub-folders under the data root.
DATA_SUBDIRS = ("uploads", "outputs", "library", "tmp", "logs", "db")


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_prefix="BHASHASETU_",
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )

    # --- Server -------------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:8000"

    # --- Master switch ------------------------------------------------------
    enable_models: bool = False
    offline: bool = False

    # --- Compute ------------------------------------------------------------
    device: str = "auto"              # auto | cpu | cuda
    compute_type: str = "int8"        # int8 | int8_float16 | float16 | float32

    # --- Models -------------------------------------------------------------
    whisper_model: str = "small"
    mt_backend: str = "indictrans2"  # indictrans2 | nllb
    indictrans_en_indic: str = "ai4bharat/indictrans2-en-indic-dist-200M"
    indictrans_indic_en: str = "ai4bharat/indictrans2-indic-en-dist-200M"
    indictrans_indic_indic: str = "ai4bharat/indictrans2-indic-indic-dist-320M"
    nllb_model: str = "facebook/nllb-200-distilled-600M"
    tts_backend: str = "mms"         # mms | parler
    mt_batch_size: int = 8           # sentences translated per model.generate() call

    # --- Hugging Face auth (needed for gated repos like IndicTrans2) --------
    hf_token: str = ""               # set via BHASHASETU_HF_TOKEN or HF_TOKEN

    # --- Storage ------------------------------------------------------------
    # The single storage knob. When set, ALL runtime artifacts live under it:
    # <base_dir>/data (uploads, outputs, library, tmp, logs, db) and
    # <base_dir>/models (downloaded weights + HF/torch caches). Leave blank for a
    # project-local (portable/demo) layout relative to backend/.
    base_dir: str = ""

    # --- Limits (mirror BAIF spec) ------------------------------------------
    max_audio_mb: int = 150
    max_video_mb: int = 200
    max_duration_min: int = 30

    # --- Derived paths ------------------------------------------------------
    @property
    def base_path(self) -> Path | None:
        """The single install base that everything derives from.

        Accepts a bare drive letter (``D`` or ``D:``) - expanded to
        ``<drive>:\\translationService`` - or a full rooted path used as-is.
        Returns ``None`` for a project-local (demo/portable) layout.
        """
        b = (self.base_dir or "").strip().strip('"')
        if not b:
            return None
        # Bare drive letter -> <drive>:\translationService (matches install.ps1).
        if re.fullmatch(r"[A-Za-z]:?", b):
            drive = b[0]
            return Path(f"{drive}:/translationService").resolve()
        return Path(b).expanduser().resolve()

    @property
    def data_path(self) -> Path:
        # Everything derives from base_path (<base>/data); falls back to the
        # project-local layout (backend/data) when no base_dir is configured.
        if self.base_path is not None:
            return (self.base_path / DATA_ROOT).resolve()
        return (BACKEND_DIR / DATA_ROOT).resolve()

    @property
    def models_path(self) -> Path:
        if self.base_path is not None:
            return (self.base_path / MODELS_ROOT).resolve()
        return (BACKEND_DIR / LOCAL_MODELS_DIR).resolve()

    @property
    def uploads_path(self) -> Path:
        return self.data_path / "uploads"

    @property
    def outputs_path(self) -> Path:
        return self.data_path / "outputs"

    @property
    def library_path(self) -> Path:
        return self.data_path / "library"

    @property
    def tmp_path(self) -> Path:
        return self.data_path / "tmp"

    @property
    def logs_path(self) -> Path:
        return self.data_path / "logs"

    @property
    def db_path(self) -> Path:
        return self.data_path / "db" / "bhashasetu.sqlite3"

    @property
    def static_path(self) -> Path:
        """Compiled React UI served by FastAPI."""
        return (BACKEND_DIR / "app" / "static").resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def ensure_dirs(self) -> None:
        """Create all runtime directories if they do not exist.

        Derived entirely from ``DATA_SUBDIRS`` plus the two roots, so adding a
        sub-folder only requires editing that one constant.
        """
        data = self.data_path
        for name in DATA_SUBDIRS:
            (data / name).mkdir(parents=True, exist_ok=True)
        self.models_path.mkdir(parents=True, exist_ok=True)

    def apply_offline_env(self) -> None:
        """Route model/tool caches to the configured base dir and honor offline mode.

        Without this, Hugging Face, Torch and download staging (TEMP) all default to
        C:\\Users\\<user>\\.cache and C:\\...\\Temp, so C: fills up with multi-GB model
        files even when Python and the install live on another drive.
        """
        if self.offline:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

        models = str(self.models_path)
        hub = str(self.models_path / "hub")
        # Model/tool caches: setdefault so an explicit user override still wins.
        cache_defaults = {
            # Hugging Face (transformers / huggingface_hub / datasets).
            "HF_HOME": models,
            "HF_HUB_CACHE": hub,
            "HUGGINGFACE_HUB_CACHE": hub,
            "TRANSFORMERS_CACHE": hub,
            # Torch hub (used by some TTS/ASR backends).
            "TORCH_HOME": str(self.models_path / "torch"),
        }
        for key, value in cache_defaults.items():
            os.environ.setdefault(key, value)

        # Temp/staging must ALWAYS point inside the base dir. On Windows TEMP/TMP
        # are pre-set by the OS, so setdefault() would silently no-op and leave
        # ffmpeg/tempfile writing multi-GB staging files to C:\...\Temp. Force it.
        tmp = str(self.tmp_path)
        Path(tmp).mkdir(parents=True, exist_ok=True)
        for key in ("TMPDIR", "TEMP", "TMP"):
            os.environ[key] = tmp


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()