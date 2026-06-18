INSERT INTO feature_definitions (feature_key, description, default_enabled)
VALUES
    ('conversion.order_architect', 'AI Order Architect recommendations', false),
    ('conversion.private_offers', 'Private offers and personalized merchandising', false),
    ('conversion.demand_twin', 'Tenant Demand Twin first-party snapshot', false),
    ('integrations.production_messaging', 'Production email/SMS/WhatsApp integrations', false),
    ('integrations.advertising', 'Advertising integration scaffolding', false),
    ('platform.performance_reviews', 'Queue, partition, and pooling performance reviews', false)
ON CONFLICT (feature_key) DO NOTHING;

INSERT INTO plan_entitlements (plan_id, feature_key, enabled)
SELECT p.id, f.feature_key, true
FROM plans p
CROSS JOIN (VALUES
    ('conversion.order_architect'),
    ('conversion.private_offers'),
    ('conversion.demand_twin'),
    ('network.neighborhood_benchmarks'),
    ('integrations.production_messaging'),
    ('integrations.advertising'),
    ('platform.performance_reviews')
) AS f(feature_key)
WHERE p.plan_key = 'legacy'
ON CONFLICT (plan_id, feature_key) DO UPDATE SET enabled = EXCLUDED.enabled;

CREATE TABLE IF NOT EXISTS order_architect_requests (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    visitor_id varchar(120),
    session_id varchar(120),
    customer_id text REFERENCES customers(id) ON DELETE SET NULL,
    budget_cents bigint CHECK (budget_cents IS NULL OR budget_cents >= 0),
    party_size integer NOT NULL DEFAULT 1 CHECK (party_size BETWEEN 1 AND 30),
    dietary_constraints jsonb NOT NULL DEFAULT '[]'::jsonb,
    excluded_ingredients jsonb NOT NULL DEFAULT '[]'::jsonb,
    preferences jsonb NOT NULL DEFAULT '{}'::jsonb,
    provider varchar(40) NOT NULL DEFAULT 'deterministic',
    status varchar(30) NOT NULL DEFAULT 'COMPLETED' CHECK (status IN ('COMPLETED','NO_MATCH','FAILED')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_order_architect_requests_tenant
    ON order_architect_requests (tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS order_architect_suggestions (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    request_id bigint NOT NULL REFERENCES order_architect_requests(id) ON DELETE CASCADE,
    cart_id varchar(120),
    items jsonb NOT NULL DEFAULT '[]'::jsonb,
    subtotal_cents bigint NOT NULL DEFAULT 0 CHECK (subtotal_cents >= 0),
    estimated_margin_cents bigint,
    explanation text NOT NULL,
    constraints_satisfied jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS private_offers (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    code varchar(80) NOT NULL,
    title varchar(160) NOT NULL,
    description text NOT NULL,
    target_segment varchar(80),
    customer_id text REFERENCES customers(id) ON DELETE SET NULL,
    visitor_id varchar(120),
    discount_type varchar(30) NOT NULL CHECK (discount_type IN ('PERCENT','FIXED')),
    discount_value integer NOT NULL CHECK (discount_value > 0),
    max_discount_cents bigint CHECK (max_discount_cents IS NULL OR max_discount_cents >= 0),
    minimum_subtotal_cents bigint NOT NULL DEFAULT 0 CHECK (minimum_subtotal_cents >= 0),
    minimum_margin_cents bigint NOT NULL DEFAULT 0,
    max_redemptions integer CHECK (max_redemptions IS NULL OR max_redemptions > 0),
    starts_at timestamptz,
    ends_at timestamptz,
    status varchar(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','APPROVED','RUNNING','PAUSED','COMPLETED','CANCELLED')),
    rules jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, code),
    CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at)
);
CREATE INDEX IF NOT EXISTS idx_private_offers_active
    ON private_offers (tenant_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS private_offer_redemptions (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    offer_id bigint NOT NULL REFERENCES private_offers(id) ON DELETE CASCADE,
    order_id varchar(20) REFERENCES orders(id) ON DELETE SET NULL,
    cart_id varchar(120),
    visitor_id varchar(120),
    customer_id text REFERENCES customers(id) ON DELETE SET NULL,
    subtotal_cents bigint NOT NULL DEFAULT 0,
    discount_cents bigint NOT NULL DEFAULT 0,
    contribution_margin_after_discount_cents bigint,
    status varchar(30) NOT NULL DEFAULT 'RESERVED' CHECK (status IN ('RESERVED','REDEEMED','REJECTED','EXPIRED')),
    reason varchar(160),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_private_offer_redemptions_offer
    ON private_offer_redemptions (tenant_id, offer_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS merchandising_events (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    event_key varchar(180) NOT NULL,
    visitor_id varchar(120),
    session_id varchar(120),
    customer_id text REFERENCES customers(id) ON DELETE SET NULL,
    placement varchar(80) NOT NULL,
    item_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    offer_id bigint REFERENCES private_offers(id) ON DELETE SET NULL,
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, event_key)
);

CREATE TABLE IF NOT EXISTS tenant_demand_twins (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    snapshot_date date NOT NULL,
    window_start date NOT NULL,
    window_end date NOT NULL,
    privacy_threshold integer NOT NULL DEFAULT 5,
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    segments jsonb NOT NULL DEFAULT '{}'::jsonb,
    menu_insights jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_mix jsonb NOT NULL DEFAULT '{}'::jsonb,
    generated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_tenant_demand_twins_latest
    ON tenant_demand_twins (tenant_id, snapshot_date DESC);

CREATE TABLE IF NOT EXISTS neighborhood_benchmark_snapshots (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    benchmark_date date NOT NULL,
    neighborhood_key varchar(160) NOT NULL,
    privacy_threshold integer NOT NULL DEFAULT 5,
    peer_count integer NOT NULL DEFAULT 0,
    status varchar(30) NOT NULL CHECK (status IN ('READY','INSUFFICIENT_PEERS')),
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    generated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, benchmark_date, neighborhood_key)
);
CREATE INDEX IF NOT EXISTS idx_neighborhood_benchmarks_latest
    ON neighborhood_benchmark_snapshots (tenant_id, benchmark_date DESC);

CREATE TABLE IF NOT EXISTS integration_accounts (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    provider varchar(80) NOT NULL,
    integration_type varchar(40) NOT NULL CHECK (integration_type IN ('MESSAGING','ADVERTISING')),
    channel varchar(40),
    status varchar(30) NOT NULL DEFAULT 'DISABLED' CHECK (status IN ('DISABLED','CONFIGURED','FAILED')),
    secret_reference varchar(200),
    settings jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_checked_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_integration_accounts_unique_channel
    ON integration_accounts (tenant_id, provider, integration_type, COALESCE(channel, ''));

CREATE TABLE IF NOT EXISTS queue_health_snapshots (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    snapshot_at timestamptz NOT NULL DEFAULT now(),
    pending_jobs integer NOT NULL DEFAULT 0,
    running_jobs integer NOT NULL DEFAULT 0,
    failed_jobs_24h integer NOT NULL DEFAULT 0,
    average_latency_seconds numeric(12,2),
    details jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_queue_health_latest
    ON queue_health_snapshots (tenant_id, snapshot_at DESC);

CREATE TABLE IF NOT EXISTS performance_reviews (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    reviewed_at timestamptz NOT NULL DEFAULT now(),
    database_pooling jsonb NOT NULL DEFAULT '{}'::jsonb,
    queue_throughput jsonb NOT NULL DEFAULT '{}'::jsonb,
    partition_recommendations jsonb NOT NULL DEFAULT '[]'::jsonb,
    status varchar(30) NOT NULL DEFAULT 'RECORDED' CHECK (status IN ('RECORDED','ATTENTION_REQUIRED')),
    UNIQUE (tenant_id, reviewed_at)
);

CREATE INDEX IF NOT EXISTS idx_analytics_events_tenant_occurred_phase8
    ON analytics_events (tenant_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_tenant_completed_phase8
    ON orders (restaurant_id, completed_at DESC)
    WHERE status = 'delivered';
CREATE INDEX IF NOT EXISTS idx_job_runs_tenant_status_phase8
    ON job_runs (tenant_id, status, updated_at DESC);
