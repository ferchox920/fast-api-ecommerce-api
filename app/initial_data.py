# app/initial_data.py
import logging
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from app.core.config import settings
from app.models.user import User
from app.services import user_service
from app.schemas.user import UserCreate
from app.db.session_async import AsyncSessionLocal

logger = logging.getLogger(__name__)

@asynccontextmanager
async def _advisory_lock(session: AsyncSession):
    """
    Evita carreras en entornos multi-worker (PostgreSQL).
    No hace nada en SQLite/otros dialectos.
    """
    dialect = session.bind.dialect.name if session.bind else "unknown"
    lock_key = 987654321  # cualquier entero estable
    got_lock = False
    try:
        if dialect == "postgresql":
            # pg_try_advisory_lock devuelve true/false
            res = await session.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": lock_key})
            got_lock = bool(res.scalar())
            if not got_lock:
                logger.info("Otro worker ya está inicializando admin; salto esta instancia.")
                yield False
                return
        yield True
    finally:
        if got_lock:
            await session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})

async def create_initial_admin_user():
    """
    Crea el admin inicial si:
      - Hay credenciales en env (.env) y
      - No existe ningún superusuario.
    Es idempotente, con protección a carreras (en Postgres).
    """
    if not settings.INITIAL_ADMIN_EMAIL or not settings.INITIAL_ADMIN_PASSWORD:
        logger.info("Skipping admin init: faltan INITIAL_ADMIN_EMAIL o INITIAL_ADMIN_PASSWORD.")
        return

    logger.info("Inicialización de admin: iniciando verificación…",
                extra={"email": str(settings.INITIAL_ADMIN_EMAIL)})

    async with AsyncSessionLocal() as session:
        async with _advisory_lock(session) as proceed:
            if proceed is False:
                return

            # 1) Ya existe algún superadmin?
            stmt = select(func.count()).select_from(User).where(User.is_superuser.is_(True))
            result = await session.execute(stmt)
            if (result.scalar() or 0) > 0:
                logger.info("Ya existe al menos un superusuario; no se crea otro.")
                return

            # 2) Existe el usuario con ese email?
            existing = await user_service.get_by_email(session, str(settings.INITIAL_ADMIN_EMAIL))
            if existing:
                if not existing.is_superuser:
                    # Promoción explícita (idempotente)
                    existing.is_superuser = True
                    existing.email_verified = True
                    await session.commit()
                    logger.warning(
                        "Usuario inicial ya existía sin permisos; promovido a superadmin.",
                        extra={"user_id": str(existing.id), "email": existing.email},
                    )
                else:
                    logger.info("El usuario inicial ya era superadmin; nada que hacer.")
                return

            # 3) Crear usuario y marcarlo admin
            user_in = UserCreate(
                email=str(settings.INITIAL_ADMIN_EMAIL),
                password=settings.INITIAL_ADMIN_PASSWORD,
                full_name="Initial Admin",
            )

            # create_user debe hashear password y persistir
            user = await user_service.create_user(session, user_in)
            user.is_superuser = True
            user.email_verified = True
            session.add(user)
            await session.commit()
            await session.refresh(user)

            logger.info("Superadmin creado correctamente.",
                        extra={"user_id": str(user.id), "email": user.email})
