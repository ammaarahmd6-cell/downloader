"""Tests for URL validation and SSRF protection."""

from __future__ import annotations

import pytest

from app.core.security import URLValidationError, validate_url


class TestValidURL:
    """Valid URLs that should pass validation."""

    def test_https_youtube(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert validate_url(url) == url

    def test_http_url(self):
        url = "http://vimeo.com/123456789"
        assert validate_url(url) == url

    def test_url_with_trailing_space_stripped(self):
        url = "  https://www.youtube.com/watch?v=abc  "
        assert validate_url(url) == url.strip()


class TestInvalidURL:
    """Invalid or dangerous URLs that should be rejected."""

    def test_empty_string(self):
        with pytest.raises(URLValidationError):
            validate_url("")

    def test_none_raises(self):
        with pytest.raises((URLValidationError, AttributeError)):
            validate_url(None)  # type: ignore

    def test_ftp_scheme_rejected(self):
        with pytest.raises(URLValidationError, match="scheme"):
            validate_url("ftp://example.com/file.mp4")

    def test_file_scheme_rejected(self):
        with pytest.raises(URLValidationError, match="scheme"):
            validate_url("file:///etc/passwd")

    def test_javascript_scheme_rejected(self):
        with pytest.raises(URLValidationError, match="scheme"):
            validate_url("javascript:alert(1)")

    def test_no_host(self):
        with pytest.raises(URLValidationError):
            validate_url("https://")

    def test_url_too_long(self):
        with pytest.raises(URLValidationError, match="length"):
            validate_url("https://example.com/" + "a" * 3000)

    def test_credentials_rejected(self):
        with pytest.raises(URLValidationError, match="credentials"):
            validate_url("https://user:pass@example.com/video")


class TestSSRFProtection:
    """Ensure SSRF attacks via private IPs are blocked."""

    def test_localhost_blocked(self):
        with pytest.raises(URLValidationError):
            validate_url("https://localhost/admin")

    def test_127_0_0_1_blocked(self):
        with pytest.raises(URLValidationError):
            validate_url("https://127.0.0.1/secret")

    def test_private_192_168_blocked(self):
        with pytest.raises(URLValidationError):
            validate_url("https://192.168.1.1/file")

    def test_private_10_blocked(self):
        with pytest.raises(URLValidationError):
            validate_url("https://10.0.0.1/internal")

    def test_private_172_blocked(self):
        with pytest.raises(URLValidationError):
            validate_url("https://172.16.0.1/api")

    def test_aws_metadata_blocked(self):
        with pytest.raises(URLValidationError):
            validate_url("https://169.254.169.254/latest/meta-data/")
