from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain.value_objects.enums import PaymentStatus, PaymentType
from infrastructure.persistence.db import Base

if TYPE_CHECKING:
    from infrastructure.persistence.models.acquiring_details import AcquiringDetailsORM
    from infrastructure.persistence.models.order import OrderORM


class PaymentORM(Base):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, nullable=False)
    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, name="payment_type"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    refunded_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    client_reference_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )

    order: Mapped[OrderORM] = relationship(
        "OrderORM",
        back_populates="payments",
        lazy="joined",
    )
    acquiring_details: Mapped[AcquiringDetailsORM | None] = relationship(
        "AcquiringDetailsORM",
        back_populates="payment",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
    )
