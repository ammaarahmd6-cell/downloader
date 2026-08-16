"""URL resolution, redirection unwrapping, and platform detection utilities."""

from __future__ import annotations

import re
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)
PlatformType = Literal["youtube", "instagram", "tiktok", "snapchat", "pinterest", "facebook", "general"]

# Common tracking parameters to strip
TRACKING_PARAMS = {
    "igsh",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "si",
    "feature",
    "sender_device",
    "sender_web_id",
    "is_from_webapp",
    "fbclid",
    "gclid",
    "_ga",
    "ref",
    "src",
    "share_id",
}

# Domains that require redirect following
KNOWN_SHORTENER_DOMAINS = {
    "pin.it",
    "vt.tiktok.com",
    "vm.tiktok.com",
    "t.snapchat.com",
    "youtu.be",
    "fb.watch",
    "t.co",
    "bit.ly",
    "tinyurl.com",
    "instagr.am",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def detect_platform(url: str) -> PlatformType:
    """Identify which platform the URL belongs to."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except Exception:
        return "general"

    if any(d in host for d in ("youtube.com", "youtu.be", "youtube-nocookie.com", "m.youtube.com")):
        return "youtube"
    if any(d in host for d in ("instagram.com", "instagr.am")):
        return "instagram"
    if any(d in host for d in ("tiktok.com", "vt.tiktok.com", "vm.tiktok.com")):
        return "tiktok"
    if any(d in host for d in ("snapchat.com", "story.snapchat.com", "t.snapchat.com")):
        return "snapchat"
    if any(d in host for d in ("pinterest.com", "pin.it", "pinterest.co.uk", "pinterest.ca")):
        return "pinterest"
    if any(d in host for d in ("facebook.com", "fb.watch", "fb.com")):
        return "facebook"

    return "general"


def clean_tracking_params(url: str) -> str:
    """
    Remove unnecessary marketing and tracking query parameters from the URL
    while preserving essential query parameters (like video IDs on YouTube).
    """
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url

        query_dict = parse_qs(parsed.query, keep_blank_values=True)
        # Filter out tracking keys
        cleaned_dict = {
            k: v for k, v in query_dict.items() if k.lower() not in TRACKING_PARAMS
        }

        new_query = urlencode(cleaned_dict, doseq=True)
        cleaned_url = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment,
            )
        )
        return cleaned_url
    except Exception as exc:
        logger.debug("Failed to clean tracking parameters", url=url, error=str(exc))
        return url


async def resolve_redirects(url: str, max_hops: int = 5) -> str:
    """
    Unshorten URLs by following HTTP redirects asynchronously.
    Only queries network if the domain is a known shortener or share link.
    """
    cleaned = clean_tracking_params(url)
    try:
        parsed = urlparse(cleaned)
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()
    except Exception:
        return cleaned

    is_shortener = (
        any(s in host for s in KNOWN_SHORTENER_DOMAINS)
        or host in ("bit.ly", "tinyurl.com", "t.co")
        or (host == "tiktok.com" and path.startswith("/t/"))
        or (host == "snapchat.com" and path.startswith("/t/"))
    )

    # If it's already a full standard URL (e.g. youtube.com/watch, instagram.com/reel), skip network hop
    if not is_shortener:
        return cleaned

    logger.info("Resolving shortened URL", url=cleaned)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=max_hops,
            timeout=8.0,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            try:
                response = await client.head(cleaned)
                final_url = str(response.url)
                if final_url and final_url != cleaned:
                    logger.info("Resolved redirect via HEAD", initial=cleaned, final=final_url)
                    return clean_tracking_params(final_url)
            except Exception:
                pass

            response = await client.get(cleaned)
            final_url = str(response.url)
            logger.info("Resolved redirect via GET", initial=cleaned, final=final_url)
            return clean_tracking_params(final_url)

    except Exception as exc:
        logger.warning("Redirect resolution failed; using original URL", url=cleaned, error=str(exc))
        return cleaned


async def normalize_media_url(url: str) -> tuple[str, PlatformType]:
    """
    Perform full URL normalization:
    1. Strip whitespace
    2. Resolve shortened redirect URLs (e.g. pin.it, vt.tiktok.com, t.snapchat.com)
    3. Clean tracking parameters
    4. Detect target platform
    """
    if not url:
        return "", "general"

    trimmed = url.strip()
    resolved_url = await resolve_redirects(trimmed)
    platform = detect_platform(resolved_url)

    return resolved_url, platform
