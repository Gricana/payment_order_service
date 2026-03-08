from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from application.ports.bank_api import AbstractBankApiClient, BankPaymentInfo
from domain.value_objects.enums import BankPaymentStatus
from domain.value_objects.money import Money


@dataclass(slots=True)
class FakeBankApiClient(AbstractBankApiClient):
    """In-memory fake implementation of bank API for unit tests."""

    should_fail: bool = False
    calls: list[dict[str, str]] = field(default_factory=list)
    _payments: dict[str, BankPaymentInfo] = field(default_factory=dict)

    async def start_acquiring(
        self,
        *,
        order_id: str,
        amount: Money,
        correlation_id: str,
    ) -> str:
        self.calls.append({"method": "start_acquiring", "order_id": order_id})
        if self.should_fail:
            raise RuntimeError("Bank API failure (simulated)")

        bank_payment_id = str(uuid4())
        info = BankPaymentInfo(
            bank_payment_id=bank_payment_id,
            status=BankPaymentStatus.CAPTURED,
            amount=amount,
        )
        self._payments[bank_payment_id] = info
        return bank_payment_id

    async def check_payment(
        self,
        *,
        bank_payment_id: str,
        correlation_id: str,
    ) -> BankPaymentInfo:
        self.calls.append({"method": "check_payment", "bank_payment_id": bank_payment_id})
        if self.should_fail:
            raise RuntimeError("Bank API failure (simulated)")

        return self._payments[bank_payment_id]
