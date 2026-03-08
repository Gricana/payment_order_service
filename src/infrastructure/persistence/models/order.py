from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain.value_objects.enums import OrderPaymentStatus
from infrastructure.persistence.db import Base

if TYPE_CHECKING:
    from infrastructure.persistence.models.payment import PaymentORM


class OrderORM(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payment_status: Mapped[OrderPaymentStatus] = mapped_column(
        Enum(OrderPaymentStatus, name="order_payment_status"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    payments: Mapped[list[PaymentORM]] = relationship(
        "PaymentORM",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
