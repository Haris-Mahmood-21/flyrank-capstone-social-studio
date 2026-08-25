"""FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.scheduler import start_scheduler, stop_scheduler

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)




@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Social Media Studio starting up")
    if settings.ENVIRONMENT != "test":
        start_scheduler()
    yield
    if settings.ENVIRONMENT != "test":
        stop_scheduler()
    logger.info("Social Media Studio shutting down")


app = FastAPI(
    title="Social Media Studio",
    description="Turn a blog post into a scheduled, multi-platform social campaign.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
from app.api import auth, posts, variants  # noqa: E402

app.include_router(auth.router)
app.include_router(posts.router)
app.include_router(variants.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe — returns ok when the app is running."""
    return {"status": "ok"}
