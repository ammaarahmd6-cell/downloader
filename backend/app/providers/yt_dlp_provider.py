"""Enhanced multi-platform media provider backed by yt-dlp and fallback extractors.

Specifically tailored for:
- YouTube (Videos, Shorts, Music)
- Instagram (Reels, Stories, Posts, Videos)
- TikTok (Videos, Shorts, Sounds)
- Snapchat (Spotlight, Stories)
- Pinterest (Video Pins, Image Pins)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import yt_dlp

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import MediaProvider, MediaUnavailableError, ProviderError
from app.providers.direct_extractors import (
    extract_instagram_fallback,
    extract_pinterest_fallback,
    extract_snapchat_fallback,
    download_fallback_media,
)
from app.schemas.info import FormatOption, MediaInfoResponse
from app.utils.url_resolver import detect_platform, normalize_media_url

logger = get_logger(__name__)
settings = get_settings()

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _classify_format(fmt: dict[str, Any]) -> str:
    """Classify a yt-dlp format dict into video, audio, video+audio, or other."""
    vcodec = fmt.get("vcodec") or "none"
    acodec = fmt.get("acodec") or "none"
    has_video = vcodec != "none"
    has_audio = acodec != "none"
    if has_video and has_audio:
        return "video+audio"
    if has_video:
        return "video"
    if has_audio:
        return "audio"
    return "other"


def _normalize_format(fmt: dict[str, Any]) -> FormatOption:
    """Convert a raw yt-dlp format dict into a FormatOption schema."""
    width = fmt.get("width")
    height = fmt.get("height")
    resolution = fmt.get("resolution")
    if not resolution and width and height:
        resolution = f"{width}x{height}"
    elif not resolution and height:
        resolution = f"{height}p"

    return FormatOption(
        format_id=str(fmt.get("format_id", "")),
        ext=fmt.get("ext", "mp4"),
        format_note=fmt.get("format_note"),
        resolution=resolution,
        width=width,
        height=height,
        fps=fmt.get("fps"),
        vcodec=fmt.get("vcodec") if fmt.get("vcodec") != "none" else None,
        acodec=fmt.get("acodec") if fmt.get("acodec") != "none" else None,
        abr=fmt.get("abr"),
        vbr=fmt.get("vbr"),
        filesize=fmt.get("filesize"),
        filesize_approx=fmt.get("filesize_approx"),
        quality=fmt.get("quality"),
        media_type=_classify_format(fmt),  # type: ignore[arg-type]
        language=fmt.get("language"),
    )


def _build_platform_ydl_opts(platform: str, cookie_file: Path | None = None, *, is_retry: bool = False) -> dict[str, Any]:
    """Build tuned yt-dlp options specifically tailored for each platform.

    For info extraction we intentionally do NOT override YouTube's player_client
    so that yt-dlp uses its own default client negotiation, which returns the
    full set of formats (30+).  Overriding to specific clients like
    web_creator/ios/android/mweb drastically reduces available formats.
    """
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 45,
        "ffmpeg_location": settings.FFMPEG_PATH,
        "http_headers": {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    # Platform-specific tweaks (user-agents only — no format restrictions)
    if platform == "tiktok":
        opts["http_headers"]["User-Agent"] = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
        )
        opts["extractor_args"] = {
            "tiktok": {
                "api_hostname": "api16-normal-c-useast1a.tiktokv.com",
                "app_info": "7355_318.0.0"
            }
        }
    elif platform == "instagram":
        opts["http_headers"]["Sec-Fetch-Site"] = "none"

    # On retry, strip custom headers so yt-dlp uses its own defaults
    if is_retry:
        opts.pop("http_headers", None)
        opts["socket_timeout"] = 60

    if cookie_file and cookie_file.exists():
        opts["cookiefile"] = str(cookie_file)

    return opts


class YtDlpProvider(MediaProvider):
    """
    Primary media extraction & downloading provider.
    Supports YouTube, Instagram, TikTok, Snapchat, Pinterest, and more.
    """

    @property
    def name(self) -> str:
        return "yt-dlp"

    async def can_handle(self, url: str) -> bool:
        """Handles any valid media URL."""
        return True

    async def get_info(self, url: str) -> MediaInfoResponse:
        """Extract media info using normalized URL, smart options, and fallbacks.

        Extraction pipeline:
          1. Normalize / resolve shortened URL
          2. Try yt-dlp with default options (returns full format list)
          3. On failure → retry once with stripped-down options
          4. On second failure → try platform-specific direct fallback extractors
          5. If everything fails → raise a descriptive error
        """
        # 1. Unshorten & clean URL
        resolved_url, platform = await normalize_media_url(url)
        cookie_file = Path(settings.STORAGE_DIR) / "cookies.txt"

        logger.info("Extracting media info", original=url, resolved=resolved_url, platform=platform)

        # 2. Try extraction via yt-dlp (with one retry using simpler options)
        info: dict[str, Any] | None = None
        yt_dlp_error: Exception | None = None

        for attempt, is_retry in enumerate([(False), (True)]):
            ydl_opts = _build_platform_ydl_opts(platform, cookie_file, is_retry=is_retry)
            try:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda opts=ydl_opts: self._extract_info(resolved_url, opts)
                )
                if info:
                    break  # success
            except yt_dlp.utils.DownloadError as exc:
                yt_dlp_error = exc
                logger.warning(
                    "yt-dlp extraction failed",
                    url=resolved_url,
                    attempt=attempt + 1,
                    retry=is_retry,
                    error=str(exc),
                )
            except Exception as exc:
                yt_dlp_error = exc
                logger.warning(
                    "yt-dlp general extraction error",
                    url=resolved_url,
                    attempt=attempt + 1,
                    retry=is_retry,
                    error=str(exc),
                )

            if not is_retry:
                # Brief pause before retry
                await asyncio.sleep(1)

        # 3. If yt-dlp failed, attempt platform-specific direct fallbacks
        if not info:
            fallback_response: MediaInfoResponse | None = None
            if platform == "instagram":
                fallback_response = await extract_instagram_fallback(resolved_url)
            elif platform == "snapchat":
                fallback_response = await extract_snapchat_fallback(resolved_url)
            elif platform == "pinterest":
                fallback_response = await extract_pinterest_fallback(resolved_url)

            if fallback_response:
                logger.info("Fallback extraction succeeded", platform=platform, title=fallback_response.title)
                return fallback_response

            # If fallback also failed or not available, classify error message
            if yt_dlp_error:
                msg = str(yt_dlp_error)
                if "private" in msg.lower() or "login required" in msg.lower():
                    raise MediaUnavailableError("This media is private or requires login") from yt_dlp_error
                if "removed" in msg.lower() or "not found" in msg.lower() or "404" in msg:
                    raise MediaUnavailableError("This media is no longer available or URL is invalid") from yt_dlp_error
                raise ProviderError(f"Could not analyze media: {msg}", category="extraction_error") from yt_dlp_error
            raise ProviderError("Media extraction failed. Please check the URL.", category="extraction_error")

        # 4. Normalize and clean formats
        raw_formats: list[dict] = info.get("formats", [])
        formats = [_normalize_format(f) for f in raw_formats if f.get("ext")]

        # Filter out storyboards and internal manifests
        formats = [
            f for f in formats
            if f.ext not in ("mhtml", "live_head")
            and f.format_id not in ("sb0", "sb1", "sb2", "sb3")
        ]

        # Ensure standard quality entries exist if video formats are detected
        has_video = any(f.height and f.height > 0 for f in formats)
        if not formats or not has_video:
            formats = [
                FormatOption(
                    format_id="best",
                    ext="mp4",
                    format_note="Best Available Quality",
                    resolution="HD",
                    media_type="video+audio",
                ),
                FormatOption(
                    format_id="bestaudio",
                    ext="mp3",
                    format_note="Audio MP3 (320kbps)",
                    media_type="audio",
                    abr=320,
                ),
            ]

        # Sort: highest quality first
        formats.sort(key=lambda f: (f.height or 0, f.quality or 0), reverse=True)

        source_platform = platform if platform != "general" else info.get("extractor_key", "media").lower()

        return MediaInfoResponse(
            url=resolved_url,
            title=info.get("title", "Media Download"),
            thumbnail=info.get("thumbnail"),
            duration=int(info["duration"]) if info.get("duration") else None,
            uploader=info.get("uploader") or info.get("channel") or info.get("creator"),
            uploader_url=info.get("uploader_url") or info.get("channel_url"),
            description=info.get("description"),
            view_count=info.get("view_count"),
            like_count=info.get("like_count"),
            upload_date=info.get("upload_date"),
            source=source_platform,
            webpage_url=info.get("webpage_url", resolved_url),
            formats=formats,
        )

    def _extract_info(self, url: str, opts: dict) -> dict:
        """Synchronous yt-dlp extraction."""
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)  # type: ignore[return-value]

    async def download(
        self,
        url: str,
        format_id: str,
        output_path: str,
        progress_callback: Any | None = None,
    ) -> str:
        """Download media using yt-dlp into the specified output directory with audio guarantee."""
        resolved_url, platform = await normalize_media_url(url)
        output_template = str(Path(output_path) / "%(title)s.%(ext)s")

        progress_hooks = []
        if progress_callback:
            progress_hooks.append(progress_callback)

        # Smart format specification for reliable audio + video merge
        is_audio = (
            format_id in ("mp3", "audio", "bestaudio", "mp3-320", "mp3-128", "m4a-original")
            or "mp3" in format_id
            or "audio" in format_id
        )

        if is_audio:
            fmt_spec = "bestaudio/best"
        elif format_id.endswith("p") and format_id[:-1].isdigit():
            h = format_id[:-1]
            fmt_spec = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
        elif format_id in ("best", "hd_video", "1080p", "720p", "480p", "360p"):
            fmt_spec = "bestvideo+bestaudio/best"
        elif format_id and not ("+" in format_id or format_id in ("18", "22")):
            fmt_spec = f"{format_id}+bestaudio/best"
        else:
            fmt_spec = format_id or "bestvideo+bestaudio/best"

        cookie_file = Path(settings.STORAGE_DIR) / "cookies.txt"
        ydl_opts: dict[str, Any] = {
            "format": fmt_spec,
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 60,
            "ffmpeg_location": settings.FFMPEG_PATH,
            "progress_hooks": progress_hooks,
            "noprogress": False,
            "merge_output_format": "mp4",
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"]
                }
            }
        }

        # Platform specific user-agents if needed
        if platform == "tiktok":
            ydl_opts["http_headers"] = {
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
                )
            }
            ydl_opts["extractor_args"]["tiktok"] = {
                "api_hostname": "api16-normal-c-useast1a.tiktokv.com",
                "app_info": "7355_318.0.0"
            }

        # Add FFmpeg MP3 extraction postprocessor if audio is requested
        if is_audio:
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }
            ]

        if cookie_file.exists():
            ydl_opts["cookiefile"] = str(cookie_file)

        downloaded_file: list[str] = []

        def _postprocessor_hook(d: dict) -> None:
            if d.get("status") == "finished" and d.get("filepath"):
                downloaded_file.append(d["filepath"])

        ydl_opts["postprocessor_hooks"] = [_postprocessor_hook]

        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._do_download(resolved_url, ydl_opts)
            )
        except yt_dlp.utils.DownloadError as exc:
            logger.warning("yt-dlp primary download failed, trying robust fallback...", error=str(exc))
            fallback_path = await download_fallback_media(resolved_url, platform, output_path)
            if fallback_path:
                return fallback_path
                
            logger.warning("Robust fallback also failed, retrying yt-dlp with best format...")
            # Fallback retry with best single stream format
            fallback_opts = dict(ydl_opts)
            fallback_opts["format"] = "best"
            fallback_opts.pop("postprocessors", None)
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self._do_download(resolved_url, fallback_opts)
                )
            except Exception as fallback_exc:
                logger.error("yt-dlp fallback download failed", error=str(fallback_exc))
                raise ProviderError(str(exc), category="download_error") from exc

        # Find the downloaded file
        out_dir = Path(output_path)
        candidates = sorted(
            out_dir.glob("*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if downloaded_file and Path(downloaded_file[-1]).exists():
            return str(downloaded_file[-1])
        if candidates:
            return str(candidates[0])

        raise ProviderError("Download completed but output file was not found", category="missing_output")

    def _do_download(self, url: str, opts: dict) -> None:
        """Synchronous yt-dlp download."""
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
