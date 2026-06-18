# Data Dictionary

## Existing core

- `restaurants`: tenant root.
- `domains`: verified hostname-to-tenant mapping.
- `users` / `admin_users` / `platform_admins`: customer and administrative identities.
- `menu_items`: tenant menu catalog with compatibility decimals plus authoritative currency, integer price, sale price, ingredient cost, and packaging cost snapshots.
- `orders`: tenant order header with compatibility decimals/JSONB plus integer totals, costs, margin, visitor/session/cart links, and completion time.
- `settings` / `theme_settings`: operational and presentation configuration.

## Phase 0

- `feature_definitions`, `plans`, `plan_entitlements`, `tenant_plans`, `tenant_feature_overrides`, `feature_usage`: entitlement catalog, assignment, overrides, and monthly usage.
- `audit_logs`: actor, action, resource, before/after JSON, metadata, and timestamp.
- `customers`: analytics/customer profile linked optionally to an existing authenticated user.
- `customer_identities`: hashed identity keys and non-sensitive display hints.
- `customer_consents`: per-channel status and provenance.
- `communication_suppressions`: active channel-level messaging blocks.

## Phase 1

- `carts`, `cart_lines`: normalized active/converted/abandoned cart state priced from menu records.
- `order_line_items`: immutable normalized line snapshots for price, discount, costs, revenue, and contribution margin.
- `analytics_events`: canonical client and server event store, deduplicated by tenant and event ID.
- `event_ingestion_windows`: per-tenant minute counters used for ingestion limits.
- `job_runs`: durable PostgreSQL job queue and execution ledger with retries and idempotency keys.
- `communication_frequency_limits`: tenant/channel caps consulted with consent and suppression state.
- `daily_item_metrics`, `daily_funnel_metrics`, `daily_search_metrics`, `daily_checkout_metrics`, `daily_source_metrics`: rebuildable daily aggregates populated by `analytics.aggregate_daily` (all rows use `location_id = 0`, a tenant-wide rollup).
- `daily_chat_metrics`, `daily_customer_metrics`: rebuildable daily aggregates populated by `analytics.aggregate_daily` (Phase 2); chat metrics from `analytics_events` chat event types, customer metrics from new-vs-returning order classification.
- `basket_associations`: item-pair support/confidence/lift over a rolling window, recomputed by `analytics.refresh_basket_associations` (Phase 2).
- `data_quality_checks`: latest status, affected count, details, and check time for each quality rule.

## Phase 2

- `competitors`: manually maintained competitor records per tenant (name, website, address, notes, currency, reference item/price, status, verification timestamp/actor). Unique on `(tenant_id, name)`.
- `menu_item_classifications`: persisted menu-matrix classification, confidence, baselines, and evidence window for each item.
- `basket_candidates`: materialized candidate pairs used to support richer basket analysis.
- `competitor_locations`, `competitor_sources`, `competitor_products`, `competitor_deals`: normalized competitor observations and provenance.
- `product_comparisons`: own-item-to-competitor-product matching, normalized price index, match quality, and required human approval.
- Phase 2 aggregate tables include richer unique-session, checkout, purchase, discount/refund, source, and bidirectional basket fields added by migration `0004_phase2_hardening.sql`.

## Phase 3

- `opportunities`: deterministic findings, evidence window, bounded scores, financial estimates, lifecycle, trend, AI explanation, detector version, and stable tenant fingerprint.
- `opportunity_evidence`: detector evidence snapshots keyed to an opportunity.
- `opportunity_actions`: append-only view, comment, approval, dismissal, and other lifecycle actions.
- `opportunity_comments`: tenant-scoped admin discussion.
- `ai_generation_logs`: aggregate evidence hash, provider/model/prompt version, validated output, latency, token counts, and errors for every explanation attempt.

## Phase 4

- `experiments`: configuration, audience, metric, confidence/sample bounds, placement, conflict key, schedule, approval, and lifecycle.
- `experiment_variants`: weighted control/treatment configuration.
- `experiment_assignments`: unique sticky visitor assignment.
- `experiment_exposures`: idempotent actual-render records.
- `experiment_outcomes`: authoritative post-exposure order outcomes.
- `experiment_results`: statistical result, winning variant, uncertainty method, financial metrics, and guardrails.

## Phase 5

- `customer_metric_profiles`, `segment_rules`, `customer_segment_memberships`: deterministic customer value, timing, preference, and segment evidence.
- `missions`: shared mission configuration, financial/capacity bounds, approval, and lifecycle.
- `mission_audiences`, `mission_guardrails`, `mission_actions`, `mission_holdouts`, `mission_events`, `mission_results`: eligibility, execution, deterministic control groups, evidence, and incrementality.
- `campaign_messages`, `message_deliveries`: consent-checked mock campaign message and delivery ledger.
- `intervention_request_windows`: database-backed per-tenant/minute limits for public experiment assignment/exposure and mission assignment APIs.

Money is stored in minor units (`*_cents`) with a three-letter currency. Legacy decimal columns remain dual-written for existing clients during migration.
