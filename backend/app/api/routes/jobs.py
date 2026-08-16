"""Job status, file serving, and cancellation endpoints."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.insforge import db_client
from app.schemas.jobs import JobStatusResponse
from app.utils.filenames import validate_output_path

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])
logger = get_logger(__name__)
settings = get_settings()

async def _get_job(job_id: str) -> dict:
    """Fetch a job by ID or raise 404."""
    job = await db_client.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"message": "Job not found", "category": "not_found"})
    return job


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
    description="Poll this endpoint to get the current status and progress of a download job.",
)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Return the current status and progress of a job."""
    job = await _get_job(job_id)
    return JobStatusResponse(
        job_id=job["id"],
        status=job["status"],  # type: ignore[arg-type]
        progress=job.get("progress", 0.0),
        speed=job.get("speed"),
        eta=job.get("eta"),
        stage=job.get("stage"),
        title=job.get("title"),
        filename=job.get("filename"),
        file_size=job.get("file_size"),
        output_format=job.get("output_format"),
        error_message=job.get("error_message"),
        error_category=job.get("error_category"),
        created_at=job.get("created_at"),
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        expires_at=job.get("expires_at"),
    )


@router.get(
    "/{job_id}/file",
    summary="Download the completed file",
    description=(
        "Returns the processed media file for a completed job. "
        "The file is served with the correct Content-Type and Content-Disposition headers. "
        "Files are automatically expired after the configured retention period."
    ),
)
async def download_job_file(job_id: str) -> FileResponse:
    """Serve the completed file securely."""
    job = await _get_job(job_id)

    if job["status"] == "expired":
        raise HTTPException(
            status_code=410,
            detail={"message": "This file has expired and been deleted.", "category": "expired"},
        )

    if job["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail={"message": f"Job is not complete yet (status: {job['status']})", "category": "not_ready"},
        )

    file_path = job.get("file_path")
    if not file_path:
        raise HTTPException(
            status_code=404,
            detail={"message": "Output file not found", "category": "missing_file"},
        )

    # Path traversal protection
    try:
        safe_path = validate_output_path(file_path, settings.COMPLETED_DIR)
    except ValueError:
        logger.error("Path traversal attempt blocked", job_id=job_id, path=file_path)
        raise HTTPException(status_code=403, detail="Access denied")

    if not safe_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"message": "Output file not found on disk", "category": "missing_file"},
        )

    return FileResponse(
        path=str(safe_path),
        filename=job.get("filename") or safe_path.name,
        media_type="application/octet-stream",
    )


@router.post(
    "/{job_id}/cancel",
    summary="Cancel a queued or active job",
    description="Attempts to cancel a job. Queued jobs are cancelled immediately; active jobs may take a moment.",
)
async def cancel_job(job_id: str) -> dict:
    """Cancel a job if it's in a cancellable state."""
    job = await _get_job(job_id)

    cancellable = {"queued", "starting", "analyzing", "downloading", "processing"}
    if job["status"] not in cancellable:
        raise HTTPException(
            status_code=409,
            detail={"message": f"Job in status '{job['status']}' cannot be cancelled", "category": "not_cancellable"},
        )

    # Clean up temp files
    from app.utils.storage import delete_job_temp
    delete_job_temp(job_id)

    await db_client.update_job(job_id, {"status": "cancelled", "stage": "Cancelled"})

    logger.info("Job cancelled", job_id=job_id)
    return {"job_id": job_id, "status": "cancelled"}

