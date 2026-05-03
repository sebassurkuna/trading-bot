-- ============================================================
-- MT5 Bridge API — Initial Schema
-- Usage: psql -U trading_user -d trading_db -f 001_init_schema.sql
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- Table: order_map
-- Maps client order_id to MT5 broker / position ticket.
-- ============================================================
CREATE TABLE IF NOT EXISTS order_map (
    order_id        UUID PRIMARY KEY,
    broker_ticket   BIGINT,
    position_ticket BIGINT,
    status          VARCHAR(20)    NOT NULL DEFAULT 'PENDING',
    symbol          VARCHAR(20)    NOT NULL,
    action          VARCHAR(10)    NOT NULL,
    volume          DECIMAL(10, 2) NOT NULL,
    fill_price      DECIMAL(18, 6),
    sl              DECIMAL(18, 6),
    tp              DECIMAL(18, 6),
    comment         TEXT,
    magic           INTEGER,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Table: exec_reports
-- Append-only audit log of every execution event per order.
-- ============================================================
CREATE TABLE IF NOT EXISTS exec_reports (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id    UUID        NOT NULL REFERENCES order_map(order_id) ON DELETE CASCADE,
    event_type  VARCHAR(50) NOT NULL,
    data        JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_order_map_broker_ticket   ON order_map(broker_ticket);
CREATE INDEX IF NOT EXISTS idx_order_map_position_ticket ON order_map(position_ticket);
CREATE INDEX IF NOT EXISTS idx_order_map_status          ON order_map(status);
CREATE INDEX IF NOT EXISTS idx_order_map_created_at      ON order_map(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_exec_reports_order_id     ON exec_reports(order_id);
CREATE INDEX IF NOT EXISTS idx_exec_reports_created_at   ON exec_reports(created_at DESC);

-- ============================================================
-- Trigger: auto-update updated_at on order_map
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_order_map_updated_at ON order_map;
CREATE TRIGGER trg_order_map_updated_at
    BEFORE UPDATE ON order_map
    FOR EACH ROW
    EXECUTE PROCEDURE update_updated_at_column();
