from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

from domain.value_objects.enums import BankPaymentStatus
from domain.value_objects.money import Money


class BankApiError(Exception):
    """Base error for bank API issues."""


class BankPaymentNotFoundError(BankApiError):
    """Raised when bank payment cannot be found."""


class BankApiUnavailableError(BankApiError):
    """Raised when bank API is temporarily unavailable."""


@dataclass(frozen=True, slots=True)
class BankPaymentInfo:
    """Internal representation of bank payment state from external API."""

    bank_payment_id: str
    status: BankPaymentStatus
    amount: Money


class AbstractBankApiClient(ABC):
    """Port for communication with external bank acquiring API."""

    @abstractmethod
    async def start_acquiring(self, *, order_id: str, amount: Money, correlation_id: str) -> str:
        """Initiate acquiring payment and return bank_payment_id."""

    @abstractmethod
    async def check_payment(self, *, bank_payment_id: str, correlation_id: str) -> BankPaymentInfo:
        """Check current state of acquiring payment."""


class AbstractCorrelationIdProvider(Protocol):
    """Abstraction to obtain correlation IDs for logging/tracing."""

    def get_correlation_id(self) -> str:  # pragma: no cover - interface
        ...
