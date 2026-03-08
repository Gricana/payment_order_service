from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from domain.exceptions import InsufficientFundsError
from domain.value_objects.enums import BankPaymentStatus, PaymentStatus, PaymentType
from domain.value_objects.identifiers import OrderId, PaymentId
from domain.value_objects.money import Money


@dataclass(slots=True)
class AcquiringPaymentDetails:
    """Bank acquiring specific details."""

    bank_payment_id: str
    bank_status: BankPaymentStatus
    bank_paid_at: datetime | None = None
    last_synced_at: datetime | None = None


@dataclass(slots=True)
class Payment:
    """Payment entity belonging to an Order aggregate."""

    id: PaymentId
    order_id: OrderId
    payment_type: PaymentType
    amount: Money
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    acquiring_details: AcquiringPaymentDetails | None = None
    refunded_amount: Money | None = None
    client_reference_id: str | None = None

    def __post_init__(self) -> None:
        if self.refunded_amount is None:
            self.refunded_amount = Money.zero(self.amount.currency)

    @property
    def remaining_refundable_amount(self) -> Money:
        return self.amount - (self.refunded_amount or Money.zero(self.amount.currency))

    def mark_completed(self) -> None:
        self.status = PaymentStatus.COMPLETED

    def mark_failed(self) -> None:
        self.status = PaymentStatus.FAILED

    def refund(self, amount: Money) -> None:
        if amount.currency != self.amount.currency:
            raise InsufficientFundsError("Refund currency must match payment currency.")
        if amount.is_zero():
            return
        if amount.amount > self.remaining_refundable_amount.amount:
            raise InsufficientFundsError("Cannot refund more than remaining refundable amount.")
        self.refunded_amount = (self.refunded_amount or Money.zero(self.amount.currency)) + amount
        if self.refunded_amount.amount == self.amount.amount:
            self.status = PaymentStatus.REFUNDED
