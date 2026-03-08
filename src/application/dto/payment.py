from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.value_objects.enums import PaymentStatus, PaymentType
from domain.value_objects.identifiers import OrderId, PaymentId
from domain.value_objects.money import Money


@dataclass(frozen=True, slots=True)
class PaymentDTO:
    """Application-level DTO representing payment for use cases and presentation layer."""

    id: str
    order_id: str
    payment_type: PaymentType
    amount: str
    currency: str
    status: PaymentStatus
    created_at: datetime
    refunded_amount: str

    @classmethod
    def from_domain(
        cls,
        payment_id: PaymentId,
        order_id: OrderId,
        money: Money,
        status: PaymentStatus,
        created_at: datetime,
        payment_type: PaymentType,
        refunded_amount: Money,
    ) -> PaymentDTO:
        return cls(
            id=str(payment_id.value),
            order_id=str(order_id.value),
            payment_type=payment_type,
            amount=str(money.amount),
            currency=money.currency,
            status=status,
            created_at=created_at,
            refunded_amount=str(refunded_amount.amount),
        )
