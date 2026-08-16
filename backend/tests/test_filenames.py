"""Tests for filename sanitization utilities."""

from __future__ import annotations

import pytest

from app.utils.filenames import safe_filename, validate_output_path
from pathlib import Path
import tempfile
import os


class TestSafeFilename:
    def test_basic(self):
        result = safe_filename("My Video Title", "mp4")
        assert result == "My_Video_Title.mp4"

    def test_special_chars_replaced(self):
        result = safe_filename('Video: "Hello" / World?', "mp4")
        assert "/" not in result
        assert '"' not in result
        assert "?" not in result

    def test_path_separator_removed(self):
        result = safe_filename("../../etc/passwd", "txt")
        assert ".." not in result
        assert "/" not in result

    def test_empty_title(self):
        result = safe_filename("", "mp4")
        assert result == "download.mp4"

    def test_very_long_title_truncated(self):
        result = safe_filename("a" * 500, "mp4")
        assert len(result) <= 200 + 4  # 4 = ".mp4"

    def test_dangerous_extension_blocked(self):
        result = safe_filename("setup", "exe")
        assert result.endswith(".bin")

    def test_mp3_extension_preserved(self):
        result = safe_filename("audio track", "mp3")
        assert result.endswith(".mp3")


class TestValidateOutputPath:
    def test_valid_path(self):
        with tempfile.TemporaryDirectory() as base:
            child = Path(base) / "subdir" / "file.mp4"
            child.parent.mkdir(parents=True, exist_ok=True)
            child.touch()
            result = validate_output_path(child, base)
            assert result.is_relative_to(Path(base).resolve())

    def test_path_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as base:
            evil_path = Path(base) / ".." / "evil.txt"
            with pytest.raises(ValueError):
                validate_output_path(evil_path, base)
