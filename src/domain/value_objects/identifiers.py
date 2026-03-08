from __future__ import annotations

from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class BaseId:
    """Base class for all strongly typed identifiers."""

    value: UUID

    @classmethod
    def new(cls) -> Self:
        return cls(uuid4())

    @classmethod
    def from_string(cls, raw: str) -> Self:
        return cls(UUID(raw))

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class OrderId(BaseId):
    """Strongly typed identifier for orders."""


@dataclass(frozen=True, slots=True)
class PaymentId(BaseId):
    """Strongly typed identifier for payments."""
