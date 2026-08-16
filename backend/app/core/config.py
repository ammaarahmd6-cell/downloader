"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the media downloader application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_parse_none_str="null",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_ENV: Literal["development", "testing", "production"] = "development"
    APP_NAME: str = "MediaDL"
    APP_VERSION: str = "1.0.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    # Supports: postgresql+psycopg://... or sqlite+aiosqlite:///./db.sqlite3
    DATABASE_URL: str = "sqlite+aiosqlite:///./mediadl.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and not v.startswith("postgresql+"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql+psycopg://"):
            return v.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
        return v

    # ── InsForge ─────────────────────────────────────────────────────────────
    INSFORGE_URL: str = ""
    INSFORGE_API_KEY: str = ""



    # ── Storage ──────────────────────────────────────────────────────────────
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    STORAGE_DIR: Path = Field(default_factory=lambda: Path("./storage").resolve())
    TEMP_DIR: Path = Field(default_factory=lambda: Path("./storage/temp").resolve())
    COMPLETED_DIR: Path = Field(default_factory=lambda: Path("./storage/completed").resolve())

    # ── Limits ───────────────────────────────────────────────────────────────
    MAX_CONCURRENT_JOBS: int = 3
    MAX_JOB_DURATION: int = 3600          # seconds
    MAX_DOWNLOAD_SIZE_MB: int = 2048      # 2 GB
    MAX_STORAGE_SIZE_GB: int = 10
    FILE_RETENTION_SECONDS: int = 3600   # 1 hour

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_INFO: str = "10/minute"
    RATE_LIMIT_DOWNLOAD: str = "5/minute"

    # ── CORS ─────────────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"
    # Comma-separated origins: "http://localhost:3000,http://127.0.0.1:3000"
    ALLOWED_ORIGINS_STR: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS_STR.split(",") if o.strip()]

    # ── FFmpeg ───────────────────────────────────────────────────────────────
    FFMPEG_PATH: str = "ffmpeg"
    FFPROBE_PATH: str = "ffprobe"

    # ── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"

    # ── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "console"

    @field_validator("STORAGE_DIR", "TEMP_DIR", "COMPLETED_DIR", mode="before")
    @classmethod
    def resolve_path(cls, v: str | Path) -> Path:
        return Path(v).resolve()


    def ensure_dirs(self) -> None:
        """Create storage directories if they don't exist."""
        for d in (self.STORAGE_DIR, self.TEMP_DIR, self.COMPLETED_DIR):
            d.mkdir(parents=True, exist_ok=True)

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def max_download_size_bytes(self) -> int:
        return self.MAX_DOWNLOAD_SIZE_MB * 1024 * 1024


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the singleton Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
