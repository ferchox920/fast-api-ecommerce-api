# migrations/env.py
from __future__ import annotations

from logging.config import fileConfig
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# --- Añadir la raíz del proyecto al sys.path (…/fast_api) ---
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# --- Imports de tu app ---
from app.core.config import settings
from app.db.session import Base  # tu declarative Base

# IMPORTANTE: importar todos los modelos para poblar Base.metadata
# Si no tenés __init__.py en app/models, importalos explícitamente:
from app.models import product   # noqa: F401  # Category, Brand, Product, ProductVariant, ProductImage
from app.models import supplier  # noqa: F401  # Supplier
from app.models import purchase  # noqa: F401  # PurchaseOrder, PurchaseOrderLine
from app.models import order     # noqa: F401  # Order, OrderLine
from app.models import cart      # noqa: F401  # Cart, CartItem
from app.models import product_question  # noqa: F401  # ProductQuestion, ProductAnswer
from app.models import notification  # noqa: F401  # Notification
from app.models import engagement  # noqa: F401  # ProductEngagementDaily, ProductRanking, ExposureSlot
from app.models import promotion   # noqa: F401  # Promotion
from app.models import loyalty     # noqa: F401  # Loyalty
# importa user, inventory, etc. si existen y usan Base
# from app.models import user     # noqa: F401
# from app.models import inventory  # noqa: F401

# --- Config de Alembic ---
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Elegimos la URL para Alembic (SIEMPRE sync)
# 1) Usa ALEMBIC_DATABASE_URL si existe
# 2) Si solo hay DATABASE_URL y es async, la convertimos a psycopg (sync)
alembic_url = getattr(settings, "ALEMBIC_DATABASE_URL", None) or settings.DATABASE_URL
if alembic_url.startswith("postgresql+asyncpg"):
    alembic_url = alembic_url.replace("+asyncpg", "+psycopg")

# Inyectar la URL definitiva a Alembic
config.set_main_option("sqlalchemy.url", alembic_url)

# Metadata objetivo para autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Ejecuta migraciones en modo offline (sin Engine)."""
    context.configure(
        url=alembic_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta migraciones en modo online (con Engine/Connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
