CREATE TABLE IF NOT EXISTS opportunities (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    location_id integer REFERENCES branches(id) ON DELETE SET NULL,
    type varchar(60) NOT NULL,
    entity_type varchar(40) NOT NULL,
    entity_id text,
    period_start date NOT NULL,
    period_end date NOT NULL,
    headline varchar(240) NOT NULL,
    summary text NOT NULL,
    estimated_revenue_impact_cents bigint,
    estimated_margin_impact_cents bigint,
    impact_score numeric(5,2) NOT NULL CHECK (impact_score BETWEEN 0 AND 100),
    confidence_score numeric(5,2) NOT NULL CHECK (confidence_score BETWEEN 0 AND 100),
    effort_score numeric(5,2) NOT NULL CHECK (effort_score BETWEEN 0 AND 100),
    urgency_score numeric(5,2) NOT NULL CHECK (urgency_score BETWEEN 0 AND 100),
    priority_score numeric(5,2) NOT NULL CHECK (priority_score BETWEEN 0 AND 100),
    evidence_json jsonb NOT NULL,
    recommended_action_json jsonb NOT NULL,
    ai_explanation_json jsonb,
    detector_version varchar(40) NOT NULL,
    fingerprint varchar(64) NOT NULL,
    trend varchar(20) NOT NULL DEFAULT 'new' CHECK (trend IN ('new','improving','worsening','unchanged')),
    status varchar(40) NOT NULL DEFAULT 'DETECTED' CHECK (status IN ('DETECTED','NEEDS_REVIEW','RECOMMENDED','APPROVED','DISMISSED','CONVERTED_TO_EXPERIMENT','CONVERTED_TO_MISSION','RESOLVED','EXPIRED')),
    first_detected_at timestamptz NOT NULL DEFAULT now(),
    last_detected_at timestamptz NOT NULL DEFAULT now(),
    viewed_at timestamptz,
    view_count integer NOT NULL DEFAULT 0,
    approved_at timestamptz,
    approved_by text,
    dismissed_at timestamptz,
    dismissed_by text,
    dismissal_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_opportunities_tenant_status_priority ON opportunities (tenant_id, status, priority_score DESC, last_detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_opportunities_tenant_period ON opportunities (tenant_id, period_end DESC, type);

CREATE TABLE IF NOT EXISTS opportunity_evidence (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    opportunity_id bigint NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    evidence_key varchar(100) NOT NULL,
    value_json jsonb NOT NULL,
    source_table varchar(100) NOT NULL,
    period_start date NOT NULL,
    period_end date NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (opportunity_id, evidence_key)
);

CREATE TABLE IF NOT EXISTS opportunity_actions (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    opportunity_id bigint NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    actor_type varchar(30) NOT NULL,
    actor_id text,
    action varchar(60) NOT NULL,
    from_status varchar(40),
    to_status varchar(40),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_opportunity_actions_tenant_opportunity ON opportunity_actions (tenant_id, opportunity_id, created_at DESC);

CREATE TABLE IF NOT EXISTS opportunity_comments (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    opportunity_id bigint NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    actor_id text NOT NULL,
    body varchar(2000) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_generation_logs (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    opportunity_id bigint REFERENCES opportunities(id) ON DELETE CASCADE,
    operation varchar(80) NOT NULL,
    provider varchar(50) NOT NULL,
    model varchar(100),
    prompt_version varchar(40) NOT NULL,
    input_evidence_hash varchar(64) NOT NULL,
    output_json jsonb,
    validation_result varchar(30) NOT NULL,
    latency_ms integer,
    input_tokens integer,
    output_tokens integer,
    error text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ai_generation_logs_tenant_created ON ai_generation_logs (tenant_id, created_at DESC);

UPDATE plan_entitlements pe SET enabled = true
FROM plans p WHERE pe.plan_id = p.id AND p.plan_key = 'legacy' AND pe.feature_key = 'opportunities.weekly_cards';
