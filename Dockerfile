FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

FROM python:3.11-slim AS production
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY src/ ./src/
COPY alembic.ini .
COPY alembic/ ./alembic/

ENV PYTHONPATH=/app/src

RUN adduser --disabled-password --gecos "" appuser && \
    mkdir -p /app/logs && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "presentation.main:app", "--host", "0.0.0.0", "--port", "8000"]

