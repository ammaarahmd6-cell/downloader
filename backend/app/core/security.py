"""SSRF protection, URL validation, and security utilities."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from app.core.logging import get_logger

logger = get_logger(__name__)

# Allowed URL schemes
ALLOWED_SCHEMES = {"https", "http"}

# Block these private/reserved IP ranges
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),   # link-local
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),    # shared address space
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]

# Blocked hostnames
_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "169.254.169.254",     # AWS/GCP metadata
    "100.100.100.200",     # Alibaba Cloud metadata
}

# Maximum URL length
MAX_URL_LENGTH = 2048


class URLValidationError(ValueError):
    """Raised when a URL fails security validation."""
    pass


def validate_url(url: str) -> str:
    """
    Validate and sanitize a URL for safe use.

    Checks:
    - URL format validity
    - Allowed scheme (http/https only)
    - No private/reserved IP targets (SSRF protection)
    - No localhost or internal hostnames
    - Reasonable length

    Returns the normalized URL if valid, raises URLValidationError otherwise.
    """
    if not url or not isinstance(url, str):
        raise URLValidationError("URL must be a non-empty string")

    url = url.strip()

    if len(url) > MAX_URL_LENGTH:
        raise URLValidationError(f"URL exceeds maximum length of {MAX_URL_LENGTH} characters")

    # Basic format check
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise URLValidationError(f"Malformed URL: {exc}") from exc

    # Scheme check
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise URLValidationError(
            f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed."
        )

    # Host required
    host = parsed.hostname
    if not host:
        raise URLValidationError("URL must have a valid hostname")

    # Blocked hostname check
    if host.lower() in _BLOCKED_HOSTNAMES:
        logger.warning("Blocked hostname access attempt", hostname=host)
        raise URLValidationError(f"Access to '{host}' is not permitted")

    # IP address SSRF check
    try:
        ip = ipaddress.ip_address(host)
    except (ValueError, ipaddress.AddressValueError):
        # Not an IP address literal — it's a domain name; safe to proceed
        pass
    else:
        # It IS an IP address — check if it's in a blocked range
        _check_ip_blocked(ip, host)

    # Prevent user info in URL (username:password@host)
    if parsed.username or parsed.password:
        raise URLValidationError("URLs with credentials are not permitted")

    logger.debug("URL passed security validation", url=url)
    return url


def _check_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, host: str) -> None:
    """Raise URLValidationError if the IP is in a blocked range."""
    for network in _BLOCKED_NETWORKS:
        if ip in network:
            logger.warning("Blocked private IP access attempt", host=host, ip=str(ip))
            raise URLValidationError(
                "Access to private/reserved IP addresses is not permitted"
            )


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """
    Produce a safe filesystem filename from an arbitrary string.

    - Strips path separators and null bytes
    - Removes control characters
    - Collapses whitespace
    - Limits length
    - Never returns a blank string
    """
    if not name:
        return "download"

    # Remove null bytes and control characters
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)

    # Replace path separators and dangerous chars
    name = re.sub(r'[/\\:*?"<>|]', "_", name)

    # Collapse whitespace/underscores
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"_+", "_", name)

    # Remove leading/trailing dots and underscores
    name = name.strip("._")

    # Limit length (leave room for extension)
    name = name[:max_length]

    return name or "download"
