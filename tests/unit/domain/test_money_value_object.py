from __future__ import annotations

from decimal import Decimal

import pytest

from domain.exceptions import CurrencyMismatchError, NegativeAmountError
from domain.value_objects.money import Money


def test_money_addition_is_precise() -> None:
    a = Money("10.00", "USD")
    b = Money("0.01", "USD")

    result = a + b

    assert isinstance(result.amount, Decimal)
    assert result.amount == Decimal("10.01")
    assert result.currency == "USD"


def test_money_raises_on_negative_amount() -> None:
    with pytest.raises(NegativeAmountError):
        Money("-0.01", "USD")


def test_money_equality_by_value() -> None:
    a = Money("10.00", "USD")
    b = Money(Decimal("10.0"), "usd")

    assert a == b


def test_money_comparison_operators() -> None:
    smaller = Money("5.00", "USD")
    bigger = Money("10.00", "USD")

    assert smaller < bigger
    assert smaller <= bigger
    assert bigger > smaller
    assert bigger >= smaller


def test_money_comparison_raises_on_currency_mismatch() -> None:
    usd = Money("5.00", "USD")
    eur = Money("5.00", "EUR")

    with pytest.raises(CurrencyMismatchError):
        _ = usd < eur
