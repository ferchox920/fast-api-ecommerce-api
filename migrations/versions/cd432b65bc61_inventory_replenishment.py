"""inventory_replenishment

Revision ID: cd432b65bc61
Revises: cdf21a359210
Create Date: 2025-09-13 18:51:53.182740
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "cd432b65bc61"
down_revision: Union[str, Sequence[str], None] = "cdf21a359210"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # IMPORTANTE:
    # - No dropeamos 'inventory_movements' aunque el autogenerate lo haya detectado como "removed".
    #   Si realmente querés borrarla, hacelo en otra migración explícita.
    #
    # - Agregamos columnas NOT NULL con server_default para no romper filas existentes.
    #   Luego quitamos el default, así el ORM gobierna los valores nuevos.

    op.add_column(
        "product_variants",
        sa.Column("allow_backorder", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "product_variants",
        sa.Column("allow_preorder", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "product_variants",
        sa.Column("release_at", sa.DateTime(timezone=True), nullable=True),
    )

    # (Opcional) Backfill custom si quisieras setear true en algunos casos:
    # op.execute("UPDATE product_variants SET allow_backorder = true WHERE ...")
    # op.execute("UPDATE product_variants SET allow_preorder  = true WHERE ...")

    # Quitamos el server_default para dejar la restricción NOT NULL sin default
    op.alter_column("product_variants", "allow_backorder", server_default=None)
    op.alter_column("product_variants", "allow_preorder", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    # Revertimos únicamente las columnas agregadas.
    # No recreamos 'inventory_movements' porque no la borramos en upgrade.
    op.drop_column("product_variants", "release_at")
    op.drop_column("product_variants", "allow_preorder")
    op.drop_column("product_variants", "allow_backorder")
