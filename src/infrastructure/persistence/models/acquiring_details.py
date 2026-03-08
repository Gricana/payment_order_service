from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain.value_objects.enums import BankPaymentStatus
from infrastructure.persistence.db import Base

if TYPE_CHECKING:
    from infrastructure.persistence.models.payment import PaymentORM


class AcquiringDetailsORM(Base):
    __tablename__ = "acquiring_details"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, nullable=False)
    payment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    bank_payment_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    bank_status: Mapped[BankPaymentStatus] = mapped_column(
        Enum(BankPaymentStatus, name="bank_payment_status"), nullable=False
    )
    bank_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    payment: Mapped[PaymentORM] = relationship(
        "PaymentORM",
        back_populates="acquiring_details",
        lazy="joined",
    )
