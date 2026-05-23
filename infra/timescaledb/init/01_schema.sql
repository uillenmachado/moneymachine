-- Inicialização do schema do TimescaleDB
-- Executado uma única vez na primeira subida do container.

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- ─────────── Tabelas transacionais (PostgreSQL puro) ───────────

CREATE TABLE IF NOT EXISTS orders (
    id              BIGSERIAL PRIMARY KEY,
    client_order_id TEXT NOT NULL UNIQUE,
    exchange_order_id TEXT,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type      TEXT NOT NULL,
    price           NUMERIC(20, 10),
    quantity        NUMERIC(20, 10) NOT NULL,
    filled_qty      NUMERIC(20, 10) NOT NULL DEFAULT 0,
    status          TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_orders_symbol_created ON orders(symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status) WHERE status IN ('OPEN', 'PARTIALLY_FILLED');

CREATE TABLE IF NOT EXISTS fills (
    id              BIGSERIAL PRIMARY KEY,
    order_id        BIGINT NOT NULL REFERENCES orders(id),
    trade_id        TEXT NOT NULL,
    price           NUMERIC(20, 10) NOT NULL,
    quantity        NUMERIC(20, 10) NOT NULL,
    fee             NUMERIC(20, 10) NOT NULL DEFAULT 0,
    fee_currency    TEXT,
    is_maker        BOOLEAN NOT NULL,
    executed_at     TIMESTAMPTZ NOT NULL,
    UNIQUE(order_id, trade_id)
);
CREATE INDEX IF NOT EXISTS idx_fills_executed ON fills(executed_at DESC);

CREATE TABLE IF NOT EXISTS risk_events (
    id              BIGSERIAL PRIMARY KEY,
    event_type      TEXT NOT NULL,
    severity        TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
    message         TEXT NOT NULL,
    metadata        JSONB,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_risk_severity_time ON risk_events(severity, occurred_at DESC);

-- ─────────── Tabelas de séries temporais (TimescaleDB hypertables) ───────────

CREATE TABLE IF NOT EXISTS book_snapshots (
    ts              TIMESTAMPTZ NOT NULL,
    symbol          TEXT NOT NULL,
    bids            JSONB NOT NULL,  -- [[price, qty], ...] top N levels
    asks            JSONB NOT NULL,
    sequence        BIGINT
);
SELECT create_hypertable('book_snapshots', 'ts', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 hour');
CREATE INDEX IF NOT EXISTS idx_book_symbol_ts ON book_snapshots(symbol, ts DESC);

CREATE TABLE IF NOT EXISTS trades_tape (
    ts              TIMESTAMPTZ NOT NULL,
    symbol          TEXT NOT NULL,
    price           NUMERIC(20, 10) NOT NULL,
    quantity        NUMERIC(20, 10) NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    trade_id        TEXT
);
SELECT create_hypertable('trades_tape', 'ts', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 hour');
CREATE INDEX IF NOT EXISTS idx_tape_symbol_ts ON trades_tape(symbol, ts DESC);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    ts              TIMESTAMPTZ NOT NULL,
    equity_usd      NUMERIC(20, 10) NOT NULL,
    realized_pnl    NUMERIC(20, 10) NOT NULL,
    unrealized_pnl  NUMERIC(20, 10) NOT NULL,
    inventory       JSONB NOT NULL  -- {symbol: qty}
);
SELECT create_hypertable('equity_snapshots', 'ts', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');

-- Retenção: ticks após 90 dias podem ser agregados/descartados (configurar na Fase 4)
-- SELECT add_retention_policy('book_snapshots', INTERVAL '90 days', if_not_exists => TRUE);
