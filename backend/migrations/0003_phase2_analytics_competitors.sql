CREATE TABLE IF NOT EXISTS competitors (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name varchar(200) NOT NULL,
    website text,
    address text,
    notes text,
    currency varchar(3) NOT NULL DEFAULT 'USD',
    reference_item_name varchar(200),
    reference_price_cents bigint CHECK (reference_price_cents IS NULL OR reference_price_cents >= 0),
    observed_at timestamptz,
    status varchar(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    verified_at timestamptz,
    verified_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);
CREATE INDEX IF NOT EXISTS idx_competitors_tenant_status ON competitors (tenant_id, status);

-- Support efficient new-vs-returning customer classification in
-- analytics.aggregate_daily (Phase 2 daily_customer_metrics).
CREATE INDEX IF NOT EXISTS idx_orders_tenant_visitor_created
    ON orders (restaurant_id, visitor_id, created_at) WHERE visitor_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_tenant_user_created
    ON orders (restaurant_id, user_id, created_at) WHERE user_id IS NOT NULL;
