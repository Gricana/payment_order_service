from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from domain.entities.order import Order
from domain.entities.payment import Payment
from domain.value_objects.identifiers import OrderId


class OrderReader(Protocol):
    """Read-only operations for Order aggregate."""

    async def get_by_id(self, order_id: OrderId) -> Order | None:  # pragma: no cover - interface
        ...

    async def find_payment_by_idempotency_key(  # pragma: no cover - interface
        self,
        order_id: OrderId,
        idempotency_key: str,
    ) -> Payment | None: ...


class OrderWriter(Protocol):
    """Write operations for Order aggregate."""

    async def add(self, order: Order) -> None:  # pragma: no cover - interface
        ...

    async def update(self, order: Order) -> None:  # pragma: no cover - interface
        ...


class AbstractOrderRepository(OrderReader, OrderWriter, ABC):
    """Repository abstraction for Order aggregate."""

    @abstractmethod
    async def get_by_id(self, order_id: OrderId) -> Order | None:
        raise NotImplementedError

    @abstractmethod
    async def find_payment_by_idempotency_key(
        self,
        order_id: OrderId,
        idempotency_key: str,
    ) -> Payment | None:
        """Find an existing payment by idempotency key using a direct DB query."""
        raise NotImplementedError

    @abstractmethod
    async def add(self, order: Order) -> None:
        raise NotImplementedError

    @abstractmethod
    async def update(self, order: Order) -> None:
        raise NotImplementedError
