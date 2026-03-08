from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from application.ports.bank_api import (
    AbstractBankApiClient,
    BankApiError,
    BankApiUnavailableError,
    BankPaymentInfo,
)
from domain.value_objects.enums import BankPaymentStatus
from domain.value_objects.money import Money

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class HttpBankApiClient(AbstractBankApiClient):
    """HTTP implementation of AbstractBankApiClient using httpx."""

    base_url: str
    timeout_seconds: float = 5.0
    max_retries: int = 3

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None,
        correlation_id: str,
    ) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {"X-Correlation-ID": correlation_id}

        async def send() -> dict[str, Any]:
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.request(method, url, json=json, headers=headers)
            except httpx.RequestError as exc:
                logger.error(
                    "bank_api.http_error",
                    error=str(exc),
                    url=url,
                    method=method,
                    correlation_id=correlation_id,
                )
                raise BankApiUnavailableError("Bank API request failed") from exc

            logger.info(
                "bank_api.response",
                status_code=response.status_code,
                url=url,
                method=method,
                correlation_id=correlation_id,
            )

            if response.status_code >= 500:
                raise BankApiUnavailableError(f"Bank API returned {response.status_code}")
            if response.status_code == 404:
                from application.ports.bank_api import BankPaymentNotFoundError

                raise BankPaymentNotFoundError("Bank payment not found")
            if response.status_code >= 400:
                raise BankApiError(f"Bank API returned {response.status_code}: {response.text}")

            return response.json()

        retrying = AsyncRetrying(
            retry=retry_if_exception_type(BankApiUnavailableError),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
            reraise=True,
        )

        try:
            async for attempt in retrying:
                with attempt:
                    return await send()
        except RetryError as exc:  # pragma: no cover - defensive
            raise BankApiUnavailableError("Bank API unavailable after retries") from exc

    def _parse_bank_payment_info(self, data: dict[str, Any]) -> BankPaymentInfo:
        return BankPaymentInfo(
            bank_payment_id=data["bank_payment_id"],
            status=BankPaymentStatus(data["status"]),
            amount=Money(data["amount"], data["currency"]),
        )

    async def start_acquiring(
        self,
        *,
        order_id: str,
        amount: Money,
        correlation_id: str,
    ) -> str:
        payload = {
            "order_id": order_id,
            "amount": str(amount.amount),
            "currency": amount.currency,
        }
        logger.info(
            "bank_api.start_acquiring",
            order_id=order_id,
            amount=str(amount.amount),
            currency=amount.currency,
            correlation_id=correlation_id,
        )
        data = await self._request(
            "POST",
            "/acquiring_start",
            json=payload,
            correlation_id=correlation_id,
        )
        return data["bank_payment_id"]

    async def check_payment(
        self,
        *,
        bank_payment_id: str,
        correlation_id: str,
    ) -> BankPaymentInfo:
        logger.info(
            "bank_api.check_payment",
            bank_payment_id=bank_payment_id,
            correlation_id=correlation_id,
        )
        data = await self._request(
            "POST",
            "/acquiring_check",
            json={"bank_payment_id": bank_payment_id},
            correlation_id=correlation_id,
        )
        return self._parse_bank_payment_info(data)
