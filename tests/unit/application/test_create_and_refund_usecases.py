from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from application.ports.payment_processor import (
    AbstractPaymentProcessor,
    SimplePaymentProcessorFactory,
)
from application.ports.unit_of_work import AbstractEventPublisher, AbstractUnitOfWork
from application.use_cases.create_payment import CreatePaymentCommand, CreatePaymentUseCase
from application.use_cases.refund_payment import RefundPaymentCommand, RefundPaymentUseCase
from application.use_cases.sync_acquiring_status import (
    SyncAcquiringStatusCommand,
    SyncAcquiringStatusUseCase,
)
from domain.entities.order import Order
from domain.entities.payment import AcquiringPaymentDetails, Payment
from domain.exceptions import PaymentNotFoundError
from domain.value_objects.enums import (
    BankPaymentStatus,
    OrderPaymentStatus,
    PaymentStatus,
    PaymentType,
)
from domain.value_objects.identifiers import OrderId, PaymentId
from domain.value_objects.money import Money
from tests.fakes.fake_bank_client import FakeBankApiClient
from tests.fakes.fake_order_repository import FakeOrderRepository


class InMemoryEventPublisher(AbstractEventPublisher):
    def __init__(self) -> None:
        self.published: list[object] = []

    async def publish(self, event) -> None:  # type: ignore[override]
        self.published.append(event)


class InMemoryUnitOfWork(AbstractUnitOfWork):
    def __init__(self, repo: FakeOrderRepository, publisher: InMemoryEventPublisher) -> None:
        super().__init__(publisher)
        self.order_repository = repo
        self.committed = False

    async def commit(self) -> None:  # type: ignore[override]
        self.committed = True

    async def rollback(self) -> None:  # type: ignore[override]
        self.committed = False


@dataclass
class DummyProcessor(AbstractPaymentProcessor):
    _type: PaymentType

    @property
    def payment_type(self) -> PaymentType:
        return self._type

    async def start_payment(self, payment: Payment) -> Payment:
        payment.status = PaymentStatus.COMPLETED
        return payment

    async def refund(self, payment: Payment, amount: Money) -> Payment:
        return payment


class DummyCorrelationProvider:
    def __init__(self) -> None:
        self.counter = 0

    def get_correlation_id(self) -> str:
        self.counter += 1
        return f"test-{self.counter}"


@pytest.mark.asyncio
async def test_create_cash_payment_success() -> None:
    order_id = OrderId.new()
    order = Order(
        id=order_id,
        total_amount=Money(Decimal("100.00"), "USD"),
        payment_status=OrderPaymentStatus.UNPAID,
    )
    repo = FakeOrderRepository({_id: order for _id in [order_id]})
    publisher = InMemoryEventPublisher()
    uow = InMemoryUnitOfWork(repo, publisher)

    cash_processor = DummyProcessor(PaymentType.CASH)
    factory = SimplePaymentProcessorFactory(processors={PaymentType.CASH: cash_processor})

    use_case = CreatePaymentUseCase(
        uow=uow,
        order_repository=repo,
        processor_factory=factory,
    )

    cmd = CreatePaymentCommand(
        order_id=str(order_id.value),
        amount="50.00",
        currency="USD",
        payment_type=PaymentType.CASH,
    )

    dto = await use_case.execute(cmd)

    assert dto.amount == "50.00"
    assert dto.currency == "USD"
    assert dto.status == PaymentStatus.COMPLETED
    assert order.payment_status == OrderPaymentStatus.PARTIALLY_PAID


@pytest.mark.asyncio
async def test_create_acquiring_payment_calls_bank_api() -> None:
    order_id = OrderId.new()
    order = Order(
        id=order_id,
        total_amount=Money(Decimal("100.00"), "USD"),
        payment_status=OrderPaymentStatus.UNPAID,
    )
    repo = FakeOrderRepository({_id: order for _id in [order_id]})
    publisher = InMemoryEventPublisher()
    uow = InMemoryUnitOfWork(repo, publisher)

    bank_client = FakeBankApiClient()
    correlation = DummyCorrelationProvider()

    from application.ports.bank_api import AbstractCorrelationIdProvider
    from infrastructure.payments.processors import AcquiringPaymentProcessor

    class _CorrelationAdapter(AbstractCorrelationIdProvider):
        def __init__(self, inner: DummyCorrelationProvider) -> None:
            self._inner = inner

        def get_correlation_id(self) -> str:  # type: ignore[override]
            return self._inner.get_correlation_id()

    acquiring_processor = AcquiringPaymentProcessor(
        bank_api=bank_client,
        correlation_id_provider=_CorrelationAdapter(correlation),
    )
    factory = SimplePaymentProcessorFactory(
        processors={PaymentType.ACQUIRING: acquiring_processor},
    )

    use_case = CreatePaymentUseCase(
        uow=uow,
        order_repository=repo,
        processor_factory=factory,
    )

    cmd = CreatePaymentCommand(
        order_id=str(order_id.value),
        amount="20.00",
        currency="USD",
        payment_type=PaymentType.ACQUIRING,
    )

    dto = await use_case.execute(cmd)

    assert dto.status in {PaymentStatus.COMPLETED, PaymentStatus.PENDING}
    assert any(call["method"] == "start_acquiring" for call in bank_client.calls)


