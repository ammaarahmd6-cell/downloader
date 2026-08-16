"""Async SQLAlchemy session factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()

# Create engine — URL supports both sqlite+aiosqlite and postgresql+asyncpg
connect_args = {}
if "sqlite" in _settings.DATABASE_URL:
    connect_args["check_same_thread"] = False
elif "asyncpg" in _settings.DATABASE_URL or "postgresql" in _settings.DATABASE_URL:
    # Disable prepared statement caching for compatibility with PgBouncer / Supabase connection pooler
    connect_args["statement_cache_size"] = 0
    connect_args["prepared_statement_cache_size"] = 0

engine = create_async_engine(
    _settings.DATABASE_URL,
    echo=_settings.DEBUG,
    pool_pre_ping=True,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables (used in development/testing)."""
    from app.db.base import Base  # noqa: F401 — ensures models are imported
    import app.models.job  # noqa: F401
    import app.models.download_history  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
