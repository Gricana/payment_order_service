from __future__ import annotations

from dataclasses import dataclass

import structlog

from application.dto.payment import PaymentDTO
from application.ports.order_repository import AbstractOrderRepository
from application.ports.payment_processor import PaymentProcessorFactory
from application.ports.unit_of_work import AbstractUnitOfWork
from domain.entities.payment import Payment
from domain.exceptions import DomainError, OrderAlreadyPaidError, OrderNotFoundError
from domain.value_objects.enums import OrderPaymentStatus, PaymentType
from domain.value_objects.identifiers import OrderId, PaymentId
from domain.value_objects.money import Money

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class CreatePaymentCommand:
    order_id: str
    amount: str
    currency: str
    payment_type: PaymentType
    idempotency_key: str | None = None


@dataclass(slots=True)
class CreatePaymentUseCase:
    """Use case for creating a new payment for an order."""

    uow: AbstractUnitOfWork
    order_repository: AbstractOrderRepository
    processor_factory: PaymentProcessorFactory

    async def execute(self, command: CreatePaymentCommand) -> PaymentDTO:
        """Create a payment and apply it to the order aggregate."""
        logger.info(
            "create_payment.started",
            order_id=command.order_id,
            amount=command.amount,
            currency=command.currency,
            payment_type=command.payment_type,
            has_idempotency_key=bool(command.idempotency_key),
        )

        try:
            return await self._execute(command)
        except DomainError as exc:
            logger.warning(
                "create_payment.domain_error",
                order_id=command.order_id,
                error=type(exc).__name__,
                detail=str(exc),
            )
            raise

    async def _execute(self, command: CreatePaymentCommand) -> PaymentDTO:
        """Internal implementation — all domain errors bubble up to execute() for logging."""

        order_id = OrderId.from_string(command.order_id)
        amount = Money(command.amount, command.currency)

        async with self.uow:
            order = await self.order_repository.get_by_id(order_id)
            if order is None:
                logger.warning("create_payment.order_not_found", order_id=command.order_id)
                raise OrderNotFoundError(f"Order {order_id} not found.")

            if order.payment_status == OrderPaymentStatus.PAID:
                logger.warning(
                    "create_payment.order_already_paid",
                    order_id=command.order_id,
                )
                raise OrderAlreadyPaidError("Order already fully paid.")

            if command.idempotency_key:
                existing = next(
                    (p for p in order.payments if p.client_reference_id == command.idempotency_key),
                    None,
                )
                if existing is not None:
                    logger.info(
                        "create_payment.idempotent_hit",
                        order_id=command.order_id,
                        payment_id=str(existing.id),
                        idempotency_key=command.idempotency_key,
                    )
                    return PaymentDTO.from_domain(
                        payment_id=existing.id,
                        order_id=order.id,
                        money=existing.amount,
                        status=existing.status,
                        created_at=existing.created_at,
                        payment_type=existing.payment_type,
                        refunded_amount=existing.refunded_amount
                        or Money.zero(existing.amount.currency),
                    )

            payment = Payment(
                id=PaymentId.new(),
                order_id=order.id,
                payment_type=command.payment_type,
                amount=amount,
                client_reference_id=command.idempotency_key,
            )

            order.add_payment(payment)

            processor = self.processor_factory.get_processor(command.payment_type)
            await processor.start_payment(payment)

            await self.order_repository.update(order)
            await self.uow.publish_events(order.pull_events())

            logger.info(
                "create_payment.completed",
                order_id=command.order_id,
                payment_id=str(payment.id),
                payment_type=command.payment_type,
                amount=command.amount,
                currency=command.currency,
                status=payment.status,
                order_payment_status=order.payment_status,
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