@pytest.mark.asyncio
async def test_refund_payment_success() -> None:
    order_id = OrderId.new()
    payment_id = PaymentId.new()
    payment = Payment(
        id=payment_id,
        order_id=order_id,
        payment_type=PaymentType.CASH,
        amount=Money("100.00", "USD"),
        status=PaymentStatus.COMPLETED,
    )
    order = Order(
        id=order_id,
        total_amount=Money("100.00", "USD"),
        payment_status=OrderPaymentStatus.PAID,
        payments=[payment],
    )
    repo = FakeOrderRepository({order_id: order})
    publisher = InMemoryEventPublisher()
    uow = InMemoryUnitOfWork(repo, publisher)

    cash_processor = DummyProcessor(PaymentType.CASH)
    factory = SimplePaymentProcessorFactory(processors={PaymentType.CASH: cash_processor})

    use_case = RefundPaymentUseCase(uow=uow, processor_factory=factory)

    cmd = RefundPaymentCommand(
        order_id=str(order_id.value),
        payment_id=str(payment_id.value),
        amount="40.00",
        currency="USD",
    )

    dto = await use_case.execute(cmd)

    assert dto.status == PaymentStatus.COMPLETED
    assert order.payment_status == OrderPaymentStatus.PARTIALLY_PAID
    assert dto.refunded_amount == "40.00"


@pytest.mark.asyncio
async def test_refund_raises_when_payment_not_found() -> None:
    order_id = OrderId.new()
    order = Order(
        id=order_id,
        total_amount=Money("100.00", "USD"),
        payment_status=OrderPaymentStatus.UNPAID,
        payments=[],
    )
    repo = FakeOrderRepository({order_id: order})
    publisher = InMemoryEventPublisher()
    uow = InMemoryUnitOfWork(repo, publisher)

    cash_processor = DummyProcessor(PaymentType.CASH)
    factory = SimplePaymentProcessorFactory(processors={PaymentType.CASH: cash_processor})

    use_case = RefundPaymentUseCase(uow=uow, processor_factory=factory)

    cmd = RefundPaymentCommand(
        order_id=str(order_id.value),
        payment_id=str(PaymentId.new().value),
        amount="10.00",
        currency="USD",
    )

    with pytest.raises(PaymentNotFoundError):
        await use_case.execute(cmd)


@pytest.mark.asyncio
async def test_sync_acquiring_updates_completed_status() -> None:
    order_id = OrderId.new()
    payment_id = PaymentId.new()

    payment = Payment(
        id=payment_id,
        order_id=order_id,
        payment_type=PaymentType.ACQUIRING,
        amount=Money("100.00", "USD"),
        status=PaymentStatus.PENDING,
        acquiring_details=AcquiringPaymentDetails(
            bank_payment_id="bank-1",
            bank_status=BankPaymentStatus.PENDING,
        ),
    )
    order = Order(
        id=order_id,
        total_amount=Money("100.00", "USD"),
        payment_status=OrderPaymentStatus.PARTIALLY_PAID,
        payments=[payment],
    )
    repo = FakeOrderRepository({order_id: order})
    publisher = InMemoryEventPublisher()
    uow = InMemoryUnitOfWork(repo, publisher)

    bank_client = FakeBankApiClient()

    from application.ports.bank_api import AbstractCorrelationIdProvider, BankPaymentInfo

    bank_client._payments["bank-1"] = BankPaymentInfo(
        bank_payment_id="bank-1",
        status=BankPaymentStatus.CAPTURED,
        amount=payment.amount,
    )

    correlation = DummyCorrelationProvider()

    class _CorrelationAdapter(AbstractCorrelationIdProvider):
        def __init__(self, inner: DummyCorrelationProvider) -> None:
            self._inner = inner

        def get_correlation_id(self) -> str:  # type: ignore[override]
            return self._inner.get_correlation_id()

    use_case = SyncAcquiringStatusUseCase(
        uow=uow,
        bank_api=bank_client,
        correlation_id_provider=_CorrelationAdapter(correlation),
    )

    cmd = SyncAcquiringStatusCommand(
        order_id=str(order_id.value),
        payment_id=str(payment_id.value),
    )

    dto = await use_case.execute(cmd)

    assert dto.status == PaymentStatus.COMPLETED
