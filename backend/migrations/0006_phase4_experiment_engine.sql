CREATE TABLE IF NOT EXISTS experiments (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    opportunity_id bigint REFERENCES opportunities(id) ON DELETE SET NULL,
    location_id integer REFERENCES branches(id) ON DELETE SET NULL,
    type varchar(40) NOT NULL CHECK (type IN (
        'PRODUCT_IMAGE','PRODUCT_NAME','PRODUCT_DESCRIPTION','PRODUCT_POSITION',
        'SERVING_INFORMATION','PRICE','DEAL','BUTTON_COPY','LANDING_PAGE',
        'MODIFIER_DEFAULT','UPSELL','CHAT_RECOMMENDATION','MENU_LAYOUT'
    )),
    name varchar(200) NOT NULL,
    hypothesis text NOT NULL,
    entity_type varchar(40),
    entity_id text,
    placement varchar(100) NOT NULL DEFAULT 'GENERIC',
    audience_definition jsonb NOT NULL DEFAULT '{}'::jsonb,
    primary_metric varchar(80) NOT NULL,
    guardrail_metrics jsonb NOT NULL DEFAULT '[]'::jsonb,
    minimum_sample integer NOT NULL DEFAULT 100 CHECK (minimum_sample BETWEEN 20 AND 1000000),
    confidence_level numeric(5,4) NOT NULL DEFAULT 0.95 CHECK (confidence_level BETWEEN 0.80 AND 0.999),
    allocation_percentage integer NOT NULL DEFAULT 100 CHECK (allocation_percentage BETWEEN 1 AND 100),
    conflict_key varchar(160) NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
        'DRAFT','NEEDS_APPROVAL','SCHEDULED','RUNNING','PAUSED','COMPLETED',
        'CANCELLED','INCONCLUSIVE'
    )),
    starts_at timestamptz,
    ends_at timestamptz,
    approved_by text,
    approved_at timestamptz,
    started_at timestamptz,
    completed_at timestamptz,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at)
);
CREATE INDEX IF NOT EXISTS idx_experiments_tenant_status ON experiments (tenant_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_experiments_active_conflict ON experiments (tenant_id, conflict_key, status)
    WHERE status IN ('SCHEDULED','RUNNING');

CREATE TABLE IF NOT EXISTS experiment_variants (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    experiment_id bigint NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    variant_key varchar(80) NOT NULL,
    name varchar(160) NOT NULL,
    config jsonb NOT NULL DEFAULT '{}'::jsonb,
    weight integer NOT NULL DEFAULT 50 CHECK (weight BETWEEN 1 AND 10000),
    is_control boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (experiment_id, variant_key)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_experiment_control ON experiment_variants (experiment_id) WHERE is_control;

CREATE TABLE IF NOT EXISTS experiment_assignments (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    experiment_id bigint NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    variant_id bigint NOT NULL REFERENCES experiment_variants(id) ON DELETE CASCADE,
    visitor_id varchar(100) NOT NULL,
    customer_id text REFERENCES customers(id) ON DELETE SET NULL,
    audience_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (experiment_id, visitor_id)
);
CREATE INDEX IF NOT EXISTS idx_experiment_assignments_tenant_visitor ON experiment_assignments (tenant_id, visitor_id, assigned_at DESC);

CREATE TABLE IF NOT EXISTS experiment_exposures (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    experiment_id bigint NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    variant_id bigint NOT NULL REFERENCES experiment_variants(id) ON DELETE CASCADE,
    assignment_id bigint NOT NULL REFERENCES experiment_assignments(id) ON DELETE CASCADE,
    exposure_key varchar(120) NOT NULL,
    visitor_id varchar(100) NOT NULL,
    session_id varchar(100) NOT NULL,
    occurred_at timestamptz NOT NULL,
    context jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, exposure_key)
);
CREATE INDEX IF NOT EXISTS idx_experiment_exposures_experiment_time ON experiment_exposures (tenant_id, experiment_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS experiment_outcomes (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    experiment_id bigint NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    variant_id bigint NOT NULL REFERENCES experiment_variants(id) ON DELETE CASCADE,
    visitor_id varchar(100) NOT NULL,
    order_id varchar(20) REFERENCES orders(id) ON DELETE CASCADE,
    metric varchar(80) NOT NULL,
    value numeric(18,4) NOT NULL,
    revenue_cents bigint NOT NULL DEFAULT 0,
    contribution_margin_cents bigint,
    occurred_at timestamptz NOT NULL,
    attribution_method varchar(40) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (experiment_id, metric, order_id)
);

CREATE TABLE IF NOT EXISTS experiment_results (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    experiment_id bigint NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    result varchar(30) NOT NULL CHECK (result IN ('WINNER','LOSER','INCONCLUSIVE','INSUFFICIENT_DATA')),
    winning_variant_id bigint REFERENCES experiment_variants(id) ON DELETE SET NULL,
    method varchar(80) NOT NULL,
    confidence_level numeric(5,4) NOT NULL,
    sample_size bigint NOT NULL,
    metrics jsonb NOT NULL,
    guardrail_status jsonb NOT NULL DEFAULT '{}'::jsonb,
    evaluated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_experiment_results_latest ON experiment_results (tenant_id, experiment_id, evaluated_at DESC);

UPDATE plan_entitlements pe SET enabled = true
FROM plans p WHERE pe.plan_id = p.id AND p.plan_key = 'legacy' AND pe.feature_key = 'experiments.enabled';
