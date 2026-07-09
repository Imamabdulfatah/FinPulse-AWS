-- File: scripts/create_tables.sql
-- DDL Script untuk membuat tabel agregasi di PostgreSQL (finpulse_db)

CREATE TABLE IF NOT EXISTS merchant_metrics_per_minute (
    metric_time TIMESTAMP NOT NULL,
    merchant_category VARCHAR(100) NOT NULL,
    total_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
    transaction_volume INT NOT NULL DEFAULT 0,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraint Primary Key diperlukan untuk fitur UPSERT (ON CONFLICT)
    PRIMARY KEY (metric_time, merchant_category)
);

-- Opsional: Index tambahan jika Dashboard Grafana sering memfilter berdasarkan kategori
CREATE INDEX IF NOT EXISTS idx_merchant_category 
ON merchant_metrics_per_minute (merchant_category);
