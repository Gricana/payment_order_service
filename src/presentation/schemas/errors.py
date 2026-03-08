from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Стандартная схема ошибки API."""

    detail: str = Field(..., description="Текстовое описание ошибки")
