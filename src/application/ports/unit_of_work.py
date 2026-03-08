from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from application.ports.order_repository import AbstractOrderRepository
from domain.events import DomainEvent


class AbstractEventPublisher(Protocol):
    """Port for publishing domain events to the outside world."""

    async def publish(self, event: DomainEvent) -> None:  # pragma: no cover - interface
        ...


class AbstractUnitOfWork(ABC):
    """Unit of Work abstraction for transactional operations on aggregates."""

    order_repository: AbstractOrderRepository

    def __init__(self, event_publisher: AbstractEventPublisher) -> None:
        self._event_publisher = event_publisher

    async def __aenter__(self) -> AbstractUnitOfWork:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            await self.rollback()
        else:
            await self.commit()

    @abstractmethod
    async def commit(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def rollback(self) -> None:
        raise NotImplementedError

    async def publish_events(self, events: list[DomainEvent]) -> None:
        for event in events:
            await self._event_publisher.publish(event)
