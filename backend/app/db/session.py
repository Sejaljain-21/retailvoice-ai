"""Async engine / session factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

_connect_args: dict = {}
if settings.is_sqlite:
    # Needed because the voice WebSocket touches the DB from several tasks.
    _connect_args = {"check_same_thread": False}

_engine_kwargs: dict = {"pool_pre_ping": True}
if settings.APP_ENV == "test":
    # Each test gets its own event loop; a pooled connection created in a
    # previous loop would blow up when reused, so don't pool at all.
    _engine_kwargs = {"poolclass": NullPool}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    future=True,
    connect_args=_connect_args,
    **_engine_kwargs,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """For background tasks / WebSocket handlers that are not request-scoped."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
