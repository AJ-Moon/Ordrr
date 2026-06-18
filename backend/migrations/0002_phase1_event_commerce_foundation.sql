ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS currency varchar(3) NOT NULL DEFAULT 'USD';
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS price_cents bigint;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS sale_price_cents bigint;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS ingredient_cost_cents bigint;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS packaging_cost_cents bigint NOT NULL DEFAULT 0;

UPDATE menu_items
SET price_cents = round(price * 100)::bigint
WHERE price_cents IS NULL;
UPDATE menu_items
SET sale_price_cents = round(sale_price * 100)::bigint
WHERE sale_price IS NOT NULL AND sale_price_cents IS NULL;
ALTER TABLE menu_items ALTER COLUMN price_cents SET NOT NULL;
ALTER TABLE menu_items ADD CONSTRAINT menu_items_price_cents_nonnegative CHECK (price_cents >= 0) NOT VALID;
ALTER TABLE menu_items ADD CONSTRAINT menu_items_sale_price_cents_nonnegative CHECK (sale_price_cents IS NULL OR sale_price_cents >= 0) NOT VALID;
ALTER TABLE menu_items ADD CONSTRAINT menu_items_cost_cents_nonnegative CHECK (ingredient_cost_cents IS NULL OR ingredient_cost_cents >= 0) NOT VALID;

ALTER TABLE orders ADD COLUMN IF NOT EXISTS currency varchar(3) NOT NULL DEFAULT 'USD';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS subtotal_cents bigint;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount_cents bigint;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_charge_cents bigint;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS tax_cents bigint NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refund_cents bigint NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_cost_cents bigint NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS commission_cents bigint NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS packaging_cost_cents bigint NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS ingredient_cost_cents bigint NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS contribution_margin_cents bigint;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_cents bigint;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS cart_id text;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS visitor_id varchar(100);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS session_id varchar(100);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS completed_at timestamptz;

UPDATE orders
SET subtotal_cents = round(subtotal * 100)::bigint,
    discount_cents = round(discount_amount * 100)::bigint,
    delivery_charge_cents = round(delivery_charge * 100)::bigint,
    total_cents = round(total * 100)::bigint
WHERE subtotal_cents IS NULL OR discount_cents IS NULL
   OR delivery_charge_cents IS NULL OR total_cents IS NULL;

