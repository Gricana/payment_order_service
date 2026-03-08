from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from application.dto.payment import PaymentDTO
from application.ports.bank_api import (
    AbstractBankApiClient,
    AbstractCorrelationIdProvider,
    BankApiError,
    BankApiUnavailableError,
    BankPaymentNotFoundError,
)
from application.ports.unit_of_work import AbstractUnitOfWork
from domain.entities.order import Order
from domain.entities.payment import Payment
from domain.exceptions import OrderNotFoundError, PaymentNotFoundError
from domain.value_objects.enums import BankPaymentStatus, PaymentType
from domain.value_objects.identifiers import OrderId, PaymentId
from domain.value_objects.money import Money

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class SyncAcquiringStatusCommand:
    """Command to synchronize acquiring payment status with bank API."""

    order_id: str
    payment_id: str


@dataclass(slots=True)
class SyncAcquiringStatusUseCase:
    """Use case for background synchronization of acquiring payment status.

    Designed to be run by schedulers/workers to reconcile our state with the bank.
    """

    uow: AbstractUnitOfWork
    bank_api: AbstractBankApiClient
    correlation_id_provider: AbstractCorrelationIdProvider

    async def execute(self, command: SyncAcquiringStatusCommand) -> PaymentDTO:
        logger.info(
            "sync_acquiring.started",
            order_id=command.order_id,
            payment_id=command.payment_id,
        )

        order_id = OrderId.from_string(command.order_id)
        payment_id = PaymentId.from_string(command.payment_id)

        async with self.uow:
            order: Order | None = await self.uow.order_repository.get_by_id(order_id)
            if order is None:
                logger.warning("sync_acquiring.order_not_found", order_id=command.order_id)
                raise OrderNotFoundError(f"Order {order_id} not found.")

            payment: Payment | None = next((p for p in order.payments if p.id == payment_id), None)
            if payment is None:
                logger.warning(
                    "sync_acquiring.payment_not_found",
                    order_id=command.order_id,
                    payment_id=command.payment_id,
                )
                raise PaymentNotFoundError(f"Payment {payment_id} not found for order {order_id}.")

            if payment.payment_type != PaymentType.ACQUIRING or payment.acquiring_details is None:
                raise PaymentNotFoundError(
                    f"Payment {payment_id} is not an acquiring payment with bank details."
                )

            correlation_id = self.correlation_id_provider.get_correlation_id()
            bank_payment_id = payment.acquiring_details.bank_payment_id

            try:
                bank_info = await self.bank_api.check_payment(
                    bank_payment_id=bank_payment_id,
                    correlation_id=correlation_id,
                )
            except (BankApiUnavailableError, BankPaymentNotFoundError, BankApiError) as exc:
                logger.error(
                    "sync_acquiring.bank_api_error",
                    order_id=command.order_id,
                    payment_id=command.payment_id,
                    bank_payment_id=bank_payment_id,
                    error=str(exc),
                )
                raise

            prev_status = payment.status
            payment.acquiring_details.bank_status = bank_info.status
            payment.acquiring_details.last_synced_at = datetime.now(UTC)

            if bank_info.status in {BankPaymentStatus.CAPTURED, BankPaymentStatus.AUTHORIZED}:
                payment.mark_completed()
            elif bank_info.status in {BankPaymentStatus.FAILED, BankPaymentStatus.CANCELLED}:
                payment.mark_failed()

            await self.uow.order_repository.update(order)
            await self.uow.publish_events(order.pull_events())

            logger.info(
                "sync_acquiring.completed",
                order_id=command.order_id,
                payment_id=command.payment_id,
                bank_payment_id=bank_payment_id,
                bank_status=bank_info.status,
                prev_payment_status=prev_status,
                new_payment_status=payment.status,
            )

            return PaymentDTO.from_domain(
                payment_id=payment.id,
                order_id=order.id,
                money=payment.amount,
                status=payment.status,
                created_at=payment.created_at,
                payment_type=payment.payment_type,
                refunded_amount=payment.refunded_amount or Money.zero(payment.amount.currency),
            )
