from __future__ import annotations

import logging
import logging.handlers
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import structlog

from infrastructure.logging.correlation import get_correlation_id
from presentation.settings import settings

LOGS_DIR = Path(settings.logs_dir)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _add_correlation_id(
    logger: object, method: str, event_dict: dict[str, object]
) -> dict[str, object]:
    """Inject correlation_id into every log record."""
    cid = get_correlation_id()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def _configure_logging() -> None:
    """
    Wire structlog to Python stdlib logging so that:
    - uvicorn / sqlalchemy / alembic logs also go through structlog
    - All records are written as JSON to both stdout and a rotating file
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_correlation_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        filename=LOGS_DIR / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)

    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


_configure_logging()


from fastapi import FastAPI  # noqa: E402

from presentation.api.routes import router as payments_router  # noqa: E402

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app.startup", logs_dir=str(LOGS_DIR))
    from infrastructure.persistence.seed import seed_orders

    await seed_orders()
    logger.info("app.ready")
    yield
    logger.info("app.shutdown")


app = FastAPI(
    title="Payment Order Service",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(payments_router)
