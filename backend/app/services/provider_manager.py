"""Provider registry — routes URLs to the correct media provider."""

from __future__ import annotations

from app.core.logging import get_logger
from app.providers.base import MediaProvider, UnsupportedURLError
from app.providers.yt_dlp_provider import YtDlpProvider

logger = get_logger(__name__)


class ProviderManager:
    """
    Manages registered MediaProvider instances.

    Providers are checked in registration order.
    The first provider whose can_handle() returns True is used.
    """

    def __init__(self) -> None:
        self._providers: list[MediaProvider] = []

    def register(self, provider: MediaProvider) -> None:
        """Add a provider to the registry."""
        self._providers.append(provider)
        logger.info("Registered provider", name=provider.name)

    async def get_provider(self, url: str) -> MediaProvider:
        """Return the first provider that can handle the URL."""
        for provider in self._providers:
            if await provider.can_handle(url):
                logger.debug("Provider selected", provider=provider.name, url=url)
                return provider
        raise UnsupportedURLError(url)

    @property
    def provider_names(self) -> list[str]:
        return [p.name for p in self._providers]


# Singleton instance — populated in app startup
_manager: ProviderManager | None = None


def get_provider_manager() -> ProviderManager:
    """Return the application-wide ProviderManager."""
    global _manager
    if _manager is None:
        _manager = ProviderManager()
        _manager.register(YtDlpProvider())
    return _manager
