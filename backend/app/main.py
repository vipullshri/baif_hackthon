"""
BhashaSetu - FastAPI application entry point.

Serves the JSON API under `/api` and the compiled React single-page app at the
root, making the whole product a single, offline-friendly deployable.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __app_name__, __version__
from app.api.routes import router as api_router
from app.config import settings
from app.db.database import init_db
from app.services import glossary, jobs

def _configure_logging() -> None:
    """Configure console + persistent on-disk logging.

    Logs always stream to the console AND to a rotating file under
    `<base>/data/logs/bhashasetu.log` (5 MB x 5 files), regardless of build
    mode (console/windowed/dev), so a diagnostics trail is always saved to disk.
    """
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        root.addHandler(console)

    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        try:
            settings.logs_path.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                settings.logs_path / "bhashasetu.log",
                maxBytes=5 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(fmt)
            root.addHandler(file_handler)
        except Exception:  # noqa: BLE001 - never let logging setup crash startup
            logging.getLogger("bhashasetu").warning(
                "Could not open log file at %s; logging to console only.",
                settings.logs_path,
            )

_configure_logging()
logger = logging.getLogger("bhashasetu")

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.apply_offline_env()
    settings.ensure_dirs()
    init_db()

    asr_warm = False
    if settings.enable_models and settings.asr_preload:
        asr_warm = asr.preload_model()

    seeded = glossary.seed_glossary_if_empty()

    logger.info(
        "%s v%s starting | models=%s | offline=%s | asr_preloaded=%s | glossary_seeded=%d",
        __app_name__, __version__, settings.enable_models, settings.offline, asr_warm, seeded,
    )
    yield
    jobs.shutdown()

app = FastAPI(
    title=f"{__app_name__} API",
    version=__version__,
    description="Offline-capable media translation for BAIF (Marathi - Hindi - English).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# --- Serve the UI (single deployable) -----------------------------------------
# The app now relies only on the compiled React build
# (frontend/npm run build -> app/static).

_ui_root = settings.static_path
_INDEX = "index.html"

if (_ui_root / _INDEX).exists():
    # Hashed assets (JS/CSS/fonts) under /assets, if the build produced them.
    if (_ui_root / "assets").exists():
        app.mount("/assets", StaticFiles(directory=_ui_root / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        # Let the API 404 naturally; everything else falls back to the SPA shell.
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        candidate = _ui_root / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)

        return FileResponse(_ui_root / _INDEX)
else:
    @app.get("/", include_in_schema=False)
    async def root_placeholder():
        return JSONResponse(
            {
                "app": __app_name__,
                "version": __version__,
                "message": "API is running, but the React UI build is missing. Run scripts/install.ps1 to build and serve the UI.",
                "docs": "/docs",
                "health": "/api/health",
            }
            ,status_code=503
        )