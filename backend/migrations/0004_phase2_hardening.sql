ALTER TABLE daily_item_metrics ADD COLUMN IF NOT EXISTS unique_impression_sessions bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_item_metrics ADD COLUMN IF NOT EXISTS unique_detail_view_sessions bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_item_metrics ADD COLUMN IF NOT EXISTS modifier_starts bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_item_metrics ADD COLUMN IF NOT EXISTS unique_add_to_cart_sessions bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_item_metrics ADD COLUMN IF NOT EXISTS checkout_count bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_item_metrics ADD COLUMN IF NOT EXISTS purchase_count bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_item_metrics ADD COLUMN IF NOT EXISTS unique_carts bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_item_metrics ADD COLUMN IF NOT EXISTS discount_cents bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_item_metrics ADD COLUMN IF NOT EXISTS refund_count bigint NOT NULL DEFAULT 0;

ALTER TABLE daily_checkout_metrics ADD COLUMN IF NOT EXISTS median_duration_ms bigint;
ALTER TABLE daily_checkout_metrics ADD COLUMN IF NOT EXISTS delivery_area_rejections bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_checkout_metrics ADD COLUMN IF NOT EXISTS minimum_order_blocks bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_checkout_metrics ADD COLUMN IF NOT EXISTS coupon_failures bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_checkout_metrics ADD COLUMN IF NOT EXISTS mobile_entered bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_checkout_metrics ADD COLUMN IF NOT EXISTS mobile_completed bigint NOT NULL DEFAULT 0;

ALTER TABLE daily_source_metrics ADD COLUMN IF NOT EXISTS new_visitors bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_source_metrics ADD COLUMN IF NOT EXISTS returning_visitors bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_source_metrics ADD COLUMN IF NOT EXISTS item_views bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_source_metrics ADD COLUMN IF NOT EXISTS cart_sessions bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_source_metrics ADD COLUMN IF NOT EXISTS checkout_sessions bigint NOT NULL DEFAULT 0;
ALTER TABLE daily_source_metrics ADD COLUMN IF NOT EXISTS repeat_customers bigint NOT NULL DEFAULT 0;

ALTER TABLE basket_associations ADD COLUMN IF NOT EXISTS reverse_confidence numeric(12,8);
ALTER TABLE basket_associations ADD COLUMN IF NOT EXISTS combined_revenue_cents bigint;
ALTER TABLE basket_associations ADD COLUMN IF NOT EXISTS combined_cost_cents bigint;
ALTER TABLE basket_associations ADD COLUMN IF NOT EXISTS contribution_margin_cents bigint;

CREATE TABLE IF NOT EXISTS menu_item_classifications (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    item_id integer NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    period_start date NOT NULL,
    period_end date NOT NULL,
    classification varchar(30) NOT NULL CHECK (classification IN ('HERO','LEAKING','HIDDEN_WINNER','WEAK','INSUFFICIENT_DATA')),
    attention_rate numeric(12,8),
    conversion_rate numeric(12,8),
    category_attention_baseline numeric(12,8),
    category_conversion_baseline numeric(12,8),
    tenant_attention_baseline numeric(12,8),
    tenant_conversion_baseline numeric(12,8),
    sample_size bigint NOT NULL DEFAULT 0,
    confidence_score numeric(5,2) NOT NULL DEFAULT 0 CHECK (confidence_score BETWEEN 0 AND 100),
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    detector_version varchar(40) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, item_id, period_start, period_end)
);
CREATE INDEX IF NOT EXISTS idx_item_classifications_tenant_period ON menu_item_classifications (tenant_id, period_end DESC, classification);

CREATE TABLE IF NOT EXISTS basket_candidates (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    window_start date NOT NULL,
    window_end date NOT NULL,
    item_a_id integer NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    item_b_id integer NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    pair_orders bigint NOT NULL,
    support numeric(12,8),
    confidence numeric(12,8),
    reverse_confidence numeric(12,8),
    lift numeric(12,8),
    combined_revenue_cents bigint,
    contribution_margin_cents bigint,
    status varchar(24) NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate','approved','dismissed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, window_start, window_end, item_a_id, item_b_id),
    CHECK (item_a_id < item_b_id)
);

