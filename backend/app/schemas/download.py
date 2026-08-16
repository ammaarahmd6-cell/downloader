"""Pydantic schemas for download requests."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DownloadRequest(BaseModel):
    """Request body for POST /api/download."""

    url: str = Field(..., min_length=1, max_length=2048)
    format_id: str = Field(..., description="Format ID from the info response")
    output_format: str = Field(
        default="mp4",
        description="Desired container format (mp4, mp3, webm, m4a …)",
        pattern=r"^[a-zA-Z0-9]{1,10}$",
    )
    quality: str | None = Field(
        default=None,
        description="Optional quality preset (best, 1080p, 720p, audio …)",
    )


class JobCreatedResponse(BaseModel):
    """Response returned after successfully enqueuing a download job."""

    job_id: str
    status: str = "queued"
    message: str = "Job has been queued for processing"
