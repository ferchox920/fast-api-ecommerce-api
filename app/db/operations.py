# app/db/operations.py
"""Common sync/async session helpers."""

from collections.abc import Callable, Iterable
from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

T = TypeVar("T")


def _coerce_iter(items: Iterable[Any] | None) -> list[Any] | None:
    if not items:
        return None
    return list(items)


def commit_sync(session: Session) -> None:
    session.commit()


async def commit_async(session: AsyncSession) -> None:
    await session.commit()


def rollback_sync(session: Session) -> None:
    session.rollback()


async def rollback_async(session: AsyncSession) -> None:
    await session.rollback()


def flush_sync(session: Session, *objects: Any) -> None:
    session.flush(_coerce_iter(objects))


async def flush_async(session: AsyncSession, *objects: Any) -> None:
    await session.flush(_coerce_iter(objects))


def refresh_sync(session: Session, *instances: Any, attribute_names: list[str] | None = None) -> None:
    for instance in instances:
        if attribute_names:
            session.refresh(instance, attribute_names=attribute_names)
        else:
            session.refresh(instance)


async def refresh_async(session: AsyncSession, *instances: Any, attribute_names: list[str] | None = None) -> None:
    for instance in instances:
        if attribute_names:
            await session.refresh(instance, attribute_names=attribute_names)
        else:
            await session.refresh(instance)


async def run_sync(session: AsyncSession, func: Callable[[Session], T], *args: Any, **kwargs: Any) -> T:
    """Execute a synchronous callable against the session within run_sync."""
    def _runner(sync_session: Session) -> T:
        return func(sync_session, *args, **kwargs)

    return await session.run_sync(_runner)
