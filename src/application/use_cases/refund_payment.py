from __future__ import annotations

from dataclasses import dataclass

import structlog

from application.dto.payment import PaymentDTO
from application.ports.payment_processor import PaymentProcessorFactory
from application.ports.unit_of_work import AbstractUnitOfWork
from domain.entities.order import Order
from domain.exceptions import DomainError, OrderNotFoundError, PaymentNotFoundError
from domain.value_objects.identifiers import OrderId, PaymentId
from domain.value_objects.money import Money

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class RefundPaymentCommand:
    order_id: str
    payment_id: str
    amount: str
    currency: str


@dataclass(slots=True)
class RefundPaymentUseCase:
    """Use case for refunding an existing payment."""

    uow: AbstractUnitOfWork
    processor_factory: PaymentProcessorFactory

    async def execute(self, command: RefundPaymentCommand) -> PaymentDTO:
        logger.info(
            "refund_payment.started",
            order_id=command.order_id,
            payment_id=command.payment_id,
            amount=command.amount,
            currency=command.currency,
        )

        try:
            return await self._execute(command)
        except DomainError as exc:
            logger.warning(
                "refund_payment.domain_error",
                order_id=command.order_id,
                payment_id=command.payment_id,
                error=type(exc).__name__,
                detail=str(exc),
            )
            raise

    async def _execute(self, command: RefundPaymentCommand) -> PaymentDTO:
        """Internal implementation — all domain errors bubble up to execute() for logging."""

        order_id = OrderId.from_string(command.order_id)
        payment_id = PaymentId.from_string(command.payment_id)
        amount = Money(command.amount, command.currency)

        async with self.uow:
            order: Order | None = await self.uow.order_repository.get_by_id(order_id)
            if order is None:
                logger.warning("refund_payment.order_not_found", order_id=command.order_id)
                raise OrderNotFoundError(f"Order {order_id} not found.")

            payment = next((p for p in order.payments if p.id == payment_id), None)
            if payment is None:
                logger.warning(
                    "refund_payment.payment_not_found",
                    order_id=command.order_id,
                    payment_id=command.payment_id,
                )
                raise PaymentNotFoundError(f"Payment {payment_id} not found for order {order_id}.")

            # Apply refund via aggregate root (enforces invariants)
            order.apply_refund(payment_id, amount)

            processor = self.processor_factory.get_processor(payment.payment_type)
            await processor.refund(payment, amount)

            await self.uow.order_repository.update(order)
            await self.uow.publish_events(order.pull_events())

            updated_payment = next(p for p in order.payments if p.id == payment_id)

            logger.info(
                "refund_payment.completed",
                order_id=command.order_id,
                payment_id=command.payment_id,
                refunded_amount=command.amount,
                currency=command.currency,
                payment_status=updated_payment.status,
                order_payment_status=order.payment_status,
            )

            return PaymentDTO.from_domain(
                payment_id=updated_payment.id,
                order_id=order.id,
                money=updated_payment.amount,
                status=updated_payment.status,
                created_at=updated_payment.created_at,
                payment_type=updated_payment.payment_type,
                refunded_amount=updated_payment.refunded_amount
                or Money.zero(updated_payment.amount.currency),
            )
