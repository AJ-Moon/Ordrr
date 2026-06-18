-- 0011_saas_security_foundation.sql
-- Multi-tenant SaaS hardening: tenant/user lifecycle, real subscription plans,
-- domain ownership verification, order idempotency, and durable login throttling.
-- Every statement is idempotent so the migration is safe to re-run.

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Tenant + user lifecycle status
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE restaurants
    ADD COLUMN IF NOT EXISTS status varchar(20) NOT NULL DEFAULT 'active';
-- active | trialing | suspended | cancelled
ALTER TABLE restaurants
    DROP CONSTRAINT IF EXISTS restaurants_status_check;
ALTER TABLE restaurants
    ADD CONSTRAINT restaurants_status_check
    CHECK (status IN ('active', 'trialing', 'suspended', 'cancelled'));

ALTER TABLE admin_users
    ADD COLUMN IF NOT EXISTS status varchar(20) NOT NULL DEFAULT 'active';
-- active | disabled
ALTER TABLE admin_users
    DROP CONSTRAINT IF EXISTS admin_users_status_check;
ALTER TABLE admin_users
    ADD CONSTRAINT admin_users_status_check
    CHECK (status IN ('active', 'disabled'));
ALTER TABLE admin_users
    ADD COLUMN IF NOT EXISTS last_login_at timestamptz;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Real subscription plans (priced) + subscription state machine
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE plans ADD COLUMN IF NOT EXISTS description text NOT NULL DEFAULT '';
ALTER TABLE plans ADD COLUMN IF NOT EXISTS currency char(3) NOT NULL DEFAULT 'USD';
ALTER TABLE plans ADD COLUMN IF NOT EXISTS monthly_price_cents integer NOT NULL DEFAULT 0;
ALTER TABLE plans ADD COLUMN IF NOT EXISTS annual_price_cents integer NOT NULL DEFAULT 0;
ALTER TABLE plans ADD COLUMN IF NOT EXISTS trial_days integer NOT NULL DEFAULT 0;
ALTER TABLE plans ADD COLUMN IF NOT EXISTS sort_order integer NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS subscriptions (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    plan_id bigint NOT NULL REFERENCES plans(id),
    status varchar(24) NOT NULL DEFAULT 'trialing',
    trial_ends_at timestamptz,
    current_period_start timestamptz NOT NULL DEFAULT now(),
    current_period_end timestamptz,
    cancel_at timestamptz,
    cancelled_at timestamptz,
    provider varchar(40) NOT NULL DEFAULT 'manual',
    provider_customer_id text,
    provider_subscription_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT subscriptions_status_check CHECK (
        status IN ('trialing','active','past_due','grace','unpaid',
                   'cancelled','suspended','expired','complimentary')
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_one_active_per_tenant
    ON subscriptions (tenant_id)
    WHERE status IN ('trialing','active','past_due','grace','complimentary');
CREATE INDEX IF NOT EXISTS idx_subscriptions_tenant ON subscriptions (tenant_id);

-- Plan change history (upgrade/downgrade audit)
CREATE TABLE IF NOT EXISTS plan_history (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    from_plan_id bigint REFERENCES plans(id),
    to_plan_id bigint NOT NULL REFERENCES plans(id),
    actor_type varchar(40) NOT NULL,
    actor_id text,
    reason text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Seed the three real plans (idempotent). Entitlements are layered on below.
INSERT INTO plans (plan_key, name, description, monthly_price_cents, annual_price_cents, trial_days, sort_order)
VALUES
    ('starter', 'Starter',  'Single-location online ordering and menu management.', 2900,  29000, 14, 1),
    ('growth',  'Growth',   'Multi-location, analytics, loyalty and AI chatbot.',  7900,  79000, 14, 2),
    ('pro',     'Pro',      'Full revenue-operator suite, experiments and missions.', 19900, 199000, 14, 3)
ON CONFLICT (plan_key) DO UPDATE
    SET name = EXCLUDED.name,
        description = EXCLUDED.description,
        monthly_price_cents = EXCLUDED.monthly_price_cents,
        annual_price_cents = EXCLUDED.annual_price_cents,
        trial_days = EXCLUDED.trial_days,
        sort_order = EXCLUDED.sort_order;

-- Core feature definitions that gate the SaaS tiers (limits enforced server-side).
INSERT INTO feature_definitions (feature_key, description, default_enabled, default_limit)
VALUES
    ('core.online_ordering', 'Accept online orders',          true,  NULL),
    ('core.custom_domain',   'Connect a custom domain',       false, 0),
    ('core.menu_items',      'Maximum menu items',            true,  50),
    ('core.admin_seats',     'Maximum admin users',           true,  2),
    ('core.locations',       'Maximum branches/locations',    true,  1),
    ('analytics.basic',      'Basic analytics dashboards',    false, NULL)
ON CONFLICT (feature_key) DO NOTHING;

-- Helper: set an entitlement for a plan by key.
DO $$
DECLARE
    starter_id bigint;
    growth_id  bigint;
    pro_id     bigint;
BEGIN
    SELECT id INTO starter_id FROM plans WHERE plan_key = 'starter';
    SELECT id INTO growth_id  FROM plans WHERE plan_key = 'growth';
    SELECT id INTO pro_id     FROM plans WHERE plan_key = 'pro';

    -- Starter
    INSERT INTO plan_entitlements (plan_id, feature_key, enabled, limit_value) VALUES
        (starter_id, 'core.online_ordering', true,  NULL),
        (starter_id, 'core.custom_domain',   false, 0),
        (starter_id, 'core.menu_items',      true,  50),
        (starter_id, 'core.admin_seats',     true,  2),
        (starter_id, 'core.locations',       true,  1),
        (starter_id, 'analytics.basic',      false, NULL),
        (starter_id, 'ai.chatbot',           false, NULL)
    ON CONFLICT (plan_id, feature_key) DO UPDATE
        SET enabled = EXCLUDED.enabled, limit_value = EXCLUDED.limit_value;

    -- Growth
    INSERT INTO plan_entitlements (plan_id, feature_key, enabled, limit_value) VALUES
        (growth_id, 'core.online_ordering', true,  NULL),
        (growth_id, 'core.custom_domain',   true,  1),
        (growth_id, 'core.menu_items',      true,  300),
        (growth_id, 'core.admin_seats',     true,  10),
        (growth_id, 'core.locations',       true,  5),
        (growth_id, 'analytics.basic',      true,  NULL),
        (growth_id, 'analytics.item_funnel',true,  NULL),
        (growth_id, 'ai.chatbot',           true,  NULL),
        (growth_id, 'opportunities.weekly_cards', true, NULL)
    ON CONFLICT (plan_id, feature_key) DO UPDATE
        SET enabled = EXCLUDED.enabled, limit_value = EXCLUDED.limit_value;

    -- Pro: enable every defined feature with no usage limit (unlimited).
    INSERT INTO plan_entitlements (plan_id, feature_key, enabled, limit_value)
    SELECT pro_id, f.feature_key, true, NULL::integer
    FROM feature_definitions f
    ON CONFLICT (plan_id, feature_key) DO UPDATE
        SET enabled = true, limit_value = NULL;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Domain ownership verification
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE domains ADD COLUMN IF NOT EXISTS verification_token varchar(80);
ALTER TABLE domains ADD COLUMN IF NOT EXISTS verification_method varchar(20) NOT NULL DEFAULT 'dns_txt';
ALTER TABLE domains ADD COLUMN IF NOT EXISTS verified_at timestamptz;
ALTER TABLE domains ADD COLUMN IF NOT EXISTS last_checked_at timestamptz;
ALTER TABLE domains ADD COLUMN IF NOT EXISTS ssl_status varchar(20) NOT NULL DEFAULT 'pending';
-- Normalized, globally-unique domain already enforced by existing unique index.
ALTER TABLE domains
    DROP CONSTRAINT IF EXISTS domains_method_check;
ALTER TABLE domains
    ADD CONSTRAINT domains_method_check
    CHECK (verification_method IN ('dns_txt','cname','none'));
-- New domains default to UNVERIFIED; existing rows are left untouched.
ALTER TABLE domains ALTER COLUMN verified SET DEFAULT false;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Order idempotency
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE orders ADD COLUMN IF NOT EXISTS idempotency_key varchar(80);
CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_tenant_idempotency
    ON orders (restaurant_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Durable login / auth throttling (works across multiple app instances)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS auth_rate_windows (
    bucket varchar(160) NOT NULL,
    window_start timestamptz NOT NULL,
    request_count integer NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (bucket, window_start)
);
CREATE INDEX IF NOT EXISTS idx_auth_rate_windows_start ON auth_rate_windows (window_start);

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Secure admin invitations (single-use, expiring, hashed token)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS admin_invitations (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    email varchar(255) NOT NULL,
    role varchar(50) NOT NULL DEFAULT 'admin',
    token_hash varchar(128) NOT NULL UNIQUE,
    invited_by text,
    expires_at timestamptz NOT NULL,
    accepted_at timestamptz,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_admin_invitations_tenant ON admin_invitations (tenant_id, email);
