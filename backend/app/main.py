import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.config import settings, BACKEND_DIR
from app.db.database import init_db
from app.services import glossary, jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


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