-- Enum types
CREATE TYPE order_payment_status AS ENUM (
    'unpaid',
    'partially_paid',
    'paid'
);

CREATE TYPE payment_type AS ENUM (
    'cash',
    'acquiring'
);

CREATE TYPE payment_status AS ENUM (
    'pending',
    'completed',
    'refunded',
    'failed'
);

CREATE TYPE bank_payment_status AS ENUM (
    'pending',
    'authorized',
    'captured',
    'failed',
    'cancelled',
    'refunded'
);

CREATE TABLE orders (
    id              UUID                    PRIMARY KEY,
    total_amount    NUMERIC(10, 2)          NOT NULL,
    currency        VARCHAR(3)              NOT NULL,
    payment_status  order_payment_status    NOT NULL DEFAULT 'unpaid',
    created_at      TIMESTAMPTZ             NOT NULL,
    updated_at      TIMESTAMPTZ             NOT NULL
);

CREATE TABLE payments (
    id                   UUID            PRIMARY KEY,
    order_id             UUID            NOT NULL
        REFERENCES orders(id) ON DELETE CASCADE,
    payment_type         payment_type    NOT NULL,
    amount               NUMERIC(10, 2)  NOT NULL,
    currency             VARCHAR(3)      NOT NULL,
    status               payment_status  NOT NULL DEFAULT 'pending',
    refunded_amount      NUMERIC(10, 2)  NULL,  
    client_reference_id  VARCHAR(128)    NULL,    
    created_at           TIMESTAMPTZ     NOT NULL,
    updated_at           TIMESTAMPTZ     NOT NULL
);

CREATE INDEX idx_payments_order_id
    ON payments(order_id);

CREATE INDEX idx_payments_client_reference_id
    ON payments(client_reference_id)
    WHERE client_reference_id IS NOT NULL;

CREATE TABLE acquiring_details (
    id               UUID                 PRIMARY KEY,
    payment_id       UUID                 NOT NULL UNIQUE
        REFERENCES payments(id) ON DELETE CASCADE,
    bank_payment_id  VARCHAR(64)          NOT NULL UNIQUE,
    bank_status      bank_payment_status  NOT NULL DEFAULT 'pending',
    bank_paid_at     TIMESTAMPTZ          NULL,
    last_synced_at   TIMESTAMPTZ          NULL
);

CREATE INDEX idx_acquiring_details_bank_payment_id
    ON acquiring_details(bank_payment_id);