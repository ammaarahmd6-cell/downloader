"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin, download, health, info, jobs
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Starting up", app=settings.APP_NAME, env=settings.APP_ENV)

    # Ensure storage directories exist
    settings.ensure_dirs()

    # Start periodic cleanup background task
    cleanup_task = asyncio.create_task(_periodic_cleanup())

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    cleanup_task.cancel()
    logger.info("Shutting down", app=settings.APP_NAME)


async def _periodic_cleanup() -> None:
    """Run cleanup every 15 minutes."""
    from app.services.cleanup import run_full_cleanup

    while True:
        await asyncio.sleep(15 * 60)
        try:
            result = await run_full_cleanup()
            logger.info("Periodic cleanup ran", **result)
        except Exception:
            logger.exception("Periodic cleanup failed")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-grade media downloader API. "
        "Supports downloading and processing publicly available media from supported providers. "
        "Users must have the legal right to access the content they process."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# ── Global Exception Handlers ─────────────────────────────────────────────────

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception", path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": {"message": "An internal server error occurred.", "category": "server_error"}},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(info.router)
app.include_router(download.router)
app.include_router(jobs.router)
app.include_router(admin.router)


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }
