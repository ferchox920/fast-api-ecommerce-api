from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import flush_async, refresh_async
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.user_service import create_user, get_by_email


async def list_users(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[User]:
    stmt = (
        select(User)
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


def _as_uuid(user_id: str) -> uuid.UUID:
    return uuid.UUID(str(user_id))


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    return await db.get(User, _as_uuid(user_id))


async def create_user_as_admin(
    db: AsyncSession,
    payload: UserCreate,
    make_superuser: bool = False,
) -> User:
    if await get_by_email(db, payload.email):
        raise ValueError("Email already registered")
    user = await create_user(db, payload)
    if make_superuser:
        user.is_superuser = True
        db.add(user)
        await flush_async(db, user)
        await refresh_async(db, user)
    return user


async def set_admin_role(db: AsyncSession, user_id: str, make_admin: bool) -> User | None:
    user = await get_user_by_id(db, user_id)
    if not user:
        return None
    user.is_superuser = bool(make_admin)
    db.add(user)
    await flush_async(db, user)
    await refresh_async(db, user)
    return user


async def set_active(db: AsyncSession, user_id: str, active: bool) -> User | None:
    user = await get_user_by_id(db, user_id)
    if not user:
        return None
    user.is_active = bool(active)
    db.add(user)
    await flush_async(db, user)
    await refresh_async(db, user)
    return user
