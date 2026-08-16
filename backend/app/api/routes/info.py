"""POST /api/info — extract media metadata."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.schemas.info import MediaInfoRequest, MediaInfoResponse
from app.services.extractor import ExtractionError, extract_media_info

router = APIRouter(prefix="/api", tags=["Media Info"])


@router.post(
    "/info",
    response_model=MediaInfoResponse,
    summary="Analyze a media URL",
    description=(
        "Validates the URL, fetches media metadata using the appropriate provider, "
        "and returns normalized info including title, thumbnail, duration, and available formats."
    ),
)
async def get_media_info(
    request: Request,
    body: MediaInfoRequest,
) -> MediaInfoResponse:
    """Extract and return media metadata for the given URL."""
    try:
        info = await extract_media_info(body.url)
    except ExtractionError as exc:
        category = exc.category
        status_map = {
            "invalid_url": 422,
            "unsupported_url": 422,
            "media_unavailable": 404,
            "extraction_error": 502,
            "provider_error": 502,
        }
        raise HTTPException(
            status_code=status_map.get(category, 502),
            detail={"message": str(exc), "category": category},
        ) from exc

    return info
