"""Pydantic schemas for job status responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


JobStatus = Literal[
    "queued",
    "starting",
    "analyzing",
    "downloading",
    "processing",
    "completed",
    "failed",
    "cancelled",
    "expired",
]


class JobStatusResponse(BaseModel):
    """Status of a background job returned to the frontend."""

    job_id: str
    status: JobStatus
    progress: float = 0.0
    speed: str | None = None
    eta: str | None = None
    stage: str | None = None
    title: str | None = None
    filename: str | None = None
    file_size: int | None = None
    output_format: str | None = None
    error_message: str | None = None
    error_category: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None


class JobListResponse(BaseModel):
    """Paginated list of jobs."""

    jobs: list[JobStatusResponse]
    total: int
    page: int
    page_size: int
