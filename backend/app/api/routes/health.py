"""Health and readiness check endpoints."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health", summary="Basic liveness check")
async def health() -> dict[str, str]:
    """Returns 200 OK when the API is running."""
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@router.get("/ready", summary="Deep readiness check")
async def ready() -> dict[str, Any]:
    """
    Checks connectivity to database, Redis (if enabled), and FFmpeg.
    Returns 200 if all critical services are healthy.
    """
    checks: dict[str, str] = {}

    # Database
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    # FFmpeg
    try:
        ffmpeg_path = shutil.which(settings.FFMPEG_PATH) or settings.FFMPEG_PATH
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        checks["ffmpeg"] = "ok" if result.returncode == 0 else "error"
    except Exception as exc:
        checks["ffmpeg"] = f"error: {exc}"

    # Redis (if not using fake)
    if not settings.USE_FAKE_REDIS:
        try:
            import redis

            r = redis.from_url(settings.REDIS_URL, socket_timeout=2)
            r.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"
    else:
        checks["redis"] = "fakeredis (dev mode)"

    all_ok = all(v == "ok" or "fakeredis" in v for v in checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks,
    }
