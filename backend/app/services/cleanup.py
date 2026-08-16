"""Cleanup service — removes expired files, failed jobs, and temp dirs."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.job import Job
from app.utils.storage import delete_job_completed, delete_job_temp

logger = get_logger(__name__)
settings = get_settings()


async def cleanup_expired_files() -> int:
    """Delete completed files whose expiry time has passed. Returns count."""
    now = datetime.utcnow()
    cleaned = 0

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Job).where(
                Job.status == "completed",
                Job.expires_at != None,  # noqa: E711
                Job.expires_at <= now,
            )
        )
        expired_jobs = result.scalars().all()

        for job in expired_jobs:
            delete_job_completed(job.id)
            await session.execute(
                update(Job)
                .where(Job.id == job.id)
                .values(status="expired", file_path=None, filename=None)
            )
            cleaned += 1
            logger.info("Expired file deleted", job_id=job.id)

        await session.commit()

    return cleaned


async def cleanup_stale_jobs(stale_minutes: int = 60) -> int:
    """Mark jobs stuck in processing states as failed. Returns count."""
    cutoff = datetime.utcnow() - timedelta(minutes=stale_minutes)
    stale_statuses = ("starting", "analyzing", "downloading", "processing")
    cleaned = 0

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Job).where(
                Job.status.in_(stale_statuses),
                Job.started_at != None,  # noqa: E711
                Job.started_at <= cutoff,
            )
        )
        stale_jobs = result.scalars().all()

        for job in stale_jobs:
            delete_job_temp(job.id)
            await session.execute(
                update(Job)
                .where(Job.id == job.id)
                .values(
                    status="failed",
                    error_message="Job timed out or was interrupted",
                    error_category="timeout",
                    completed_at=datetime.utcnow(),
                )
            )
            cleaned += 1
            logger.warning("Stale job marked failed", job_id=job.id)

        await session.commit()

    return cleaned


async def cleanup_orphan_temp_dirs() -> int:
    """Remove temp dirs not associated with an active job."""
    temp_base = settings.TEMP_DIR
    if not temp_base.exists():
        return 0

    cleaned = 0
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Job.id).where(Job.status.in_(("queued", "starting", "downloading", "processing")))
        )
        active_ids = {row[0] for row in result.fetchall()}

    for dir_path in temp_base.iterdir():
        if dir_path.is_dir() and dir_path.name not in active_ids:
            import shutil
            shutil.rmtree(dir_path, ignore_errors=True)
            cleaned += 1
            logger.debug("Removed orphan temp dir", path=str(dir_path))

    return cleaned


async def run_full_cleanup() -> dict:
    """Run all cleanup tasks and return a summary."""
    expired = await cleanup_expired_files()
    stale = await cleanup_stale_jobs()
    orphan = await cleanup_orphan_temp_dirs()
    logger.info(
        "Cleanup complete",
        expired=expired,
        stale=stale,
        orphan=orphan,
    )
    return {"expired": expired, "stale": stale, "orphan": orphan}