CREATE TABLE IF NOT EXISTS competitor_locations (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    competitor_id bigint NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    name varchar(200) NOT NULL,
    address text,
    city varchar(120),
    delivery_fee_cents bigint CHECK (delivery_fee_cents IS NULL OR delivery_fee_cents >= 0),
    currency varchar(3) NOT NULL DEFAULT 'USD',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, competitor_id, name)
);

CREATE TABLE IF NOT EXISTS competitor_sources (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    competitor_id bigint NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    source_url text NOT NULL,
    source_type varchar(30) NOT NULL CHECK (source_type IN ('website','menu','delivery_app','social','in_store','other')),
    captured_at timestamptz NOT NULL DEFAULT now(),
    verified_at timestamptz,
    verified_by text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS competitor_products (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    competitor_id bigint NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    location_id bigint REFERENCES competitor_locations(id) ON DELETE SET NULL,
    name varchar(200) NOT NULL,
    category varchar(120),
    size_label varchar(100),
    size_value numeric(12,3),
    size_unit varchar(30),
    estimated_servings numeric(8,2),
    ingredients_summary text,
    regular_price_cents bigint NOT NULL CHECK (regular_price_cents >= 0),
    deal_price_cents bigint CHECK (deal_price_cents IS NULL OR deal_price_cents >= 0),
    included_items jsonb NOT NULL DEFAULT '[]'::jsonb,
    delivery_fee_cents bigint CHECK (delivery_fee_cents IS NULL OR delivery_fee_cents >= 0),
    market_positioning varchar(120),
    source_url text,
    source_type varchar(30) NOT NULL DEFAULT 'other',
    captured_at timestamptz NOT NULL DEFAULT now(),
    verified_at timestamptz,
    verified_by text,
    confidence numeric(5,2) NOT NULL DEFAULT 50 CHECK (confidence BETWEEN 0 AND 100),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, competitor_id, name, size_label)
);
CREATE INDEX IF NOT EXISTS idx_competitor_products_tenant_competitor ON competitor_products (tenant_id, competitor_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS competitor_deals (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    competitor_id bigint NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    name varchar(200) NOT NULL,
    description text,
    price_cents bigint CHECK (price_cents IS NULL OR price_cents >= 0),
    included_items jsonb NOT NULL DEFAULT '[]'::jsonb,
    starts_at timestamptz,
    ends_at timestamptz,
    source_url text,
    captured_at timestamptz NOT NULL DEFAULT now(),
    verified_at timestamptz,
    verified_by text,
    status varchar(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','expired','archived')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS product_comparisons (
    id bigserial PRIMARY KEY,
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    own_item_id integer NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    competitor_product_id bigint NOT NULL REFERENCES competitor_products(id) ON DELETE CASCADE,
    match_quality numeric(5,2) NOT NULL CHECK (match_quality BETWEEN 0 AND 100),
    normalization_notes text,
    own_normalized_price_cents bigint NOT NULL CHECK (own_normalized_price_cents >= 0),
    competitor_normalized_price_cents bigint NOT NULL CHECK (competitor_normalized_price_cents >= 0),
    price_index numeric(12,4),
    approved_by_human boolean NOT NULL DEFAULT false,
    approved_by text,
    approved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, own_item_id, competitor_product_id)
);

UPDATE plan_entitlements pe SET enabled = true
FROM plans p WHERE pe.plan_id = p.id AND p.plan_key = 'legacy'
AND pe.feature_key IN ('analytics.item_funnel','analytics.menu_matrix','analytics.search_gap','analytics.checkout_friction','analytics.traffic_sources','analytics.chat_objections','analytics.basket','analytics.competitors','analytics.customer_segments');
