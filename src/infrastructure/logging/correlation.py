from __future__ import annotations

import contextvars
import uuid

_correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def set_correlation_id(value: str | None = None) -> str:
    if value is None or not value:
        value = str(uuid.uuid4())
    _correlation_id_var.set(value)
    return value


def get_correlation_id() -> str:
    cid = _correlation_id_var.get()
    if not cid:
        cid = set_correlation_id()
    return cid


class CorrelationIdProvider:
    """Implementation of AbstractCorrelationIdProvider based on contextvars."""

    def get_correlation_id(self) -> str:
        return get_correlation_id()
