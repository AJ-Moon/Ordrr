CREATE TABLE IF NOT EXISTS capacity_settings (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    location_id integer NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    weekday integer NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    time_start time NOT NULL,
    time_end time NOT NULL,
    normal_capacity_orders integer NOT NULL CHECK (normal_capacity_orders > 0),
    maximum_capacity_orders integer NOT NULL CHECK (maximum_capacity_orders >= normal_capacity_orders),
    target_utilization numeric(5,4) NOT NULL DEFAULT 0.7500 CHECK (target_utilization > 0 AND target_utilization <= 1),
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (time_end > time_start),
    UNIQUE (tenant_id, location_id, weekday, time_start, time_end)
);
CREATE INDEX IF NOT EXISTS idx_capacity_settings_active
    ON capacity_settings (tenant_id, enabled, weekday, location_id);

CREATE TABLE IF NOT EXISTS inventory_guardrails (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    item_id integer NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    available_quantity integer CHECK (available_quantity IS NULL OR available_quantity >= 0),
    low_stock_threshold integer NOT NULL DEFAULT 0 CHECK (low_stock_threshold >= 0),
    constrained boolean NOT NULL DEFAULT false,
    notes text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_inventory_guardrails_constrained
    ON inventory_guardrails (tenant_id, constrained, updated_at DESC);

CREATE TABLE IF NOT EXISTS quiet_hour_candidates (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    capacity_setting_id bigint NOT NULL REFERENCES capacity_settings(id) ON DELETE CASCADE,
    location_id integer NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    weekday integer NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    time_start time NOT NULL,
    time_end time NOT NULL,
    observed_orders numeric(10,2) NOT NULL DEFAULT 0,
    normal_capacity_orders integer NOT NULL,
    maximum_capacity_orders integer NOT NULL,
    target_utilization numeric(5,4) NOT NULL,
    actual_utilization numeric(7,4) NOT NULL DEFAULT 0,
    cancellation_rate numeric(7,4) NOT NULL DEFAULT 0,
    available_margin_items integer NOT NULL DEFAULT 0,
    status varchar(30) NOT NULL CHECK (status IN ('CANDIDATE','BLOCKED','ACTIVE','PAUSED')),
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    calculated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, capacity_setting_id)
);
CREATE INDEX IF NOT EXISTS idx_quiet_hour_candidates_status
    ON quiet_hour_candidates (tenant_id, status, calculated_at DESC);

CREATE TABLE IF NOT EXISTS product_concepts (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    mission_id bigint REFERENCES missions(id) ON DELETE SET NULL,
    name varchar(160) NOT NULL,
    description text NOT NULL,
    category varchar(80) NOT NULL,
    estimated_cost_cents bigint NOT NULL CHECK (estimated_cost_cents >= 0),
    estimated_preparation_time_minutes integer NOT NULL CHECK (estimated_preparation_time_minutes > 0),
    target_location_id integer REFERENCES branches(id) ON DELETE SET NULL,
    target_segment varchar(80),
    status varchar(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
        'DRAFT','NEEDS_APPROVAL','APPROVED','RUNNING','PAUSED','COMPLETED','CANCELLED'
    )),
    presentation_mode varchar(30) NOT NULL CHECK (presentation_mode IN (
        'COMING_SOON','LIMITED_TEST','PREORDER','JOIN_WAITLIST'
    )),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_product_concepts_tenant_status
    ON product_concepts (tenant_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS product_concept_variants (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    concept_id bigint NOT NULL REFERENCES product_concepts(id) ON DELETE CASCADE,
    variant_key varchar(80) NOT NULL,
    name varchar(160) NOT NULL,
    image_url text,
    description text NOT NULL,
    price_cents bigint CHECK (price_cents IS NULL OR price_cents >= 0),
    deal_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    serving_claim varchar(160),
    weight integer NOT NULL DEFAULT 1 CHECK (weight > 0),
    is_control boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, concept_id, variant_key)
);
CREATE INDEX IF NOT EXISTS idx_product_concept_variants_concept
    ON product_concept_variants (tenant_id, concept_id);

CREATE TABLE IF NOT EXISTS product_interest_events (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    concept_id bigint NOT NULL REFERENCES product_concepts(id) ON DELETE CASCADE,
    variant_id bigint REFERENCES product_concept_variants(id) ON DELETE SET NULL,
    mission_id bigint REFERENCES missions(id) ON DELETE SET NULL,
    event_key varchar(180) NOT NULL,
    visitor_id varchar(120),
    session_id varchar(120),
    customer_id text REFERENCES customers(id) ON DELETE SET NULL,
    event_type varchar(30) NOT NULL CHECK (event_type IN ('VIEW','INTEREST','WAITLIST','PREORDER')),
    preferred_price_cents bigint CHECK (preferred_price_cents IS NULL OR preferred_price_cents >= 0),
    segment varchar(80),
    geography varchar(120),
    source varchar(80),
    medium varchar(80),
    campaign varchar(120),
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, event_key)
);
CREATE INDEX IF NOT EXISTS idx_product_interest_events_concept
    ON product_interest_events (tenant_id, concept_id, event_type, occurred_at DESC);

CREATE TABLE IF NOT EXISTS product_waitlist_entries (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    concept_id bigint NOT NULL REFERENCES product_concepts(id) ON DELETE CASCADE,
    variant_id bigint REFERENCES product_concept_variants(id) ON DELETE SET NULL,
    customer_id text REFERENCES customers(id) ON DELETE SET NULL,
    visitor_id varchar(120),
    email varchar(255),
    phone varchar(40),
    segment varchar(80),
    geography varchar(120),
    status varchar(30) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','CONTACTED','CONVERTED','CANCELLED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (email IS NOT NULL OR phone IS NOT NULL OR customer_id IS NOT NULL OR visitor_id IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_product_waitlist_unique_email
    ON product_waitlist_entries (tenant_id, concept_id, lower(email))
    WHERE email IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_product_waitlist_unique_visitor
    ON product_waitlist_entries (tenant_id, concept_id, visitor_id)
    WHERE visitor_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS product_preorders (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    concept_id bigint NOT NULL REFERENCES product_concepts(id) ON DELETE CASCADE,
    variant_id bigint REFERENCES product_concept_variants(id) ON DELETE SET NULL,
    customer_id text REFERENCES customers(id) ON DELETE SET NULL,
    visitor_id varchar(120),
    email varchar(255),
    phone varchar(40),
    quantity integer NOT NULL DEFAULT 1 CHECK (quantity > 0 AND quantity <= 20),
    price_cents bigint NOT NULL CHECK (price_cents >= 0),
    deposit_cents bigint NOT NULL DEFAULT 0 CHECK (deposit_cents >= 0),
    status varchar(30) NOT NULL DEFAULT 'RESERVED' CHECK (status IN ('RESERVED','CANCELLED','CONVERTED','REFUNDED')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_product_preorders_concept
    ON product_preorders (tenant_id, concept_id, status, created_at DESC);

UPDATE plan_entitlements pe SET enabled = true
FROM plans p
WHERE pe.plan_id = p.id
  AND p.plan_key = 'legacy'
  AND pe.feature_key IN ('missions.quiet_hour','missions.product_demand_test');
