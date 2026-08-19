import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.config import settings, BACKEND_DIR
from app.db.database import init_db
from app.services import glossary, jobs

def _configure_logging() -> None:
    """Configure logging for the app and its dependencies.

    The default uvicorn config is too verbose and not very readable. This
    configures a single root logger with a simple format, and sets the log
    level for noisy dependencies to WARNING.
    """

    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    root= logging.getLogger()
    root.setLevel(logging.INFO)

    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        root.addHandler(console)

    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        try:
            file_handler = RotatingFileHandler(
                settings.logs_path / "bhashasetu.log",
                maxBytes=5 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(fmt)
            root.addHandler(file_handler)
        except Exception:
            logging.getLogger("bhashasetu").warning(
                "could not open log file '%s/bhashasetu.log' for writing; falling back to console only",
                settings.logs_path,
            )


_configure_logging()
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings.ensure_dirs()
    init_db()
    count = glossary.seed_glossary_if_empty()
    if count > 0:
        logging.info("Seeded glossary with %d terms.", count)

    yield

    # Shutdown
    jobs.shutdown()


app = FastAPI(
    title="BhashaSetu",
    description="Offline agricultural media translation.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(api_router)

# Mount the pre-built Vanilla JS frontend directly from the backend directory.
app.mount("/", StaticFiles(directory=str(BACKEND_DIR / "app" / "webui"), html=True), name="webui")