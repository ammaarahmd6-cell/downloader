"""Admin dashboard data endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.job import Job

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/stats", summary="Admin statistics dashboard")
async def get_admin_stats(
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return aggregate statistics for the admin dashboard."""

    # Total jobs by status
    result = await db.execute(
        select(Job.status, func.count(Job.id)).group_by(Job.status)
    )
    status_counts = dict(result.fetchall())

    # Storage usage
    from app.core.config import get_settings
    settings = get_settings()
    total_bytes = 0
    if settings.COMPLETED_DIR.exists():
        for f in settings.COMPLETED_DIR.rglob("*"):
            if f.is_file():
                total_bytes += f.stat().st_size

    # Recent jobs
    recent_result = await db.execute(
        select(Job)
        .order_by(Job.created_at.desc())
        .limit(20)
    )
    recent_jobs = recent_result.scalars().all()

    return {
        "summary": {
            "total": sum(status_counts.values()),
            "queued": status_counts.get("queued", 0),
            "active": (
                status_counts.get("starting", 0)
                + status_counts.get("downloading", 0)
                + status_counts.get("processing", 0)
            ),
            "completed": status_counts.get("completed", 0),
            "failed": status_counts.get("failed", 0),
            "cancelled": status_counts.get("cancelled", 0),
            "expired": status_counts.get("expired", 0),
        },
        "storage_bytes": total_bytes,
        "storage_mb": round(total_bytes / (1024 * 1024), 2),
        "recent_jobs": [
            {
                "id": j.id,
                "status": j.status,
                "title": j.title,
                "format": j.output_format,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in recent_jobs
        ],
    }
