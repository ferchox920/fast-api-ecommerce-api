"""Seed script for populating development users without raw SQL."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import sys
from pathlib import Path

# Ensure project root is on PYTHONPATH when running as a script.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import settings
from app.db.session_async import AsyncSessionLocal
from app.services import user_service
from app.schemas.user import UserCreate


@dataclass(frozen=True, slots=True)
class DevUser:
    email: str
    full_name: str
    password: str
    is_superuser: bool = False
    email_verified: bool = True


DEV_USERS: tuple[DevUser, ...] = (
    DevUser(
        email="admin.dev@example.com",
        full_name="Dev Admin",
        password="AdminDev123!",
        is_superuser=True,
    ),
    DevUser(
        email="manager.dev@example.com",
        full_name="Dev Manager",
        password="ManagerDev123!",
        email_verified=True,
    ),
    DevUser(
        email="user1.dev@example.com",
        full_name="Dev Customer One",
        password="UserDev123!",
    ),
    DevUser(
        email="user2.dev@example.com",
        full_name="Dev Customer Two",
        password="UserDev123!",
    ),
)


async def seed_dev_users() -> None:
    """Insert or update development users in the configured database."""
    logger = logging.getLogger("seed_dev_users")
    logger.info("Seeding development users into %s", settings.ASYNC_DATABASE_URL)

    created = 0
    updated = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        for dev_user in DEV_USERS:
            existing = await user_service.get_by_email(session, dev_user.email)

            if existing:
                changed = False
                if dev_user.is_superuser and not existing.is_superuser:
                    existing.is_superuser = True
                    changed = True
                if dev_user.email_verified and not existing.email_verified:
                    existing.email_verified = True
                    changed = True
                if changed:
                    session.add(existing)
                    updated += 1
                    logger.debug("Updated existing user %s", dev_user.email)
                else:
                    skipped += 1
                    logger.debug("Skipped user %s (already up to date)", dev_user.email)
                continue

            user_in = UserCreate(
                email=dev_user.email,
                full_name=dev_user.full_name,
                password=dev_user.password,
            )
            user = await user_service.create_user(session, user_in)
            if dev_user.is_superuser:
                user.is_superuser = True
            if dev_user.email_verified:
                user.email_verified = True
            session.add(user)
            created += 1
            logger.debug("Created user %s", dev_user.email)

        await session.commit()

    logger.info(
        "Seed completed: %s created, %s updated, %s skipped",
        created,
        updated,
        skipped,
    )


async def main() -> None:
    await seed_dev_users()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
