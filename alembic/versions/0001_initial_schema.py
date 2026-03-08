from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from domain.value_objects.enums import (
    BankPaymentStatus,
    OrderPaymentStatus,
    PaymentStatus,
    PaymentType,
)

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    order_payment_status_enum = postgresql.ENUM(
        OrderPaymentStatus,
        name="order_payment_status",
        create_type=False,
    )
    payment_type_enum = postgresql.ENUM(
        PaymentType,
        name="payment_type",
        create_type=False,
    )
    payment_status_enum = postgresql.ENUM(
        PaymentStatus,
        name="payment_status",
        create_type=False,
    )
    bank_payment_status_enum = postgresql.ENUM(
        BankPaymentStatus,
        name="bank_payment_status",
        create_type=False,
    )

    order_payment_status_enum.create(op.get_bind(), checkfirst=True)
    payment_type_enum.create(op.get_bind(), checkfirst=True)
    payment_status_enum.create(op.get_bind(), checkfirst=True)
    bank_payment_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("payment_status", order_payment_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("payment_type", payment_type_enum, nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", payment_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refunded_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("client_reference_id", sa.String(length=128), nullable=True),
    )
    op.create_index("ix_payments_order_id", "payments", ["order_id"])

    op.create_table(
        "acquiring_details",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "payment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payments.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("bank_payment_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("bank_status", bank_payment_status_enum, nullable=False),
        sa.Column("bank_paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_acquiring_details_bank_payment_id",
        "acquiring_details",
        ["bank_payment_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_acquiring_details_bank_payment_id", table_name="acquiring_details")
    op.drop_table("acquiring_details")

    op.drop_index("ix_payments_order_id", table_name="payments")
    op.drop_table("payments")

    op.drop_table("orders")

    op.execute("DROP TYPE IF EXISTS bank_payment_status")
    op.execute("DROP TYPE IF EXISTS payment_status")
    op.execute("DROP TYPE IF EXISTS payment_type")
    op.execute("DROP TYPE IF EXISTS order_payment_status")
