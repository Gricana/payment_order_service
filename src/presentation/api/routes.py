from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from application.dto.payment import PaymentDTO
from application.ports.bank_api import (
    BankApiError,
    BankApiUnavailableError,
    BankPaymentNotFoundError,
)
from application.use_cases.create_payment import CreatePaymentCommand, CreatePaymentUseCase
from application.use_cases.refund_payment import RefundPaymentCommand, RefundPaymentUseCase
from domain.exceptions import (
    CurrencyMismatchError,
    InsufficientFundsError,
    OrderAlreadyPaidError,
    OrderNotFoundError,
    PaymentNotFoundError,
)
from infrastructure.logging.correlation import set_correlation_id
from presentation.dependencies import get_create_payment_use_case, get_refund_payment_use_case
from presentation.schemas.errors import ErrorResponse
from presentation.schemas.payment import (
    CreatePaymentRequest,
    PaymentResponse,
    RefundPaymentRequest,
)

router = APIRouter(prefix="/api/v1", tags=["payments"])


def payment_response_from_dto(dto: PaymentDTO) -> PaymentResponse:
    return PaymentResponse(
        id=dto.id,
        order_id=dto.order_id,
        payment_type=dto.payment_type,
        amount=dto.amount,
        currency=dto.currency,
        status=dto.status,
        created_at=dto.created_at,
        refunded_amount=dto.refunded_amount,
    )


@router.post(
    "/orders/{order_id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать платеж по заказу",
    description="Создает новый платеж (наличные или эквайринг) для указанного заказа.",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Ошибка валидации или превышена сумма заказа",
        },
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Заказ не найден"},
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Заказ уже полностью оплачен",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "model": ErrorResponse,
            "description": "Ошибка при обращении к API банка",
        },
    },
)
async def create_payment(
    order_id: UUID,
    body: CreatePaymentRequest,
    use_case: CreatePaymentUseCase = Depends(get_create_payment_use_case),
) -> PaymentResponse:
    set_correlation_id()  # ensure correlation id exists for this request
    try:
        dto = await use_case.execute(
            CreatePaymentCommand(
                order_id=str(order_id),
                amount=body.amount,
                currency=body.currency,
                payment_type=body.payment_type,
                idempotency_key=body.idempotency_key,
            )
        )
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except OrderAlreadyPaidError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (InsufficientFundsError, CurrencyMismatchError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except BankPaymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except (BankApiUnavailableError, BankApiError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Bank API error"
        ) from exc

    return payment_response_from_dto(dto)


@router.post(
    "/orders/{order_id}/payments/{payment_id}/refund",
    response_model=PaymentResponse,
    summary="Сделать возврат по платежу",
    description="Выполняет возврат части или всей суммы по ранее созданному платежу.",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Сумма возврата некорректна или превышает оплаченный остаток",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Заказ или платеж не найдены",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "model": ErrorResponse,
            "description": "Ошибка при обращении к API банка",
        },
    },
)
async def refund_payment(
    order_id: UUID,
    payment_id: UUID,
    body: RefundPaymentRequest,
    use_case: RefundPaymentUseCase = Depends(get_refund_payment_use_case),
) -> PaymentResponse:
    set_correlation_id()
    try:
        dto = await use_case.execute(
            RefundPaymentCommand(
                order_id=str(order_id),
                payment_id=str(payment_id),
                amount=body.amount,
                currency=body.currency,
            )
        )
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (InsufficientFundsError, CurrencyMismatchError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except BankPaymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except (BankApiUnavailableError, BankApiError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Bank API error"
        ) from exc

    return payment_response_from_dto(dto)
