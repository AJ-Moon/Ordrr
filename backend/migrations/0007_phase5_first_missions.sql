CREATE TABLE IF NOT EXISTS customer_metric_profiles (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    customer_id text NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    order_count bigint NOT NULL DEFAULT 0,
    lifetime_revenue_cents bigint NOT NULL DEFAULT 0,
    lifetime_contribution_cents bigint,
    average_order_value_cents bigint NOT NULL DEFAULT 0,
    average_reorder_interval_days numeric(10,2),
    expected_reorder_at timestamptz,
    last_order_at timestamptz,
    preferred_categories jsonb NOT NULL DEFAULT '[]'::jsonb,
    preferred_location_id integer REFERENCES branches(id) ON DELETE SET NULL,
    discount_dependency numeric(7,4) NOT NULL DEFAULT 0,
    usual_daypart varchar(30),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, customer_id)
);

CREATE TABLE IF NOT EXISTS segment_rules (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    segment_key varchar(80) NOT NULL,
    rule_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, segment_key)
);

CREATE TABLE IF NOT EXISTS customer_segment_memberships (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    customer_id text NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    segment_key varchar(80) NOT NULL,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    calculated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, customer_id, segment_key)
);

CREATE TABLE IF NOT EXISTS missions (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    opportunity_id bigint REFERENCES opportunities(id) ON DELETE SET NULL,
    location_id integer REFERENCES branches(id) ON DELETE SET NULL,
    type varchar(50) NOT NULL CHECK (type IN (
        'ABANDONED_CART_RECOVERY','QUIET_HOUR_DEMAND','INTELLIGENT_BUNDLE',
        'NEW_PRODUCT_DEMAND_TEST','LAPSED_CUSTOMER_WINBACK'
    )),
    name varchar(200) NOT NULL,
    objective text NOT NULL,
    hypothesis text NOT NULL,
    start_at timestamptz,
    end_at timestamptz,
    timezone varchar(64) NOT NULL DEFAULT 'UTC',
    budget_limit_cents bigint CHECK (budget_limit_cents IS NULL OR budget_limit_cents >= 0),
    discount_limit_cents bigint CHECK (discount_limit_cents IS NULL OR discount_limit_cents >= 0),
    minimum_margin_cents bigint,
    maximum_redemptions integer CHECK (maximum_redemptions IS NULL OR maximum_redemptions > 0),
    capacity_limit integer CHECK (capacity_limit IS NULL OR capacity_limit > 0),
    audience_definition jsonb NOT NULL DEFAULT '{}'::jsonb,
    holdout_percentage integer NOT NULL DEFAULT 10 CHECK (holdout_percentage BETWEEN 0 AND 50),
    primary_metric varchar(80) NOT NULL,
    guardrail_metrics jsonb NOT NULL DEFAULT '[]'::jsonb,
    status varchar(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
        'DRAFT','NEEDS_APPROVAL','APPROVED','SCHEDULED','RUNNING','PAUSED',
        'COMPLETED','CANCELLED','FAILED'
    )),
    approval_user_id text,
    approved_at timestamptz,
    started_at timestamptz,
    completed_at timestamptz,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (end_at IS NULL OR start_at IS NULL OR end_at > start_at)
);
CREATE INDEX IF NOT EXISTS idx_missions_tenant_status ON missions (tenant_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS mission_audiences (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    mission_id bigint NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    subject_type varchar(30) NOT NULL,
    subject_id text NOT NULL,
    customer_id text REFERENCES customers(id) ON DELETE SET NULL,
    eligibility_snapshot jsonb NOT NULL,
    eligible boolean NOT NULL,
    reason varchar(120) NOT NULL,
    evaluated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (mission_id, subject_type, subject_id)
);

CREATE TABLE IF NOT EXISTS mission_guardrails (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    mission_id bigint NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    guardrail_key varchar(80) NOT NULL,
    threshold_json jsonb NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'ok' CHECK (status IN ('ok','warning','breached')),
    last_value jsonb,
    checked_at timestamptz,
    UNIQUE (mission_id, guardrail_key)
);

CREATE TABLE IF NOT EXISTS mission_actions (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    mission_id bigint NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    action_type varchar(60) NOT NULL,
    sequence_number integer NOT NULL DEFAULT 1 CHECK (sequence_number > 0),
    channel varchar(24),
    config jsonb NOT NULL DEFAULT '{}'::jsonb,
    status varchar(20) NOT NULL DEFAULT 'configured' CHECK (status IN ('configured','active','paused','completed','failed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (mission_id, sequence_number)
);

CREATE TABLE IF NOT EXISTS mission_holdouts (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    mission_id bigint NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    subject_type varchar(30) NOT NULL,
    subject_id text NOT NULL,
    group_name varchar(20) NOT NULL CHECK (group_name IN ('treatment','holdout')),
    assigned_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (mission_id, subject_type, subject_id)
);

CREATE TABLE IF NOT EXISTS mission_events (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    mission_id bigint NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    event_key varchar(160) NOT NULL,
    event_type varchar(80) NOT NULL,
    subject_type varchar(30),
    subject_id text,
    customer_id text REFERENCES customers(id) ON DELETE SET NULL,
    cart_id text,
    order_id varchar(20) REFERENCES orders(id) ON DELETE SET NULL,
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, event_key)
);

CREATE TABLE IF NOT EXISTS mission_results (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    mission_id bigint NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    treatment_size bigint NOT NULL DEFAULT 0,
    holdout_size bigint NOT NULL DEFAULT 0,
    treatment_conversions bigint NOT NULL DEFAULT 0,
    holdout_conversions bigint NOT NULL DEFAULT 0,
    incremental_orders numeric(14,4) NOT NULL DEFAULT 0,
    revenue_cents bigint NOT NULL DEFAULT 0,
    incremental_revenue_cents bigint NOT NULL DEFAULT 0,
    contribution_margin_cents bigint,
    discount_cost_cents bigint NOT NULL DEFAULT 0,
    message_cost_cents bigint NOT NULL DEFAULT 0,
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    evaluated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mission_results_latest ON mission_results (tenant_id, mission_id, evaluated_at DESC);

CREATE TABLE IF NOT EXISTS campaign_messages (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    mission_id bigint NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    action_id bigint REFERENCES mission_actions(id) ON DELETE SET NULL,
    customer_id text NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    subject_type varchar(30) NOT NULL,
    subject_id text NOT NULL,
    channel varchar(24) NOT NULL CHECK (channel IN ('email','sms','whatsapp')),
    provider varchar(40) NOT NULL,
    provider_message_id varchar(160),
    content jsonb NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED','SENT','DELIVERED','FAILED','CLICKED','UNSUBSCRIBED')),
    failure_reason varchar(160),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (mission_id, action_id, subject_type, subject_id)
);

CREATE TABLE IF NOT EXISTS message_deliveries (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    campaign_message_id bigint NOT NULL REFERENCES campaign_messages(id) ON DELETE CASCADE,
    status varchar(30) NOT NULL CHECK (status IN ('QUEUED','SENT','DELIVERED','FAILED','CLICKED','UNSUBSCRIBED')),
    provider_event_id varchar(160),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (campaign_message_id, status)
);

UPDATE plan_entitlements pe SET enabled = true
FROM plans p WHERE pe.plan_id = p.id AND p.plan_key = 'legacy'
AND pe.feature_key IN ('missions.abandoned_cart','missions.bundle','missions.lapsed_customer');