CREATE TABLE IF NOT EXISTS carts (
    id text PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    visitor_id varchar(100) NOT NULL,
    session_id varchar(100) NOT NULL,
    customer_id text REFERENCES customers(id) ON DELETE SET NULL,
    user_id text,
    currency varchar(3) NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'converted', 'abandoned', 'expired')),
    subtotal_cents bigint NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    converted_at timestamptz,
    UNIQUE (tenant_id, id)
);
CREATE INDEX IF NOT EXISTS idx_carts_tenant_status_updated
    ON carts (tenant_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_carts_visitor
    ON carts (tenant_id, visitor_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS cart_lines (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    cart_id text NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
    menu_item_id integer NOT NULL REFERENCES menu_items(id),
    quantity integer NOT NULL CHECK (quantity > 0 AND quantity <= 99),
    unit_price_cents bigint NOT NULL CHECK (unit_price_cents >= 0),
    line_total_cents bigint NOT NULL CHECK (line_total_cents >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, cart_id, menu_item_id)
);
CREATE INDEX IF NOT EXISTS idx_cart_lines_cart ON cart_lines (tenant_id, cart_id);

-- Named order_line_items (not order_items) because this database already
-- contains an unrelated legacy order_items table (uuid-keyed, references
-- items(id)) from a different schema sharing this Supabase project.
CREATE TABLE IF NOT EXISTS order_line_items (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    order_id varchar(20) NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id integer REFERENCES menu_items(id) ON DELETE SET NULL,
    item_name varchar(200) NOT NULL,
    category_name varchar(100) NOT NULL DEFAULT '',
    quantity integer NOT NULL CHECK (quantity > 0),
    currency varchar(3) NOT NULL,
    gross_unit_price_cents bigint NOT NULL,
    discount_cents bigint NOT NULL DEFAULT 0,
    net_unit_price_cents bigint NOT NULL,
    ingredient_cost_cents bigint,
    packaging_cost_cents bigint NOT NULL DEFAULT 0,
    line_revenue_cents bigint NOT NULL,
    line_contribution_margin_cents bigint,
    snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_order_line_items_order ON order_line_items (tenant_id, order_id);
CREATE INDEX IF NOT EXISTS idx_order_line_items_item_created ON order_line_items (tenant_id, menu_item_id, created_at DESC);

CREATE TABLE IF NOT EXISTS analytics_events (
    id bigserial PRIMARY KEY,
    event_id varchar(100) NOT NULL,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    location_id integer REFERENCES branches(id) ON DELETE SET NULL,
    visitor_id varchar(100) NOT NULL,
    session_id varchar(100) NOT NULL,
    customer_id text REFERENCES customers(id) ON DELETE SET NULL,
    event_name varchar(100) NOT NULL,
    occurred_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    page_path text,
    referrer text,
    source varchar(160),
    medium varchar(160),
    campaign varchar(240),
    content varchar(240),
    term varchar(240),
    click_id varchar(240),
    item_id integer REFERENCES menu_items(id) ON DELETE SET NULL,
    category_id text,
    cart_id text,
    order_id varchar(20),
    experiment_id text,
    variant_id text,
    mission_id text,
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    schema_version integer NOT NULL DEFAULT 1,
    is_server_event boolean NOT NULL DEFAULT false,
    consent_state varchar(30) NOT NULL DEFAULT 'unknown',
    UNIQUE (tenant_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_events_tenant_occurred ON analytics_events (tenant_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_tenant_name_occurred ON analytics_events (tenant_id, event_name, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_session ON analytics_events (tenant_id, session_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_item ON analytics_events (tenant_id, item_id, occurred_at DESC) WHERE item_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_cart ON analytics_events (tenant_id, cart_id, occurred_at DESC) WHERE cart_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_order ON analytics_events (tenant_id, order_id, occurred_at DESC) WHERE order_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS event_ingestion_windows (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    window_start timestamptz NOT NULL,
    event_count integer NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, window_start)
);

CREATE TABLE IF NOT EXISTS communication_frequency_limits (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    channel varchar(24) NOT NULL CHECK (channel IN ('email', 'sms', 'whatsapp', 'push')),
    max_messages integer NOT NULL CHECK (max_messages > 0),
    window_hours integer NOT NULL CHECK (window_hours > 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, channel)
);

INSERT INTO communication_frequency_limits (tenant_id, channel, max_messages, window_hours)
SELECT id, channel, max_messages, window_hours
FROM restaurants
CROSS JOIN (VALUES
    ('email', 3, 168),
    ('sms', 2, 168),
    ('whatsapp', 2, 168),
    ('push', 5, 168)
) defaults(channel, max_messages, window_hours)
ON CONFLICT (tenant_id, channel) DO NOTHING;

CREATE TABLE IF NOT EXISTS job_runs (
    id bigserial PRIMARY KEY,
    tenant_id integer REFERENCES restaurants(id) ON DELETE CASCADE,
    job_name varchar(160) NOT NULL,
    idempotency_key varchar(240) NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    run_after timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    attempt integer NOT NULL DEFAULT 0,
    max_attempts integer NOT NULL DEFAULT 3,
    error_code varchar(100),
    error_message text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (job_name, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_job_runs_queue
    ON job_runs (status, run_after, created_at) WHERE status IN ('queued', 'failed');
CREATE INDEX IF NOT EXISTS idx_job_runs_tenant_created
    ON job_runs (tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS daily_item_metrics (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    metric_date date NOT NULL,
    location_id integer,
    item_id integer NOT NULL,
    impressions bigint NOT NULL DEFAULT 0,
    detail_views bigint NOT NULL DEFAULT 0,
    add_to_carts bigint NOT NULL DEFAULT 0,
    orders bigint NOT NULL DEFAULT 0,
    quantity_sold bigint NOT NULL DEFAULT 0,
    revenue_cents bigint NOT NULL DEFAULT 0,
    contribution_margin_cents bigint,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, metric_date, location_id, item_id)
);

CREATE TABLE IF NOT EXISTS daily_funnel_metrics (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    metric_date date NOT NULL,
    location_id integer,
    sessions bigint NOT NULL DEFAULT 0,
    menu_sessions bigint NOT NULL DEFAULT 0,
    cart_sessions bigint NOT NULL DEFAULT 0,
    checkout_sessions bigint NOT NULL DEFAULT 0,
    ordering_sessions bigint NOT NULL DEFAULT 0,
    completed_orders bigint NOT NULL DEFAULT 0,
    revenue_cents bigint NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, metric_date, location_id)
);

CREATE TABLE IF NOT EXISTS daily_search_metrics (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    metric_date date NOT NULL,
    normalized_query text NOT NULL,
    searches bigint NOT NULL DEFAULT 0,
    zero_result_searches bigint NOT NULL DEFAULT 0,
    clicks bigint NOT NULL DEFAULT 0,
    add_to_carts bigint NOT NULL DEFAULT 0,
    orders bigint NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, metric_date, normalized_query)
);

CREATE TABLE IF NOT EXISTS daily_checkout_metrics (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    metric_date date NOT NULL,
    step varchar(80) NOT NULL,
    entered bigint NOT NULL DEFAULT 0,
    completed bigint NOT NULL DEFAULT 0,
    failures bigint NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, metric_date, step)
);

CREATE TABLE IF NOT EXISTS daily_source_metrics (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    metric_date date NOT NULL,
    source varchar(160) NOT NULL DEFAULT '(direct)',
    medium varchar(160) NOT NULL DEFAULT '(none)',
    campaign varchar(240) NOT NULL DEFAULT '',
    sessions bigint NOT NULL DEFAULT 0,
    orders bigint NOT NULL DEFAULT 0,
    revenue_cents bigint NOT NULL DEFAULT 0,
    contribution_margin_cents bigint,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, metric_date, source, medium, campaign)
);

CREATE TABLE IF NOT EXISTS daily_chat_metrics (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    metric_date date NOT NULL,
    intent varchar(80) NOT NULL,
    messages bigint NOT NULL DEFAULT 0,
    recommendations bigint NOT NULL DEFAULT 0,
    clicks bigint NOT NULL DEFAULT 0,
    orders bigint NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, metric_date, intent)
);

CREATE TABLE IF NOT EXISTS daily_customer_metrics (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    metric_date date NOT NULL,
    segment varchar(80) NOT NULL,
    customers bigint NOT NULL DEFAULT 0,
    orders bigint NOT NULL DEFAULT 0,
    revenue_cents bigint NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, metric_date, segment)
);

CREATE TABLE IF NOT EXISTS basket_associations (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    window_start date NOT NULL,
    window_end date NOT NULL,
    item_a_id integer NOT NULL,
    item_b_id integer NOT NULL,
    pair_orders bigint NOT NULL DEFAULT 0,
    support numeric(12,8),
    confidence numeric(12,8),
    lift numeric(12,8),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, window_start, window_end, item_a_id, item_b_id),
    CHECK (item_a_id < item_b_id)
);

CREATE TABLE IF NOT EXISTS data_quality_checks (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    check_key varchar(120) NOT NULL,
    status varchar(20) NOT NULL CHECK (status IN ('ok', 'warning', 'error')),
    affected_count bigint NOT NULL DEFAULT 0,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    checked_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, check_key)
);

INSERT INTO job_runs (tenant_id, job_name, idempotency_key, metadata)
SELECT id, 'analytics.aggregate_daily', 'phase1-initial-' || id, '{"reason":"phase1_backfill"}'::jsonb
FROM restaurants
ON CONFLICT (job_name, idempotency_key) DO NOTHING;
