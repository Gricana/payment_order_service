from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from domain.entities.order import Order
from domain.entities.payment import Payment
from domain.value_objects.enums import OrderPaymentStatus, PaymentStatus, PaymentType
from domain.value_objects.identifiers import OrderId, PaymentId
from domain.value_objects.money import Money
from infrastructure.persistence.db import Base
from infrastructure.persistence.repositories.order_repository import SqlAlchemyOrderRepository


async def _setup_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
async def test_order_repository_persists_and_loads_order_with_payments() -> None:
    engine: AsyncEngine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    await _setup_db(engine)
    session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    async with session_factory() as session:
        repo = SqlAlchemyOrderRepository(session)
        order_id = OrderId.new()
        payment_id = PaymentId.new()

        order = Order(
            id=order_id,
            total_amount=Money(Decimal("100.00"), "USD"),
            payment_status=OrderPaymentStatus.UNPAID,
            payments=[
                Payment(
                    id=payment_id,
                    order_id=order_id,
                    payment_type=PaymentType.CASH,
                    amount=Money("50.00", "USD"),
                    status=PaymentStatus.COMPLETED,
                )
            ],
        )

        await repo.add(order)
        await session.commit()

    async with session_factory() as session:
        repo = SqlAlchemyOrderRepository(session)
        loaded = await repo.get_by_id(order_id)

        assert loaded is not None
        assert loaded.id == order_id
        assert len(loaded.payments) == 1
        assert loaded.payments[0].amount.amount == Decimal("50.00")
