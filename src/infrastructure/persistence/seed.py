from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from domain.value_objects.enums import OrderPaymentStatus
from infrastructure.persistence.db import create_engine, create_session_factory
from infrastructure.persistence.models.order import OrderORM
from presentation.settings import settings

SEED_ORDERS = [
    {"id": uuid4(), "total_amount": Decimal("1000.00"), "currency": "RUB"},
    {"id": uuid4(), "total_amount": Decimal("2500.50"), "currency": "RUB"},
    {"id": uuid4(), "total_amount": Decimal("500.00"), "currency": "RUB"},
]


async def seed_orders() -> None:
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(OrderORM))
        if count and count > 0:
            print(f"Seed skipped: {count} orders already exist")
            await engine.dispose()
            return

        now = datetime.now(UTC)
        for data in SEED_ORDERS:
            session.add(
                OrderORM(
                    id=data["id"],
                    total_amount=data["total_amount"],
                    currency=data["currency"],
                    payment_status=OrderPaymentStatus.UNPAID,
                    created_at=now,
                    updated_at=now,
                )
            )

        await session.commit()
        print(f"Seeded {len(SEED_ORDERS)} orders")

    await engine.dispose()
