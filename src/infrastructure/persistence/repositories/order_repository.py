from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports.order_repository import AbstractOrderRepository
from domain.entities.order import Order
from domain.entities.payment import AcquiringPaymentDetails, Payment
from domain.value_objects.identifiers import OrderId, PaymentId
from domain.value_objects.money import Money
from infrastructure.persistence.models.acquiring_details import AcquiringDetailsORM
from infrastructure.persistence.models.order import OrderORM
from infrastructure.persistence.models.payment import PaymentORM


class SqlAlchemyOrderRepository(AbstractOrderRepository):
    """SQLAlchemy implementation of the Order repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, order_id: OrderId) -> Order | None:
        stmt = select(OrderORM).where(OrderORM.id == order_id.value)
        result = await self._session.execute(stmt)
        orm: OrderORM | None = result.scalar_one_or_none()
        if orm is None:
            return None
        return self._to_domain(orm)

    async def find_payment_by_idempotency_key(
        self,
        order_id: OrderId,
        idempotency_key: str,
    ) -> Payment | None:
        """Direct indexed DB lookup — O(log n) instead of O(n) in-memory scan."""
        stmt = select(PaymentORM).where(
            PaymentORM.order_id == order_id.value,
            PaymentORM.client_reference_id == idempotency_key,
        )
        result = await self._session.execute(stmt)
        orm: PaymentORM | None = result.scalar_one_or_none()
        if orm is None:
            return None
        return self._payment_to_domain(orm)

    async def add(self, order: Order) -> None:
        orm = self._to_orm(order)
        self._session.add(orm)

    async def update(self, order: Order) -> None:
        existing = await self._session.get(OrderORM, order.id.value)
        if existing is None:
            self._session.add(self._to_orm(order))
            return

        existing.payment_status = order.payment_status
        existing.updated_at = datetime.now(UTC)

        existing_payments: dict[uuid.UUID, PaymentORM] = {p.id: p for p in existing.payments}

        domain_payments: dict[uuid.UUID, Payment] = {p.id.value: p for p in order.payments}

        for payment_id, payment_orm in list(existing_payments.items()):
            if payment_id not in domain_payments:
                await self._session.delete(payment_orm)

        for payment_id, payment in domain_payments.items():
            if payment_id in existing_payments:
                await self._sync_payment_orm(existing_payments[payment_id], payment)
            else:
                existing.payments.append(self._payment_to_orm(payment))

    async def _sync_payment_orm(self, orm: PaymentORM, payment: Payment) -> None:
        """Update only mutable fields of an existing payment ORM."""
        orm.status = payment.status
        orm.refunded_amount = (
            payment.refunded_amount.amount if payment.refunded_amount is not None else None
        )
        orm.updated_at = datetime.now(UTC)
        await self._sync_acquiring_details(orm, payment)

    async def _sync_acquiring_details(self, orm: PaymentORM, payment: Payment) -> None:
        """Sync acquiring details: insert, update or delete."""
        if payment.acquiring_details is None:
            if orm.acquiring_details is not None:
                await self._session.delete(orm.acquiring_details)
            return

        if orm.acquiring_details is not None:
            orm.acquiring_details.bank_status = payment.acquiring_details.bank_status
            orm.acquiring_details.bank_paid_at = payment.acquiring_details.bank_paid_at
            orm.acquiring_details.last_synced_at = payment.acquiring_details.last_synced_at
        else:
            orm.acquiring_details = AcquiringDetailsORM(
                id=payment.id.value,
                payment_id=payment.id.value,
                bank_payment_id=payment.acquiring_details.bank_payment_id,
                bank_status=payment.acquiring_details.bank_status,
                bank_paid_at=payment.acquiring_details.bank_paid_at,
                last_synced_at=payment.acquiring_details.last_synced_at,
            )

    def _to_domain(self, orm: OrderORM) -> Order:
        from domain.entities.order import Order as DomainOrder

        order = DomainOrder(
            id=OrderId(orm.id),
            total_amount=Money(str(orm.total_amount), orm.currency),
            payment_status=orm.payment_status,
            payments=[],
        )
        for payment_orm in orm.payments:
            order.payments.append(self._payment_to_domain(payment_orm))
        return order

    def _to_orm(self, order: Order) -> OrderORM:
        now = datetime.now(UTC)
        orm = OrderORM(
            id=order.id.value,
            total_amount=order.total_amount.amount,
            currency=order.total_amount.currency,
            payment_status=order.payment_status,
            created_at=now,
            updated_at=now,
        )
        for payment in order.payments:
            orm.payments.append(self._payment_to_orm(payment))
        return orm

    def _payment_to_domain(self, orm: PaymentORM) -> Payment:
        acquiring_details: AcquiringPaymentDetails | None = None
        if orm.acquiring_details:
            ad = orm.acquiring_details
            acquiring_details = AcquiringPaymentDetails(
                bank_payment_id=ad.bank_payment_id,
                bank_status=ad.bank_status,
                bank_paid_at=ad.bank_paid_at,
                last_synced_at=ad.last_synced_at,
            )
        payment = Payment(
            id=PaymentId(orm.id),
            order_id=OrderId(orm.order_id),
            payment_type=orm.payment_type,
            amount=Money(str(orm.amount), orm.currency),
            status=orm.status,
            created_at=orm.created_at,
            acquiring_details=acquiring_details,
        )
        if orm.refunded_amount is not None:
            payment.refunded_amount = Money(str(orm.refunded_amount), orm.currency)
        payment.client_reference_id = orm.client_reference_id
        return payment

    def _payment_to_orm(self, payment: Payment) -> PaymentORM:
        now = datetime.now(UTC)
        orm = PaymentORM(
            id=payment.id.value,
            order_id=payment.order_id.value,
            payment_type=payment.payment_type,
            amount=payment.amount.amount,
            currency=payment.amount.currency,
            status=payment.status,
            created_at=payment.created_at,
            updated_at=now,
            refunded_amount=payment.refunded_amount.amount
            if payment.refunded_amount is not None
            else None,
            client_reference_id=payment.client_reference_id,
        )
        if payment.acquiring_details is not None:
            ad = payment.acquiring_details
            orm.acquiring_details = AcquiringDetailsORM(
                id=payment.id.value,
                payment_id=payment.id.value,
                bank_payment_id=ad.bank_payment_id,
                bank_status=ad.bank_status,
                bank_paid_at=ad.bank_paid_at,
                last_synced_at=ad.last_synced_at,
            )
        return orm
