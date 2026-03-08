from __future__ import annotations

from dataclasses import dataclass

import structlog

from application.ports.bank_api import AbstractBankApiClient, AbstractCorrelationIdProvider
from application.ports.payment_processor import AbstractPaymentProcessor
from domain.entities.payment import AcquiringPaymentDetails, Payment
from domain.value_objects.enums import BankPaymentStatus, PaymentStatus, PaymentType
from domain.value_objects.money import Money

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class CashPaymentProcessor(AbstractPaymentProcessor):
    """Processor for cash payments: marks them as completed immediately."""

    @property
    def payment_type(self) -> PaymentType:
        return PaymentType.CASH

    async def start_payment(self, payment: Payment) -> Payment:
        logger.info(
            "payments.cash.start",
            payment_id=str(payment.id),
            order_id=str(payment.order_id),
        )
        payment.status = PaymentStatus.COMPLETED
        return payment

    async def refund(self, payment: Payment, amount: Money) -> Payment:
        logger.info(
            "payments.cash.refund",
            payment_id=str(payment.id),
            order_id=str(payment.order_id),
            amount=str(amount.amount),
        )
        return payment


@dataclass(slots=True)
class AcquiringPaymentProcessor(AbstractPaymentProcessor):
    """Processor for acquiring payments integrating with bank API."""

    bank_api: AbstractBankApiClient
    correlation_id_provider: AbstractCorrelationIdProvider

    @property
    def payment_type(self) -> PaymentType:
        return PaymentType.ACQUIRING

    async def start_payment(self, payment: Payment) -> Payment:
        correlation_id = self.correlation_id_provider.get_correlation_id()
        logger.info(
            "payments.acquiring.start",
            payment_id=str(payment.id),
            order_id=str(payment.order_id),
            correlation_id=correlation_id,
        )
        bank_payment_id = await self.bank_api.start_acquiring(
            order_id=str(payment.order_id.value),
            amount=payment.amount,
            correlation_id=correlation_id,
        )
        payment.acquiring_details = AcquiringPaymentDetails(
            bank_payment_id=bank_payment_id,
            bank_status=BankPaymentStatus.PENDING,
        )
        bank_info = await self.bank_api.check_payment(
            bank_payment_id=bank_payment_id,
            correlation_id=correlation_id,
        )
        payment.acquiring_details.bank_status = bank_info.status
        if bank_info.status in {BankPaymentStatus.CAPTURED, BankPaymentStatus.AUTHORIZED}:
            payment.status = PaymentStatus.COMPLETED
        else:
            payment.status = PaymentStatus.PENDING
        return payment

    async def refund(self, payment: Payment, amount: Money) -> Payment:
        if payment.acquiring_details is None:
            raise ValueError("Acquiring details are required for acquiring payment.")

        logger.info(
            "payments.acquiring.refund",
            payment_id=str(payment.id),
            order_id=str(payment.order_id),
        )
        return payment
