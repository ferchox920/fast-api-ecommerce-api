# app/db/operations.py
"""Async SQLAlchemy session helpers used across the codebase."""

from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


def _coerce_iter(items: Iterable[Any] | None) -> list[Any] | None:
    if not items:
        return None
    return list(items)


async def commit_async(session: AsyncSession) -> None:
    """Commit the current transaction."""
    await session.commit()


async def rollback_async(session: AsyncSession) -> None:
    """Rollback the current transaction if active."""
    await session.rollback()


async def flush_async(session: AsyncSession, *objects: Any) -> None:
    """Flush pending objects to the database."""
    await session.flush(_coerce_iter(objects))


async def refresh_async(
    session: AsyncSession,
    *instances: Any,
    attribute_names: list[str] | None = None,
) -> None:
    """Refresh ORM instances from the database."""
    for instance in instances:
        if attribute_names:
            await session.refresh(instance, attribute_names=attribute_names)
        else:
            await session.refresh(instance)
