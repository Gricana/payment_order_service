from __future__ import annotations

from decimal import Decimal

import pytest

from domain.entities.order import Order
from domain.entities.payment import Payment
from domain.exceptions import InsufficientFundsError, OrderAlreadyPaidError
from domain.value_objects.enums import OrderPaymentStatus, PaymentType
from domain.value_objects.identifiers import OrderId, PaymentId
from domain.value_objects.money import Money


def _make_order(total: str = "100.00") -> Order:
    return Order(
        id=OrderId.new(),
        total_amount=Money(Decimal(total), "USD"),
        payment_status=OrderPaymentStatus.UNPAID,
    )


def _make_payment(amount: str = "10.00", order_id: OrderId | None = None) -> Payment:
    oid = order_id or OrderId.new()
    return Payment(
        id=PaymentId.new(),
        order_id=oid,
        payment_type=PaymentType.CASH,
        amount=Money(Decimal(amount), "USD"),
    )


def test_add_payment_updates_status_to_partially_paid() -> None:
    order = _make_order("100.00")
    payment = _make_payment("10.00", order.id)

    order.add_payment(payment)

    assert order.payment_status == OrderPaymentStatus.PARTIALLY_PAID


def test_add_payment_updates_status_to_paid_when_full_amount() -> None:
    order = _make_order("50.00")
    payment = _make_payment("50.00", order.id)

    order.add_payment(payment)

    assert order.payment_status == OrderPaymentStatus.PAID


def test_add_payment_raises_when_exceeds_order_amount() -> None:
    order = _make_order("100.00")
    p1 = _make_payment("60.00", order.id)
    p2 = _make_payment("50.00", order.id)

    order.add_payment(p1)

    with pytest.raises(InsufficientFundsError):
        order.add_payment(p2)


def test_add_payment_raises_when_order_already_paid() -> None:
    order = _make_order("50.00")
    p1 = _make_payment("50.00", order.id)
    p2 = _make_payment("10.00", order.id)

    order.add_payment(p1)

    with pytest.raises(OrderAlreadyPaidError):
        order.add_payment(p2)


def test_refund_updates_status_back_to_partially_paid() -> None:
    order = _make_order("100.00")
    p1 = _make_payment("100.00", order.id)
    order.add_payment(p1)
    assert order.payment_status == OrderPaymentStatus.PAID

    refund_amount = Money("40.00", "USD")
    order.apply_refund(p1.id, refund_amount)

    assert order.payment_status == OrderPaymentStatus.PARTIALLY_PAID


def test_refund_raises_when_amount_exceeds_deposited() -> None:
    order = _make_order("100.00")
    p1 = _make_payment("50.00", order.id)
    order.add_payment(p1)

    refund_amount = Money("60.00", "USD")

    with pytest.raises(InsufficientFundsError):
        order.apply_refund(p1.id, refund_amount)
