from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, getcontext
from typing import Any

from domain.exceptions import CurrencyMismatchError, NegativeAmountError

getcontext().prec = 28


@dataclass(frozen=True, slots=True)
class Money:
    """Immutable value object representing monetary amount in a specific currency."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        normalized_amount = self._normalize(self.amount)
        if normalized_amount < Decimal("0"):
            raise NegativeAmountError("Money amount cannot be negative.")
        object.__setattr__(self, "amount", normalized_amount)
        object.__setattr__(self, "currency", self.currency.upper())

    @staticmethod
    def _normalize(value: Any) -> Decimal:
        if isinstance(value, Decimal):
            dec = value
        else:
            dec = Decimal(str(value))
        return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _assert_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"Currency mismatch: {self.currency} != {other.currency}")

    def __add__(self, other: Money) -> Money:
        self._assert_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._assert_same_currency(other)
        result = self.amount - other.amount
        if result < Decimal("0"):
            raise NegativeAmountError("Resulting Money amount cannot be negative.")
        return Money(result, self.currency)

    def __mul__(self, factor: Any) -> Money:
        dec_factor = Decimal(str(factor))
        result = self.amount * dec_factor
        return Money(result, self.currency)

    # Comparison operators are defined in terms of the underlying Decimal amount
    # but still enforce currency equality to avoid accidental cross-currency math.
    def __lt__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.amount >= other.amount

    def is_zero(self) -> bool:
        return self.amount == Decimal("0.00")

    @classmethod
    def zero(cls, currency: str) -> Money:
        return cls(Decimal("0.00"), currency)
