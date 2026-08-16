"""Safe filename utilities."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

# Characters forbidden on Windows and Unix filesystems
_FORBIDDEN_CHARS_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')
_WHITESPACE_RE = re.compile(r"\s+")
_LEADING_DOTS_RE = re.compile(r"^\.+")

# Extensions that could be dangerous on a web server
_DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".ps1", ".py", ".php",
    ".rb", ".pl", ".jar", ".msi", ".dll", ".so",
}


def safe_filename(title: str, ext: str, max_length: int = 150) -> str:
    """
    Produce a filesystem-safe filename from a media title and extension.

    Args:
        title: Raw media title (may contain unicode, special chars, etc.)
        ext: File extension WITHOUT leading dot (e.g. "mp4", "mp3")
        max_length: Maximum total filename length (default 150)

    Returns:
        A safe filename string like ``my_video_title.mp4``
    """
    # Normalize unicode
    title = unicodedata.normalize("NFKC", title)

    # Remove forbidden characters
    title = _FORBIDDEN_CHARS_RE.sub("_", title)

    # Collapse whitespace to underscores
    title = _WHITESPACE_RE.sub("_", title)

    # Remove leading dots (hidden files on Unix)
    title = _LEADING_DOTS_RE.sub("", title)

    # Strip leading/trailing underscores and spaces
    title = title.strip("_. ")

    # Ensure non-empty
    if not title:
        title = "download"

    # Sanitize extension
    ext = ext.lstrip(".").lower()
    ext = re.sub(r"[^a-z0-9]", "", ext) or "bin"

    dot_ext = f".{ext}"
    if dot_ext.lower() in _DANGEROUS_EXTENSIONS:
        dot_ext = ".bin"

    # Truncate title to fit within max_length
    max_title_len = max_length - len(dot_ext)
    title = title[:max_title_len]

    return f"{title}{dot_ext}"


def job_temp_dir(base_temp_dir: str | Path, job_id: str) -> Path:
    """Return the isolated temporary directory path for a job."""
    # Sanitize job_id to prevent path traversal
    safe_id = re.sub(r"[^a-zA-Z0-9\-]", "", job_id)
    return Path(base_temp_dir) / safe_id


def validate_output_path(path: str | Path, allowed_base: str | Path) -> Path:
    """
    Ensure *path* is within *allowed_base* to prevent path traversal.

    Raises:
        ValueError: If path escapes the allowed base directory.
    """
    resolved = Path(path).resolve()
    base = Path(allowed_base).resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError(
            f"Path '{resolved}' is outside the allowed base directory '{base}'"
        ) from exc
    return resolved
