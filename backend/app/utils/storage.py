"""Storage helpers — manage job directories and file lifecycle."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.filenames import job_temp_dir, validate_output_path

logger = get_logger(__name__)


def get_job_temp_dir(job_id: str) -> Path:
    """Create and return an isolated temp directory for the job."""
    settings = get_settings()
    d = job_temp_dir(settings.TEMP_DIR, job_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_completed_dir() -> Path:
    """Return the completed files directory, creating it if needed."""
    settings = get_settings()
    settings.COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
    return settings.COMPLETED_DIR


def move_to_completed(src: str | Path, job_id: str, filename: str) -> Path:
    """
    Move a finished file from temp storage to the completed directory.

    Returns the new absolute path.
    """
    settings = get_settings()
    dest_dir = get_completed_dir() / job_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    # Validate destination is within completed dir
    validate_output_path(dest, settings.COMPLETED_DIR)

    shutil.move(str(src), str(dest))
    logger.info("Moved file to completed", job_id=job_id, dest=str(dest))
    return dest


def delete_job_temp(job_id: str) -> None:
    """Remove the temporary directory for a job."""
    settings = get_settings()
    d = job_temp_dir(settings.TEMP_DIR, job_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        logger.debug("Deleted temp dir", job_id=job_id)


def delete_job_completed(job_id: str) -> None:
    """Remove the completed output directory for a job."""
    settings = get_settings()
    d = settings.COMPLETED_DIR / job_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        logger.debug("Deleted completed dir", job_id=job_id)


def get_file_size(path: str | Path) -> int:
    """Return file size in bytes, or 0 if the file doesn't exist."""
    p = Path(path)
    return p.stat().st_size if p.exists() else 0
