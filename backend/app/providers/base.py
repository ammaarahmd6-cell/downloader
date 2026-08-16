"""Abstract base class for media providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.info import MediaInfoResponse


class MediaProvider(ABC):
    """
    Abstract interface that all media providers must implement.

    Adding a new provider:
    1. Subclass MediaProvider
    2. Implement can_handle, get_info, download
    3. Register the provider in ProviderManager
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this provider (e.g., 'youtube', 'yt-dlp')."""
        ...

    @abstractmethod
    async def can_handle(self, url: str) -> bool:
        """Return True if this provider can process the given URL."""
        ...

    @abstractmethod
    async def get_info(self, url: str) -> MediaInfoResponse:
        """
        Extract and return normalized media metadata for the given URL.

        Raises:
            ProviderError: If extraction fails.
            UnsupportedURLError: If the URL is not supported by this provider.
        """
        ...

    @abstractmethod
    async def download(
        self,
        url: str,
        format_id: str,
        output_path: str,
        progress_callback: Any | None = None,
    ) -> str:
        """
        Download media to *output_path*.

        Args:
            url: Source URL.
            format_id: Provider-specific format identifier.
            output_path: Directory or file path for output.
            progress_callback: Optional callable(progress_dict) for status updates.

        Returns:
            Absolute path to the downloaded file.

        Raises:
            ProviderError: On download failure.
        """
        ...


class ProviderError(Exception):
    """Raised when a provider encounters a non-recoverable error."""

    def __init__(self, message: str, category: str = "provider_error") -> None:
        super().__init__(message)
        self.category = category


class UnsupportedURLError(ProviderError):
    """Raised when no provider can handle the given URL."""

    def __init__(self, url: str) -> None:
        super().__init__(f"No provider can handle URL: {url}", category="unsupported_url")
        self.url = url


class MediaUnavailableError(ProviderError):
    """Raised when media exists but is unavailable (private, removed, etc.)."""

    def __init__(self, reason: str = "Media is unavailable") -> None:
        super().__init__(reason, category="media_unavailable")
