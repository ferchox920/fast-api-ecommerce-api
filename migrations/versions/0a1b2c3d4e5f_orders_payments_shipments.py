"""orders payments shipments enhancements

Revision ID: 0a1b2c3d4e5f
Revises: f1234567890ab
Create Date: 2025-10-17 02:20:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "f1234567890ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # ENUMs idempotentes (evitan "type already exists")
    payment_status_enum = postgresql.ENUM(
        "pending", "authorized", "approved", "rejected", "cancelled", "refunded",
        name="paymentstatus",
        create_type=False,
    )
    payment_status_enum.create(bind, checkfirst=True)

    shipping_status_enum = postgresql.ENUM(
        "pending", "preparing", "shipped", "delivered", "returned",
        name="shippingstatus",
        create_type=False,
    )
    shipping_status_enum.create(bind, checkfirst=True)

    provider_enum = postgresql.ENUM(
        "mercado_pago",
        name="paymentprovider",
        create_type=False,
    )
    provider_enum.create(bind, checkfirst=True)

    # Columns en orders
    op.add_column(
        "orders",
        sa.Column(
            "payment_status",
            payment_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::paymentstatus"),
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "shipping_status",
            shipping_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::shippingstatus"),
        ),
    )
    op.add_column("orders", sa.Column("shipping_address", sa.JSON(), nullable=True))
    op.add_column("orders", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_payment_status", "orders", ["payment_status"])
    op.create_index("ix_orders_shipping_status", "orders", ["shipping_status"])

    # payments
    op.create_table(
        "payments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "provider",
            provider_enum,
            nullable=False,
            server_default=sa.text("'mercado_pago'::paymentprovider"),
        ),
        sa.Column("provider_payment_id", sa.String(length=140), nullable=True),
        sa.Column(
            "status",
            payment_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::paymentstatus"),
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default=sa.text("'ARS'")),
        sa.Column("init_point", sa.String(length=500), nullable=True),
        sa.Column("sandbox_init_point", sa.String(length=500), nullable=True),
        sa.Column("raw_preference", sa.JSON(), nullable=True),
        sa.Column("last_webhook", sa.JSON(), nullable=True),
        sa.Column("status_detail", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_payments_order_id", "payments", ["order_id"], unique=False)
    op.create_index("ix_payments_provider_payment_id", "payments", ["provider_payment_id"], unique=False)

    # shipments
    op.create_table(
        "shipments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            shipping_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::shippingstatus"),
        ),
        sa.Column("carrier", sa.String(length=120), nullable=True),
        sa.Column("tracking_number", sa.String(length=140), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("address", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_shipments_order_id", "shipments", ["order_id"], unique=False)
    op.create_index("ix_shipments_tracking_number", "shipments", ["tracking_number"], unique=False)

    # limpiar defaults opcionalmente
    op.alter_column("orders", "payment_status", server_default=None)
    op.alter_column("orders", "shipping_status", server_default=None)
    op.alter_column("payments", "currency", server_default=None)
    op.alter_column("payments", "status", server_default=None)
    op.alter_column("shipments", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_shipments_tracking_number", table_name="shipments")
    op.drop_index("ix_shipments_order_id", table_name="shipments")
    op.drop_table("shipments")

    op.drop_index("ix_payments_provider_payment_id", table_name="payments")
    op.drop_index("ix_payments_order_id", table_name="payments")
    op.drop_table("payments")

    op.drop_index("ix_orders_shipping_status", table_name="orders")
    op.drop_index("ix_orders_payment_status", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")

    op.drop_column("orders", "cancelled_at")
    op.drop_column("orders", "fulfilled_at")
    op.drop_column("orders", "paid_at")
    op.drop_column("orders", "notes")
    op.drop_column("orders", "shipping_address")
    op.drop_column("orders", "shipping_status")
    op.drop_column("orders", "payment_status")

    bind = op.get_bind()
    provider_enum = postgresql.ENUM("mercado_pago", name="paymentprovider", create_type=False)
    provider_enum.drop(bind, checkfirst=True)

    payment_status_enum = postgresql.ENUM(
        "pending", "authorized", "approved", "rejected", "cancelled", "refunded",
        name="paymentstatus",
        create_type=False,
    )
    payment_status_enum.drop(bind, checkfirst=True)

    shipping_status_enum = postgresql.ENUM(
        "pending", "preparing", "shipped", "delivered", "returned",
        name="shippingstatus",
        create_type=False,
    )
    shipping_status_enum.drop(bind, checkfirst=True)
