from __future__ import annotations

from dataclasses import dataclass, field

from application.ports.order_repository import AbstractOrderRepository
from domain.entities.order import Order
from domain.entities.payment import Payment
from domain.value_objects.identifiers import OrderId


@dataclass(slots=True)
class FakeOrderRepository(AbstractOrderRepository):
    """In-memory implementation of Order repository for unit tests."""

    _store: dict[OrderId, Order] = field(default_factory=dict)

    async def get_by_id(self, order_id: OrderId) -> Order | None:  # type: ignore[override]
        return self._store.get(order_id)

    async def find_payment_by_idempotency_key(  # type: ignore[override]
        self,
        order_id: OrderId,
        idempotency_key: str,
    ) -> Payment | None:
        order = self._store.get(order_id)
        if order is None:
            return None
        return next(
            (p for p in order.payments if p.client_reference_id == idempotency_key),
            None,
        )

    async def add(self, order: Order) -> None:  # type: ignore[override]
        self._store[order.id] = order

    async def update(self, order: Order) -> None:  # type: ignore[override]
        self._store[order.id] = order
