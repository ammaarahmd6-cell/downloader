"""Background tasks for media download/processing jobs."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import ProviderError
from app.utils.filenames import safe_filename
from app.utils.storage import (
    delete_job_temp,
    get_file_size,
    get_job_temp_dir,
    move_to_completed,
)

logger = get_logger(__name__)
settings = get_settings()


def _run_async(coro):
    """Run an async coroutine synchronously inside a background thread."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _update_job_status(job_id: str, **kwargs) -> None:
    """Update job fields in the database asynchronously."""
    from app.db.insforge import db_client
    try:
        # Convert any datetime objects to ISO strings
        safe_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, datetime):
                safe_kwargs[k] = v.isoformat()
            else:
                safe_kwargs[k] = v
                
        await db_client.update_job(job_id, safe_kwargs)
    except Exception as e:
        logger.error("Failed to update job status", error=str(e), job_id=job_id)


async def download_media(
    job_id: str,
    url: str,
    format_id: str,
    output_format: str = "mp4",
    quality: str | None = None,
) -> dict[str, Any]:
    """
    Background task: download and process media for a given job.
    Runs asynchronously natively within FastAPI.

    Lifecycle:
        queued → starting → downloading → processing → completed
                                                    ↘ failed
    """
    logger.info("Starting download task natively", job_id=job_id, url=url, format_id=format_id)

    temp_dir = get_job_temp_dir(job_id)
    downloaded_path: str | None = None

    try:
        # ── 1. Starting ────────────────────────────────────────────────────
        await _update_job_status(
            job_id,
            status="starting",
            started_at=datetime.utcnow(),
            stage="Initializing",
        )

        # ── 2. Provider selection ──────────────────────────────────────────
        from app.services.provider_manager import get_provider_manager

        manager = get_provider_manager()
        provider = await manager.get_provider(url)

        await _update_job_status(job_id, status="downloading", stage="Downloading media", progress=5.0)

        # ── 3. Progress tracking ───────────────────────────────────────────
        last_update = 0.0

        def progress_hook(d: dict) -> None:
            nonlocal last_update
            if d["status"] == "downloading":
                now = time.time()
                # Throttle updates to twice a second to prevent DB locking
                if now - last_update < 0.5:
                    return
                last_update = now

                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                pct = (downloaded / total * 80) if total > 0 else 0
                speed = d.get("_speed_str", "")
                eta = d.get("_eta_str", "")
                
                # We are in the executor thread, so use _run_async to run the db update
                _run_async(
                    _update_job_status(
                        job_id,
                        progress=min(pct + 5, 85),
                        speed=speed,
                        eta=eta,
                        stage="Downloading",
                    )
                )

        # ── 4. Download ────────────────────────────────────────────────────
        downloaded_path = await provider.download(
            url=url,
            format_id=format_id,
            output_path=str(temp_dir),
            progress_callback=progress_hook,
        )

        logger.info("Download complete", job_id=job_id, path=downloaded_path)
        await _update_job_status(
            job_id, status="processing", stage="Processing", progress=88.0
        )

        # ── 5. Build safe output filename ──────────────────────────────────
        src = Path(downloaded_path)
        ext = src.suffix.lstrip(".") or output_format
        filename = safe_filename(src.stem, ext)

        # ── 6. Move to completed storage ───────────────────────────────────
        dest = move_to_completed(src, job_id, filename)
        file_size = get_file_size(dest)
        expires_at = datetime.utcnow() + timedelta(seconds=settings.FILE_RETENTION_SECONDS)

        # ── 7. Mark completed ──────────────────────────────────────────────
        await _update_job_status(
            job_id,
            status="completed",
            progress=100.0,
            stage="Completed",
            speed=None,
            eta=None,
            filename=filename,
            file_path=str(dest),
            file_size=file_size,
            completed_at=datetime.utcnow(),
            expires_at=expires_at,
        )

        logger.info(
            "Job completed natively",
            job_id=job_id,
            filename=filename,
            file_size=file_size,
        )
        return {"job_id": job_id, "status": "completed", "filename": filename}

    except Exception as exc:
        logger.exception("Job failed", job_id=job_id, error=str(exc))

        category = getattr(exc, "category", "unknown_error")
        safe_message = _safe_error_message(exc)

        await _update_job_status(
            job_id,
            status="failed",
            stage="Failed",
            error_message=safe_message,
            error_category=category,
            completed_at=datetime.utcnow(),
        )

        # Clean up temp files on failure
        delete_job_temp(job_id)
        raise

    finally:
        # Always clean the temp dir (completed files are in completed/)
        if downloaded_path:
            delete_job_temp(job_id)


def _safe_error_message(exc: Exception) -> str:
    """Return a user-safe error message (no stack traces, no paths)."""
    known = {
        "invalid_url": "The URL is invalid or not supported.",
        "unsupported_url": "This URL is not supported by any available provider.",
        "media_unavailable": "The media is unavailable (private, removed, or region-restricted).",
        "download_error": "Download failed. The media may be unavailable.",
        "extraction_error": "Failed to analyze the media URL.",
        "provider_error": "A provider error occurred. Please try again.",
    }
    category = getattr(exc, "category", None)
    return known.get(category, "An error occurred during processing. Please try again.")
