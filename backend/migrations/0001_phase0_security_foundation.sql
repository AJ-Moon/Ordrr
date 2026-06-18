CREATE TABLE IF NOT EXISTS schema_migrations (
    version varchar(255) PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS timezone varchar(64) NOT NULL DEFAULT 'UTC';
ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS currency varchar(3) NOT NULL DEFAULT 'USD';

CREATE TABLE IF NOT EXISTS feature_definitions (
    feature_key varchar(120) PRIMARY KEY,
    description text NOT NULL DEFAULT '',
    default_enabled boolean NOT NULL DEFAULT false,
    default_limit integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS plans (
    id bigserial PRIMARY KEY,
    plan_key varchar(80) NOT NULL UNIQUE,
    name varchar(160) NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS plan_entitlements (
    plan_id bigint NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    feature_key varchar(120) NOT NULL REFERENCES feature_definitions(feature_key) ON DELETE CASCADE,
    enabled boolean NOT NULL DEFAULT false,
    limit_value integer,
    PRIMARY KEY (plan_id, feature_key)
);

CREATE TABLE IF NOT EXISTS tenant_plans (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    plan_id bigint NOT NULL REFERENCES plans(id),
    starts_at date NOT NULL DEFAULT CURRENT_DATE,
    ends_at date,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, starts_at),
    CHECK (ends_at IS NULL OR ends_at >= starts_at)
);

CREATE TABLE IF NOT EXISTS tenant_feature_overrides (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    feature_key varchar(120) NOT NULL REFERENCES feature_definitions(feature_key) ON DELETE CASCADE,
    enabled boolean NOT NULL,
    limit_value integer,
    reason text NOT NULL DEFAULT '',
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, feature_key)
);

CREATE TABLE IF NOT EXISTS feature_usage (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    feature_key varchar(120) NOT NULL REFERENCES feature_definitions(feature_key) ON DELETE CASCADE,
    period_start date NOT NULL,
    amount bigint NOT NULL DEFAULT 0 CHECK (amount >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, feature_key, period_start)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id bigserial PRIMARY KEY,
    tenant_id integer REFERENCES restaurants(id) ON DELETE SET NULL,
    actor_type varchar(40) NOT NULL,
    actor_id text,
    action varchar(120) NOT NULL,
    resource_type varchar(120) NOT NULL,
    resource_id text,
    before_data jsonb NOT NULL DEFAULT '{}'::jsonb,
    after_data jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_created
    ON audit_logs (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource
    ON audit_logs (tenant_id, resource_type, resource_id);

CREATE TABLE IF NOT EXISTS customers (
    id text PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    user_id text,
    email varchar(255),
    phone varchar(50),
    first_name varchar(100) NOT NULL DEFAULT '',
    last_name varchar(100) NOT NULL DEFAULT '',
    anonymized_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_customers_tenant_email ON customers (tenant_id, lower(email));

CREATE TABLE IF NOT EXISTS customer_identities (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    customer_id text NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    identity_type varchar(40) NOT NULL,
    identity_hash varchar(128) NOT NULL,
    display_hint varchar(100) NOT NULL DEFAULT '',
    verified_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, identity_type, identity_hash)
);

CREATE TABLE IF NOT EXISTS customer_consents (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    customer_id text NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    channel varchar(24) NOT NULL CHECK (channel IN ('email', 'sms', 'whatsapp', 'push')),
    status varchar(24) NOT NULL CHECK (status IN ('granted', 'denied', 'withdrawn', 'unknown')),
    source varchar(80) NOT NULL,
    policy_version varchar(40) NOT NULL,
    recorded_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, customer_id, channel)
);

CREATE TABLE IF NOT EXISTS communication_suppressions (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    customer_id text NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    channel varchar(24) NOT NULL CHECK (channel IN ('email', 'sms', 'whatsapp', 'push')),
    reason varchar(80) NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, customer_id, channel)
);

INSERT INTO feature_definitions (feature_key, description)
VALUES
    ('analytics.item_funnel', 'Item-level impression to order funnel'),
    ('analytics.menu_matrix', 'Menu opportunity classification'),
    ('analytics.search_gap', 'Search demand gap analysis'),
    ('analytics.checkout_friction', 'Checkout friction analysis'),
    ('analytics.traffic_sources', 'Traffic source and campaign attribution'),
    ('analytics.chat_objections', 'Chat objection classification'),
    ('analytics.basket', 'Basket association analysis'),
    ('analytics.competitors', 'Competitor analytics'),
    ('analytics.customer_segments', 'Customer segmentation'),
    ('opportunities.weekly_cards', 'Weekly opportunity cards'),
    ('experiments.enabled', 'Controlled experiments'),
    ('missions.abandoned_cart', 'Abandoned cart recovery mission'),
    ('missions.quiet_hour', 'Quiet-hour demand mission'),
    ('missions.bundle', 'Intelligent bundle mission'),
    ('missions.product_demand_test', 'New product demand test mission'),
    ('missions.lapsed_customer', 'Lapsed customer win-back mission'),
    ('ai.chatbot', 'AI chatbot'),
    ('ai.order_architect', 'AI order architect'),
    ('personalization.menu_sorting', 'Personalized menu sorting'),
    ('network.neighborhood_benchmarks', 'Anonymized neighborhood benchmarks')
ON CONFLICT (feature_key) DO NOTHING;

INSERT INTO plans (plan_key, name) VALUES ('legacy', 'Legacy Compatibility')
ON CONFLICT (plan_key) DO NOTHING;

INSERT INTO plan_entitlements (plan_id, feature_key, enabled)
SELECT p.id, f.feature_key, false
FROM plans p CROSS JOIN feature_definitions f
WHERE p.plan_key = 'legacy'
ON CONFLICT (plan_id, feature_key) DO NOTHING;

INSERT INTO tenant_plans (tenant_id, plan_id, starts_at)
SELECT r.id, p.id, DATE '2000-01-01'
FROM restaurants r CROSS JOIN plans p
WHERE p.plan_key = 'legacy'
ON CONFLICT (tenant_id, starts_at) DO NOTHING;
