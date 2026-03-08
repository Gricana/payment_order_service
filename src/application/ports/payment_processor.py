from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

from domain.entities.payment import Payment
from domain.value_objects.enums import PaymentType
from domain.value_objects.money import Money


class AbstractPaymentProcessor(ABC):
    """Strategy for processing payments of a specific type."""

    @property
    @abstractmethod
    def payment_type(self) -> PaymentType:
        raise NotImplementedError

    @abstractmethod
    async def start_payment(self, payment: Payment) -> Payment:
        """Initiate payment with external systems if needed."""

    @abstractmethod
    async def refund(self, payment: Payment, amount: Money) -> Payment:
        """Process refund for a given payment."""


class PaymentProcessorFactory(Protocol):
    """Factory abstraction to resolve processor by payment type."""

    def get_processor(
        self, payment_type: PaymentType
    ) -> AbstractPaymentProcessor:  # pragma: no cover - interface
        ...


@dataclass(slots=True)
class SimplePaymentProcessorFactory:
    """In-memory registry-based processor factory.

    Keeps implementation simple while allowing easy extension with new processors.
    """

    processors: dict[PaymentType, AbstractPaymentProcessor]

    def get_processor(self, payment_type: PaymentType) -> AbstractPaymentProcessor:
        try:
            return self.processors[payment_type]
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise ValueError(f"No payment processor registered for type {payment_type}") from exc
