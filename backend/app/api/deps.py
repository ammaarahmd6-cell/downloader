"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from app.db.session import get_db_session  # re-export for convenience

__all__ = ["get_db_session"]
