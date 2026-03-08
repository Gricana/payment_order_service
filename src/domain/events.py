from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from domain.value_objects.enums import OrderPaymentStatus
from domain.value_objects.identifiers import OrderId, PaymentId
from domain.value_objects.money import Money


class DomainEvent(Protocol):
    """Marker protocol for domain events."""

    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class PaymentDepositCreated:
    occurred_at: datetime
    order_id: OrderId
    payment_id: PaymentId
    amount: Money

    @classmethod
    def now(cls, order_id: OrderId, payment_id: PaymentId, amount: Money) -> PaymentDepositCreated:
        return cls(datetime.now(UTC), order_id, payment_id, amount)


@dataclass(frozen=True, slots=True)
class PaymentRefundProcessed:
    occurred_at: datetime
    order_id: OrderId
    payment_id: PaymentId
    amount: Money

    @classmethod
    def now(cls, order_id: OrderId, payment_id: PaymentId, amount: Money) -> PaymentRefundProcessed:
        return cls(datetime.now(UTC), order_id, payment_id, amount)


@dataclass(frozen=True, slots=True)
class OrderPaymentStatusChanged:
    occurred_at: datetime
    order_id: OrderId
    old_status: OrderPaymentStatus
    new_status: OrderPaymentStatus

    @classmethod
    def now(
        cls,
        order_id: OrderId,
        old_status: OrderPaymentStatus,
        new_status: OrderPaymentStatus,
    ) -> OrderPaymentStatusChanged:
        return cls(datetime.now(UTC), order_id, old_status, new_status)
