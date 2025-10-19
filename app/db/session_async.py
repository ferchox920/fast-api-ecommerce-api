# app/db/session_async.py
"""Async SQLAlchemy session utilities."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

T = TypeVar("T")


async_engine: AsyncEngine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_async_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an AsyncSession."""
    async with AsyncSessionLocal() as session:
        yield session


async def commit(session: AsyncSession) -> None:
    """Commit and rollback on failure."""
    try:
        await session.commit()
    except Exception:
        await rollback(session)
        raise


async def rollback(session: AsyncSession) -> None:
    """Rollback active transaction if needed."""
    if session.in_transaction():
        await session.rollback()


async def run_in_transaction(
    operation: Callable[[AsyncSession], Awaitable[T]],
) -> T:
    """Execute an async operation within a managed transaction."""
    async with AsyncSessionLocal() as session:
        try:
            result = await operation(session)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise
