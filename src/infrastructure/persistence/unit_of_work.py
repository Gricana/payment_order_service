from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from application.ports.unit_of_work import AbstractEventPublisher, AbstractUnitOfWork
from infrastructure.persistence.repositories.order_repository import (
    SqlAlchemyOrderRepository,
)


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    """SQLAlchemy-based Unit of Work implementation."""

    def __init__(self, session: AsyncSession, event_publisher: AbstractEventPublisher) -> None:
        super().__init__(event_publisher)
        self._session = session
        self.order_repository = SqlAlchemyOrderRepository(session)

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
