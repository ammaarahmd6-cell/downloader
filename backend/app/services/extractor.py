"""Media extraction service — validates URLs and delegates to providers."""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.security import URLValidationError, validate_url
from app.providers.base import MediaUnavailableError, ProviderError, UnsupportedURLError
from app.schemas.info import MediaInfoResponse
from app.services.provider_manager import get_provider_manager

logger = get_logger(__name__)


class ExtractionError(Exception):
    """Raised when extraction fails for any reason."""

    def __init__(self, message: str, category: str = "extraction_error") -> None:
        super().__init__(message)
        self.category = category


async def extract_media_info(url: str) -> MediaInfoResponse:
    """
    Validate the URL and extract normalized media metadata.

    Args:
        url: Raw URL supplied by the user.

    Returns:
        MediaInfoResponse with title, thumbnail, formats, etc.

    Raises:
        ExtractionError: On any validation or provider failure.
    """
    # 1. Security validation
    try:
        safe_url = validate_url(url)
    except URLValidationError as exc:
        raise ExtractionError(str(exc), category="invalid_url") from exc

    # 2. Provider selection
    manager = get_provider_manager()
    try:
        provider = await manager.get_provider(safe_url)
    except UnsupportedURLError as exc:
        raise ExtractionError(
            f"No provider can handle this URL. Supported providers: {manager.provider_names}",
            category="unsupported_url",
        ) from exc

    try:
        logger.info("Extracting media info", url=safe_url, provider=provider.name)
    except Exception:
        pass

    # 3. Extraction
    try:
        info = await provider.get_info(safe_url)
    except MediaUnavailableError as exc:
        logger.warning("Media unavailable", url=safe_url, reason=str(exc))
        raise ExtractionError(str(exc), category="media_unavailable") from exc
    except ProviderError as exc:
        logger.warning(
            "Provider error during extraction",
            url=safe_url,
            category=exc.category,
            error=str(exc),
        )
        raise ExtractionError(str(exc), category=exc.category) from exc
    except Exception as exc:
        logger.exception("Unexpected extraction error", url=safe_url, error=str(exc))
        raise ExtractionError(
            f"Extraction failed: {str(exc)}",
            category="provider_error",
        ) from exc

    try:
        # Safe logging without risking Unicode errors
        safe_title = info.title.encode("ascii", errors="replace").decode("ascii")
        logger.info(
            "Extraction complete",
            url=safe_url,
            title=safe_title,
            formats=len(info.formats),
        )
    except Exception:
        pass

    return info
