import os
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import URLValidationError, validate_url
from app.db.session import get_db_session
from app.models.job import Job
from app.schemas.download import DownloadRequest, JobCreatedResponse
from app.services.provider_manager import get_provider_manager
from app.utils.filenames import safe_filename
from app.workers.tasks import download_media

router = APIRouter(prefix="/api", tags=["Download"])
logger = get_logger(__name__)


@router.get(
    "/direct-download",
    summary="Direct media download",
    description="Downloads media directly and streams it to the browser's native download manager.",
)
async def direct_download(
    url: str,
    format_id: str = "best",
    output_format: str = "mp4",
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Validate request, download media in real-time, stream file directly to user browser."""
    try:
        safe_url = validate_url(url)
    except URLValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "category": "invalid_url"},
        ) from exc

    manager = get_provider_manager()
    provider = await manager.get_provider(safe_url)

    job_id = str(uuid.uuid4())
    temp_dir = Path(get_settings().TEMP_DIR) / job_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        downloaded_path_str = await provider.download(
            url=safe_url,
            format_id=format_id,
            output_path=str(temp_dir),
        )
        file_path = Path(downloaded_path_str)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File download failed.")

        ext = file_path.suffix.lstrip(".") or output_format
        clean_name = safe_filename(file_path.stem, ext)

        def _cleanup():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

        background_tasks.add_task(_cleanup)

        return FileResponse(
            path=str(file_path),
            filename=clean_name,
            media_type="application/octet-stream",
        )
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.exception("Direct download failed", url=url)
        raise HTTPException(
            status_code=500,
            detail={"message": f"Download error: {str(exc)}", "category": "download_error"},
        ) from exc


@router.post(
    "/download",
    response_model=JobCreatedResponse,
    status_code=202,
    summary="Enqueue a media download job",
    description=(
        "Creates a background job to download and process the specified media format. "
        "Returns a job_id that can be polled for status. "
        "The download runs asynchronously — the HTTP response returns immediately."
    ),
)
async def create_download_job(
    body: DownloadRequest,
    background_tasks: BackgroundTasks,
) -> JobCreatedResponse:
    """Validate request, create DB record, enqueue Celery task."""

    # Validate URL
    try:
        safe_url = validate_url(body.url)
    except URLValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "category": "invalid_url"},
        ) from exc

    # Create job record
    from app.db.insforge import db_client
    
    job_id = str(uuid.uuid4())
    job_data = {
        "id": job_id,
        "source_url": safe_url,
        "status": "queued",
        "format_id": body.format_id,
        "output_format": body.output_format,
        "quality": body.quality,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    await db_client.create_job(job_data)

    # Enqueue Background Task natively
    try:
        background_tasks.add_task(
            download_media,
            job_id=job_id,
            url=safe_url,
            format_id=body.format_id,
            output_format=body.output_format,
            quality=body.quality,
        )
    except Exception as exc:
        logger.exception("Failed to enqueue task", job_id=job_id)
        raise HTTPException(
            status_code=503,
            detail={"message": "Job queue is unavailable. Please try again.", "category": "queue_error"},
        ) from exc

    logger.info("Job queued", job_id=job_id, format_id=body.format_id)

    return JobCreatedResponse(
        job_id=job_id,
        status="queued",
        message="Your download has been queued and will start shortly.",
    )
