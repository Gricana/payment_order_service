from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from domain.value_objects.enums import PaymentStatus, PaymentType


class CreatePaymentRequest(BaseModel):
    amount: str = Field(..., description="Payment amount as decimal string")
    currency: str = Field(..., min_length=3, max_length=3)
    payment_type: PaymentType
    idempotency_key: str | None = Field(
        default=None,
        description="Idempotency key to protect against duplicate payments",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "amount": "100.00",
                "currency": "USD",
                "payment_type": "cash",
                "idempotency_key": "order-123-payment-1",
            }
        }
    }


class RefundPaymentRequest(BaseModel):
    amount: str
    currency: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "amount": "10.00",
                "currency": "USD",
            }
        }
    }


class PaymentResponse(BaseModel):
    id: UUID
    order_id: UUID
    payment_type: PaymentType
    amount: str
    currency: str
    status: PaymentStatus
    created_at: datetime
    refunded_amount: str


class PaymentsListResponse(BaseModel):
    items: list[PaymentResponse]
