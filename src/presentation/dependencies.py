from __future__ import annotations

from fastapi import Depends

from application.ports.payment_processor import SimplePaymentProcessorFactory
from application.use_cases.create_payment import CreatePaymentUseCase
from application.use_cases.refund_payment import RefundPaymentUseCase
from infrastructure.external.bank_api.client import HttpBankApiClient
from infrastructure.logging.correlation import CorrelationIdProvider, set_correlation_id
from infrastructure.persistence.db import create_engine, create_session_factory
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from presentation.settings import settings

engine = create_engine(settings.database_url)
session_factory = create_session_factory(engine)


async def get_uow():
    from application.ports.unit_of_work import AbstractEventPublisher

    class NoopEventPublisher(AbstractEventPublisher):
        async def publish(self, event) -> None:
            return None

    async with session_factory() as session:
        yield SqlAlchemyUnitOfWork(session=session, event_publisher=NoopEventPublisher())


def get_correlation_provider() -> CorrelationIdProvider:
    set_correlation_id()
    return CorrelationIdProvider()


def get_bank_client():
    from infrastructure.external.bank_api.fake_client import FakeBankApiClient

    if settings.bank_api_mode.lower() == "http":
        return HttpBankApiClient(base_url=settings.bank_api_base_url)
    return FakeBankApiClient()


def get_processor_factory(
    bank_client: HttpBankApiClient = Depends(get_bank_client),
    correlation_provider: CorrelationIdProvider = Depends(get_correlation_provider),
) -> SimplePaymentProcessorFactory:
    from domain.value_objects.enums import PaymentType
    from infrastructure.payments.processors import (
        AcquiringPaymentProcessor,
        CashPaymentProcessor,
    )

    cash = CashPaymentProcessor()
    acquiring = AcquiringPaymentProcessor(
        bank_api=bank_client,
        correlation_id_provider=correlation_provider,
    )
    return SimplePaymentProcessorFactory(
        processors={
            PaymentType.CASH: cash,
            PaymentType.ACQUIRING: acquiring,
        }
    )


def get_create_payment_use_case(
    uow=Depends(get_uow),
    processor_factory: SimplePaymentProcessorFactory = Depends(get_processor_factory),
) -> CreatePaymentUseCase:
    return CreatePaymentUseCase(
        uow=uow,
        order_repository=uow.order_repository,
        processor_factory=processor_factory,
    )


def get_refund_payment_use_case(
    uow=Depends(get_uow),
    processor_factory: SimplePaymentProcessorFactory = Depends(get_processor_factory),
) -> RefundPaymentUseCase:
    return RefundPaymentUseCase(
        uow=uow,
        processor_factory=processor_factory,
    )
