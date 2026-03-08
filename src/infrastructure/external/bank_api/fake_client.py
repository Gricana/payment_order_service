from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

import structlog

from application.ports.bank_api import AbstractBankApiClient, BankPaymentInfo
from domain.value_objects.enums import BankPaymentStatus
from domain.value_objects.money import Money

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class FakeBankApiClient(AbstractBankApiClient):
    """In‑memory fake implementation of bank API for local/dev use."""

    _payments: dict[str, BankPaymentInfo] = field(default_factory=dict)

    async def start_acquiring(
        self,
        *,
        order_id: str,
        amount: Money,
        correlation_id: str,
    ) -> str:
        bank_payment_id = str(uuid4())
        info = BankPaymentInfo(
            bank_payment_id=bank_payment_id,
            status=BankPaymentStatus.CAPTURED,
            amount=amount,
        )
        self._payments[bank_payment_id] = info
        logger.info(
            "fake_bank.start_acquiring",
            order_id=order_id,
            bank_payment_id=bank_payment_id,
            amount=str(amount.amount),
            currency=amount.currency,
            correlation_id=correlation_id,
        )
        return bank_payment_id

    async def check_payment(
        self,
        *,
        bank_payment_id: str,
        correlation_id: str,
    ) -> BankPaymentInfo:
        logger.info(
            "fake_bank.check_payment",
            bank_payment_id=bank_payment_id,
            correlation_id=correlation_id,
        )
        info = self._payments.get(bank_payment_id)
        if info is None:
            return BankPaymentInfo(
                bank_payment_id=bank_payment_id,
                status=BankPaymentStatus.PENDING,
                amount=Money.zero("USD"),
            )
        return info
