from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-level errors."""


class MoneyError(DomainError):
    """Errors related to Money value object."""


class NegativeAmountError(MoneyError):
    """Raised when attempting to create Money with negative amount."""


class CurrencyMismatchError(MoneyError):
    """Raised when performing operations on Money with different currencies."""


class OrderError(DomainError):
    """Base class for order-related errors."""


class OrderNotFoundError(OrderError):
    """Raised when order aggregate cannot be found."""


class PaymentNotFoundError(OrderError):
    """Raised when payment entity cannot be found within an order."""


class InsufficientFundsError(OrderError):
    """Raised when attempting to refund more than deposited."""


class OrderAlreadyPaidError(OrderError):
    """Raised when attempting to create a payment for an already fully paid order."""


class PaymentError(DomainError):
    """Base class for payment-related errors."""
