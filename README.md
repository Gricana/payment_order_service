# Payment Order Service

Сервис управления платежами по заказам: депозиты (наличные и эквайринг),
частичные/полные возвраты, синхронизация статусов с банковским API.

---

## Быстрый старт

**Требования:** Docker, Docker Compose

```bash
git clone https://github.com/Gricana/payment_order_service
cd payment-order-service
cp .env.example .env
docker-compose up --build
```

При старте автоматически применяются миграции и создаются 3 тестовых заказа.


| URL                          |            |
| ---------------------------- | ---------- |
| `http://localhost:8000/docs` | Swagger UI |


**.env.example:**

```env
DATABASE_URL=postgresql+asyncpg://payments:payments@db:5432/payments
BANK_API_BASE_URL=http://bank-api:8000
BANK_API_MODE=fake
DB_NAME=payments
DB_USER=payments
DB_PASSWORD=payments
```

`BANK_API_MODE=fake` — не делает реальных HTTP-запросов к банку,
используется для локальной разработки и тестов.

### Тесты

```bash
pytest
```

---

## Схема БД

```mermaid
erDiagram
    orders {
        UUID        id              PK
        NUMERIC     total_amount    "NOT NULL"
        VARCHAR3    currency        "NOT NULL"
        ENUM        payment_status  "unpaid | partially_paid | paid"
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    payments {
        UUID        id                   PK
        UUID        order_id             FK
        ENUM        payment_type         "cash | acquiring"
        NUMERIC     amount               "NOT NULL"
        VARCHAR3    currency             "NOT NULL"
        ENUM        status               "pending | completed | refunded | failed"
        NUMERIC     refunded_amount      "nullable"
        VARCHAR128  client_reference_id  "nullable, indexed — idempotency key"
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    acquiring_details {
        UUID        id              PK
        UUID        payment_id      FK "UNIQUE — one-to-one"
        VARCHAR64   bank_payment_id "UNIQUE, indexed"
        ENUM        bank_status     "pending | authorized | captured | failed | cancelled | refunded"
        TIMESTAMPTZ bank_paid_at    "nullable"
        TIMESTAMPTZ last_synced_at  "nullable"
    }

    orders ||--o{ payments : "has"
    payments ||--o| acquiring_details : "has"
```



---

## Архитектура

Проект построен на принципах **Clean Architecture**. Зависимости направлены строго
внутрь — каждый слой знает только о слоях внутри себя.

```
┌──────────────────────────────────────────────────┐
│                  presentation                    │
│                FastAPI · Pydantic                │
└─────────────────────┬────────────────────────────┘
                      │
┌──────────────────────────────────────────────────┐
│                  application                     │
│                Use Cases · DTO                   │
│                                                  │
│  CreatePaymentUseCase                            │
│  RefundPaymentUseCase                            │
│  SyncAcquiringStatusUseCase                      │
└─────────────────────┬────────────────────────────┘
                      │
┌──────────────────────────────────────────────────┐
│                    domain                        │
│           Entities · Value Objects               │
│                                                  │
│  Order                                           │
│  Payment                                         │
│  Money                                           │
└─────────────────────|────────────────────────────┘
                      |
┌─────────────────────┴────────────────────────────┐
│                infrastructure                    │
│         Адаптеры реализуют порты домена          │
│                                                  │
│  SqlAlchemyOrderRepository                       │
│  FakeBankApiClient                               │
│  CashProcessor · AcquiringProcessor              │          
└──────────────────────────────────────────────────┘
```

