from __future__ import annotations

from dataclasses import dataclass, field

from domain import events
from domain.entities.payment import Payment
from domain.exceptions import InsufficientFundsError, OrderAlreadyPaidError, PaymentNotFoundError
from domain.value_objects.enums import OrderPaymentStatus
from domain.value_objects.identifiers import OrderId, PaymentId
from domain.value_objects.money import Money


@dataclass(slots=True)
class Order:
    """Aggregate root representing an order and its payments."""

    id: OrderId
    total_amount: Money
    payment_status: OrderPaymentStatus
    payments: list[Payment] = field(default_factory=list)
    _pending_events: list[events.DomainEvent] = field(default_factory=list, init=False, repr=False)

    @property
    def currency(self) -> str:
        return self.total_amount.currency

    @property
    def deposits_total(self) -> Money:
        total = Money.zero(self.currency)
        for payment in self.payments:
            total = total + payment.amount
        return total

    @property
    def refunds_total(self) -> Money:
        total = Money.zero(self.currency)
        for payment in self.payments:
            if payment.refunded_amount:
                total = total + payment.refunded_amount
        return total

    @property
    def paid_total(self) -> Money:
        return self.deposits_total - self.refunds_total

    def add_payment(self, payment: Payment) -> None:
        """Add a payment ensuring order invariants."""
        if self.payment_status == OrderPaymentStatus.PAID:
            raise OrderAlreadyPaidError("Cannot add payment to fully paid order.")

        new_deposits_total = self.deposits_total + payment.amount
        if new_deposits_total.amount > self.total_amount.amount:
            raise InsufficientFundsError("Total deposits cannot exceed order total amount.")

        self.payments.append(payment)
        self._pending_events.append(
            events.PaymentDepositCreated.now(self.id, payment.id, payment.amount)
        )
        self._recalculate_status()

    def apply_refund(self, payment_id: PaymentId, amount: Money) -> None:
        payment = self._find_payment(payment_id)
        before_paid_total = self.paid_total

        payment.refund(amount)

        if self.paid_total.amount < Money.zero(self.currency).amount:
            raise InsufficientFundsError("Refund would make total paid amount negative.")

        self._pending_events.append(events.PaymentRefundProcessed.now(self.id, payment.id, amount))
        self._recalculate_status(before_paid_total=before_paid_total)

    def _find_payment(self, payment_id: PaymentId) -> Payment:
        for payment in self.payments:
            if payment.id == payment_id:
                return payment
        raise PaymentNotFoundError(f"Payment {payment_id} not found in order {self.id}.")

    def _recalculate_status(self, *, before_paid_total: Money | None = None) -> None:
        old_status = self.payment_status
        if self.paid_total.amount == 0:
            self.payment_status = OrderPaymentStatus.UNPAID
        elif self.paid_total.amount < self.total_amount.amount:
            self.payment_status = OrderPaymentStatus.PARTIALLY_PAID
        else:
            self.payment_status = OrderPaymentStatus.PAID

        if before_paid_total is not None and old_status != self.payment_status:
            self._pending_events.append(
                events.OrderPaymentStatusChanged.now(
                    self.id,
                    old_status=old_status,
                    new_status=self.payment_status,
                )
            )

    def pull_events(self) -> list[events.DomainEvent]:
        """Return and clear pending domain events for publishing."""
        events_to_publish = list(self._pending_events)
        self._pending_events.clear()
        return events_to_publish
