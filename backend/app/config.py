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

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ directory (two levels up from this file: app/config.py -> app -> backend).
# When frozen by PyInstaller the bundled, read-only resources (app/seed, app/webui)
# are unpacked under sys._MEIPASS, so resolve against that root instead of __file__.
if getattr(sys, "frozen", False):
    BACKEND_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
else:
    BACKEND_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_prefix="BHASHASETU_",
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )

    # --- Server ---------------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:8000"

    # --- Master switch --------------------------------------------------------
    enable_models: bool = False
    offline: bool = False

    # --- Compute --------------------------------------------------------------
    device: str = "auto"             # auto | cpu | cuda
    compute_type: str = "int8"       # int8 | int8_float16 | float16 | float32

    # --- Models ---------------------------------------------------------------
    whisper_model: str = "small"
    mt_backend: str = "indictrans2"  # indictrans2 | nllb
    indictrans_en_indic: str = "ai4bharat/indictrans2-en-indic-dist-200M"
    indictrans_indic_en: str = "ai4bharat/indictrans2-indic-en-dist-200M"
    indictrans_indic_indic: str = "ai4bharat/indictrans2-indic-indic-dist-320M"
    nllb_model: str = "facebook/nllb-200-distilled-600M"
    tts_backend: str = "mms"         # mms | parler

    # --- Hugging Face auth (needed for gated repos like IndicTrans2) ----------
    hf_token: str = "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"               # set via BHASHASETU_HF_TOKEN or HF_TOKEN

    # --- Storage --------------------------------------------------------------
    # Absolute base path chosen at install time (install.ps1). When set, all runtime
    # artifacts live under it: <base_dir>/data and <base_dir>/models. Leave blank for
    # a project-local (portable/demo) layout relative to backend/.
    base_dir: str = ""
    data_dir: str = "data"
    models_dir: str = "../models"

    # --- Limits (mirror BAIF spec) --------------------------------------------
    max_audio_mb: int = 150
    max_video_mb: int = 200
    max_duration_min: int = 30

    # --- Derived paths --------------------------------------------------------
    @property
    def base_path(self) -> Path | None:
        """The single install base that everything derives from.

        Accepts a bare drive letter (``D`` or ``D:\``) - expanded to
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
        # An absolute data_dir override always wins; otherwise everything derives
        # from base_path (<base>/data), falling back to the project-local layout.
        candidate = Path(self.data_dir).expanduser()
        if candidate.is_absolute():
            return candidate.resolve()
        if self.base_path is not None:
            return (self.base_path / "data").resolve()
        return (BACKEND_DIR / self.data_dir).resolve()

    @property
    def models_path(self) -> Path:
        candidate = Path(self.models_dir).expanduser()
        if candidate.is_absolute():
            return candidate.resolve()
        if self.base_path is not None:
            return (self.base_path / "models").resolve()
        return (BACKEND_DIR / self.models_dir).resolve()

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
        """Create all runtime directories if they do not exist."""
        for path in (
            self.data_path,
            self.uploads_path,
            self.outputs_path,
            self.library_path,
            self.tmp_path,
            self.db_path.parent,
            self.models_path,
        ):
            path.mkdir(parents=True, exist_ok=True)

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
        # Hugging Face (transformers / huggingface_hub / datasets).
        os.environ.setdefault("HF_HOME", models)
        os.environ.setdefault("HF_HUB_CACHE", hub)
        os.environ.setdefault("HUGGINGFACE_HUB_CACHE", hub)
        os.environ.setdefault("TRANSFORMERS_CACHE", hub)
        # Torch hub (used by some TTS/ASR backends).
        os.environ.setdefault("TORCH_HOME", str(self.models_path / "torch"))
        # Stage large downloads on the same drive instead of C:\...\Temp.
        tmp = str(self.tmp_path)
        os.environ.setdefault("TMPDIR", tmp)
        os.environ.setdefault("TEMP", tmp)
        os.environ.setdefault("TMP", tmp)

@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()

settings = get_settings()