from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from domain.entities.order import Order
from domain.value_objects.enums import OrderPaymentStatus
from domain.value_objects.identifiers import OrderId
from domain.value_objects.money import Money
from infrastructure.persistence.db import Base
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from presentation.dependencies import get_uow
from presentation.main import app


async def _setup_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
async def test_create_payment_api_and_refund_flow() -> None:
    engine: AsyncEngine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    await _setup_db(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        from application.ports.unit_of_work import AbstractEventPublisher

        class NoopEventPublisher(AbstractEventPublisher):
            async def publish(self, event) -> None:  # type: ignore[override]
                return None

        uow = SqlAlchemyUnitOfWork(session=session, event_publisher=NoopEventPublisher())
        order_id = OrderId.new()
        order = Order(
            id=order_id,
            total_amount=Money(Decimal("100.00"), "USD"),
            payment_status=OrderPaymentStatus.UNPAID,
        )
        await uow.order_repository.add(order)
        await uow.commit()

    async def override_get_uow():
        from application.ports.unit_of_work import AbstractEventPublisher

        class NoopEventPublisher(AbstractEventPublisher):
            async def publish(self, event) -> None:  # type: ignore[override]
                return None

        async with session_factory() as session:
            yield SqlAlchemyUnitOfWork(session=session, event_publisher=NoopEventPublisher())

    app.dependency_overrides[get_uow] = override_get_uow

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # create payment
        resp = await client.post(
            f"/api/v1/orders/{order_id.value}/payments",
            json={"amount": "50.00", "currency": "USD", "payment_type": "cash"},
        )
        assert resp.status_code == 201, resp.text
        payment = resp.json()

        # refund payment
        resp_refund = await client.post(
            f"/api/v1/orders/{order_id.value}/payments/{payment['id']}/refund",
            json={"amount": "10.00", "currency": "USD"},
        )
        assert resp_refund.status_code == 200, resp_refund.text
        refund_payload = resp_refund.json()
        assert refund_payload["refunded_amount"] == "10.00"
