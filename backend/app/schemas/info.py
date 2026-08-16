"""Pydantic schemas for media info requests and responses."""

from __future__ import annotations

from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator


class MediaInfoRequest(BaseModel):
    """Request body for POST /api/info."""

    url: str = Field(..., description="URL of the media to analyze", min_length=1, max_length=2048)


class FormatOption(BaseModel):
    """A single available format/quality option for the media."""

    format_id: str
    ext: str                          # file extension (mp4, webm, mp3, m4a …)
    format_note: str | None = None    # human-readable quality label
    resolution: str | None = None     # e.g. "1920x1080"
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    vcodec: str | None = None
    acodec: str | None = None
    abr: float | None = None          # audio bitrate kbps
    vbr: float | None = None          # video bitrate kbps
    filesize: int | None = None       # bytes (may be None if unknown)
    filesize_approx: int | None = None
    quality: float | None = None
    media_type: Literal["video", "audio", "video+audio", "other"] = "other"
    language: str | None = None


class MediaInfoResponse(BaseModel):
    """Normalized media info returned to the frontend."""

    url: str
    title: str
    thumbnail: str | None = None
    duration: int | None = None        # seconds
    uploader: str | None = None
    uploader_url: str | None = None
    description: str | None = None
    view_count: int | None = None
    like_count: int | None = None
    upload_date: str | None = None
    source: str                        # provider name, e.g. "youtube"
    webpage_url: str | None = None
    formats: list[FormatOption] = Field(default_factory=list)
