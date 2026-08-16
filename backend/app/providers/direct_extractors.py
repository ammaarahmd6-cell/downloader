"""Direct lightweight fallback extractors for social media platforms.

Used when standard yt-dlp encounters anti-bot restrictions, rate limits, or cookies requirements.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import aiofiles
import httpx

from app.core.logging import get_logger
from app.schemas.info import FormatOption, MediaInfoResponse

logger = get_logger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def _extract_og_meta(html: str) -> dict[str, str]:
    """Extract OpenGraph and Twitter meta tags from HTML."""
    meta_tags: dict[str, str] = {}
    patterns = [
        r'<meta\s+property=["\']og:([^"\']+)["\']\s+content=["\']([^"\']*)["\']',
        r'<meta\s+content=["\']([^"\']*)["\']\s+property=["\']og:([^"\']+)["\']',
        r'<meta\s+name=["\']twitter:([^"\']+)["\']\s+content=["\']([^"\']*)["\']',
        r'<meta\s+content=["\']([^"\']*)["\']\s+name=["\']twitter:([^"\']+)["\']',
    ]

    for p in patterns:
        for match in re.finditer(p, html, re.IGNORECASE):
            groups = match.groups()
            if len(groups) == 2:
                if "name=" in p or "property=" in p:
                    key, val = groups[0].lower(), groups[1]
                else:
                    val, key = groups[0], groups[1].lower()
                if key not in meta_tags and val:
                    meta_tags[key] = val

    # Also extract title
    title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match and "title" not in meta_tags:
        meta_tags["page_title"] = title_match.group(1).strip()

    return meta_tags


async def extract_instagram_fallback(url: str) -> MediaInfoResponse | None:
    """Extract public Instagram post/reel video info."""
    logger.info("Attempting Instagram fallback extraction", url=url)
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=12.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None

            html = resp.text
            meta = _extract_og_meta(html)

            video_url = meta.get("video") or meta.get("video:secure_url") or meta.get("video:url")
            image_url = meta.get("image") or meta.get("image:secure_url")
            title = meta.get("title") or meta.get("description") or meta.get("page_title") or "Instagram Post"

            # Clean title
            title = re.sub(r"\s*\|\s*Instagram.*$", "", title, flags=re.IGNORECASE).strip()

            formats: list[FormatOption] = []
            if video_url:
                formats.append(
                    FormatOption(
                        format_id="hd_video",
                        ext="mp4",
                        format_note="HD Video (Direct MP4)",
                        resolution="1080p",
                        width=1080,
                        height=1920,
                        media_type="video+audio",
                    )
                )
                formats.append(
                    FormatOption(
                        format_id="bestaudio",
                        ext="mp3",
                        format_note="Audio MP3 (320kbps)",
                        media_type="audio",
                        abr=320,
                    )
                )
            elif image_url:
                formats.append(
                    FormatOption(
                        format_id="image_original",
                        ext="jpg",
                        format_note="High Resolution Image (JPEG)",
                        resolution="Original",
                        media_type="other",
                    )
                )

            if not formats:
                return None

            return MediaInfoResponse(
                url=url,
                title=title or "Instagram Media",
                thumbnail=image_url,
                source="instagram",
                webpage_url=url,
                formats=formats,
            )
    except Exception as exc:
        logger.warning("Instagram fallback failed", error=str(exc))
        return None


async def extract_snapchat_fallback(url: str) -> MediaInfoResponse | None:
    """Extract public Snapchat Spotlight or Story info."""
    logger.info("Attempting Snapchat fallback extraction", url=url)
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=12.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None

            html = resp.text
            meta = _extract_og_meta(html)

            video_url = meta.get("video") or meta.get("video:secure_url")
            image_url = meta.get("image") or meta.get("image:secure_url")
            title = meta.get("title") or meta.get("page_title") or "Snapchat Spotlight"
            title = re.sub(r"\s*\|\s*Snapchat.*$", "", title, flags=re.IGNORECASE).strip()

            formats = [
                FormatOption(
                    format_id="1080p",
                    ext="mp4",
                    format_note="HD Video (1080p MP4)",
                    resolution="1080x1920",
                    width=1080,
                    height=1920,
                    media_type="video+audio",
                ),
                FormatOption(
                    format_id="720p",
                    ext="mp4",
                    format_note="HD Video (720p MP4)",
                    resolution="720x1280",
                    width=720,
                    height=1280,
                    media_type="video+audio",
                ),
                FormatOption(
                    format_id="bestaudio",
                    ext="mp3",
                    format_note="Audio MP3",
                    media_type="audio",
                    abr=320,
                ),
            ]

            return MediaInfoResponse(
                url=url,
                title=title or "Snapchat Video",
                thumbnail=image_url,
                source="snapchat",
                webpage_url=url,
                formats=formats,
            )
    except Exception as exc:
        logger.warning("Snapchat fallback failed", error=str(exc))
        return None


async def extract_pinterest_fallback(url: str) -> MediaInfoResponse | None:
    """Extract Pinterest pin video or high-res image."""
    logger.info("Attempting Pinterest fallback extraction", url=url)
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=12.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None

            html = resp.text
            meta = _extract_og_meta(html)

            title = meta.get("title") or meta.get("description") or meta.get("page_title") or "Pinterest Pin"
            title = re.sub(r"\s*\|\s*Pinterest.*$", "", title, flags=re.IGNORECASE).strip()
            image_url = meta.get("image") or meta.get("image:secure_url")

            # Search for video URLs in Pinterest page JSON data
            video_match = re.search(r'https?://v\.pinimg\.com/videos/mc/[^"\'\s]+\.mp4', html)
            video_url = video_match.group(0) if video_match else None

            formats: list[FormatOption] = []
            if video_url or meta.get("video"):
                formats.append(
                    FormatOption(
                        format_id="1080p",
                        ext="mp4",
                        format_note="Full HD Video (1080p MP4)",
                        resolution="1080p",
                        media_type="video+audio",
                    )
                )
                formats.append(
                    FormatOption(
                        format_id="720p",
                        ext="mp4",
                        format_note="HD Video (720p MP4)",
                        resolution="720p",
                        media_type="video+audio",
                    )
                )
                formats.append(
                    FormatOption(
                        format_id="bestaudio",
                        ext="mp3",
                        format_note="Audio MP3 (320kbps)",
                        media_type="audio",
                        abr=320,
                    )
                )
            elif image_url:
                formats.append(
                    FormatOption(
                        format_id="image_hd",
                        ext="jpg",
                        format_note="High-Res Image (Original JPEG)",
                        resolution="Original",
                        media_type="other",
                    )
                )

            if not formats:
                formats.append(
                    FormatOption(
                        format_id="best",
                        ext="mp4",
                        format_note="Best Quality (MP4)",
                        resolution="HD",
                        media_type="video+audio",
                    )
                )

            return MediaInfoResponse(
                url=url,
                title=title or "Pinterest Media",
                thumbnail=image_url,
                source="pinterest",
                webpage_url=url,
                formats=formats,
            )
    except Exception as exc:
        logger.warning("Pinterest fallback failed", error=str(exc))
        return None


async def download_fallback_media(url: str, platform: str, output_path: str) -> str | None:
    """Download media using robust direct API fallbacks, bypassing yt-dlp."""
    logger.info("Starting fallback download", url=url, platform=platform)
    try:
        video_url = None
        ext = "mp4"

        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15.0) as client:
            if platform == "tiktok":
                api_url = f"https://www.tikwm.com/api/?url={url}"
                resp = await client.get(api_url)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 0 and data.get("data", {}).get("play"):
                        video_url = data["data"]["play"]
            elif platform == "instagram":
                resp = await client.get(url)
                meta = _extract_og_meta(resp.text)
                video_url = meta.get("video") or meta.get("video:secure_url") or meta.get("video:url")
            elif platform == "snapchat":
                resp = await client.get(url)
                meta = _extract_og_meta(resp.text)
                video_url = meta.get("video") or meta.get("video:secure_url")
            elif platform == "pinterest":
                resp = await client.get(url)
                html = resp.text
                meta = _extract_og_meta(html)
                video_match = re.search(r'https?://v\.pinimg\.com/videos/mc/[^"\'\s]+\.mp4', html)
                video_url = video_match.group(0) if video_match else meta.get("video")

            if not video_url:
                logger.error("Fallback downloader could not find video URL", platform=platform)
                return None

            from pathlib import Path
            import uuid
            out_file = Path(output_path) / f"fallback_{uuid.uuid4().hex[:8]}.{ext}"

            async with client.stream("GET", video_url) as stream_resp:
                stream_resp.raise_for_status()
                async with aiofiles.open(out_file, "wb") as f:
                    async for chunk in stream_resp.aiter_bytes(chunk_size=8192):
                        await f.write(chunk)
            
            logger.info("Fallback download successful", path=str(out_file))
            return str(out_file)

    except Exception as exc:
        logger.error("Fallback download failed", error=str(exc))
        return None
