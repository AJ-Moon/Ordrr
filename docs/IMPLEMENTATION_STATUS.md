# Implementation Status

Updated: 2026-06-14

## Phase 0

Implemented:

- Repository and architecture inspection.
- Strict production domain resolution and shared auth dependencies.
- Cross-tenant checks for required and optional customer authentication.
- Feature entitlement schema/service and admin read API.
- Audit schema/service, admin read API, and writes for menu/settings/theme/domain/tenant changes.
- Customer/identity/consent/suppression schema and self-service consent APIs.
- Customer profile UI for email, SMS, and WhatsApp consent preferences.
- SQL migration runner and environment examples.

Migrations: `backend/migrations/0000_baseline_primary_keys.sql`, `backend/migrations/0001_phase0_security_foundation.sql`.

New APIs: `GET /api/v1/admin/features`, `GET /api/v1/admin/audit-logs`, `GET|PUT /api/v1/customers/me/consents`.

### This session's verification (live database)

The migrations were applied to the configured Supabase database (`backend/.env`). Applying them surfaced two pre-existing schema issues that were fixed:

- The live database had no primary key / unique constraints on `restaurants`, `menu_items`, or `branches`, which blocked the foreign keys added by migration 0001. Verified row uniqueness/non-null on all three tables, then added `backend/migrations/0000_baseline_primary_keys.sql` to add the missing primary keys (data-safe, no rows affected).
- The database already contained an unrelated legacy `order_items` table (uuid-keyed, from a different schema sharing this Supabase project), which silently collided with our `CREATE TABLE IF NOT EXISTS order_items`. Renamed our Phase 1 table to `order_line_items` everywhere (migration, `services/commerce.py`, `services/analytics_jobs.py`).

After both fixes, `python3 scripts/migrate.py` applied migrations 0000, 0001, and 0002 cleanly (verified via `schema_migrations` and a full table listing — 27 tables present).

Live verification performed against the migrated database:

- `GET /api/v1/admin/features`, `GET /api/v1/admin/audit-logs`, `GET /api/v1/data-quality` all return correct, tenant-scoped data under admin auth.
- Entitlement system confirmed to be additive scaffolding only: grepped the codebase and confirmed no router/service currently calls `require_feature` / `has_feature` / `consume_feature_usage`, so existing features (e.g. chatbot) are unaffected even though `ai.chatbot` shows `enabled: false` by default.
- **Cross-tenant isolation** (created a temporary second tenant, ran 4 live tests, then deleted it):
  1. Tenant B cannot place an order referencing Tenant A's menu item → HTTP 422.
  2. Tenant B's event batch referencing Tenant A's `itemId` is rejected with "itemId does not belong to this restaurant".
  3. Tenant B's cart sync referencing Tenant A's menu item → HTTP 422.
  4. Tenant A's admin JWT cannot be used with `X-Restaurant-ID: <Tenant B>` → 403 "Token is not valid for this tenant".

Verification (repeat checks):

- Backend unit tests: 18 passed.
- Frontend production build: passed (`tsc -b && vite build`).
- Frontend ESLint: passed, 0 errors, 20 pre-existing warnings (unused values / hook dependencies).
- Python Ruff/mypy: still not installed in the active runtime.

Limitations: no frontend entitlement/audit administration UI yet.

## Phase 1

Implemented in code:

- Server-authoritative cart, checkout, and chatbot pricing with integer money, cost, margin, and normalized line snapshots.
- Restaurant-open, minimum-order, branch, availability, order-type, and payment validation at order creation.
- Canonical event storage, tenant validation, deduplication, limits, partial batch results, server commerce events, and first-party frontend tracking.
- Visitor/session/cart identity, cart sync, attribution capture, checkout and consent instrumentation.
- Durable PostgreSQL jobs with retries, scheduler, daily aggregates, retention, abandoned-cart evaluation, data-quality checks, and admin operations UI.
- Consent-aware communication eligibility, channel frequency caps, customer export, and customer anonymization.
- FastAPI OpenAPI export and generated frontend TypeScript API definitions.

Migration: `backend/migrations/0002_phase1_event_commerce_foundation.sql` (table renamed to `order_line_items`, see Phase 0 notes above).

### This session's verification (live database)

End-to-end flow verified against the migrated Supabase database, all via real HTTP requests to a locally running backend (since stopped):

- **Event ingestion** (`POST /api/v1/events/batch`): idempotent dedup on `(tenant_id, event_id)`, content-length and rate-window checks, entity-ownership validation against `menu_items`/`branches`/`orders`, and savepoint-based partial-batch processing all confirmed working.
- **Cart sync** (`POST /api/v1/carts/sync`): persists `carts`/`cart_lines` with server-computed cents pricing; rejects items not belonging to the tenant.
- **Order creation** (`POST /api/orders/`): server-authoritative pricing recomputed from `menu_items` (not client-supplied prices), correct integer-cents math end-to-end, `order_line_items` rows written with line-level revenue/margin snapshots, `mark_cart_converted`, and `order_created` server event emitted idempotently.
- **Order status transition to "delivered"** (`admin_update_order_status`): emits `order_completed` exactly once (idempotency key `order-completed:{order_id}`), awards loyalty points, and enqueues `analytics.aggregate_daily`.
- **Background jobs** (`scripts/worker.py --once`, run with `PYTHONPATH=.`): `analytics.aggregate_daily`, `analytics.aggregate_hourly`, and `data_quality.refresh` all ran successfully (`job_runs.status = 'succeeded'`) and produced correct `daily_item_metrics` / `daily_funnel_metrics` rows reflecting the test order's revenue and funnel counts.
- **Cross-tenant isolation**: see Phase 0 section above — events, carts, and orders are all rejected across tenants, and admin JWTs are tenant-pinned.

All test data created during this verification (the temporary second tenant, one test order `FH-580239`, its cart/cart-lines/order-line-items, 5 analytics events, and the corresponding `daily_item_metrics`/`daily_funnel_metrics` rows for 2026-06-14) was deleted from the live database afterward. `job_runs` and `data_quality_checks` rows produced by the job runs were left in place as a normal operational record.

Verification (repeat checks):

- Backend unit tests: 18 passed.
- Frontend production build: passed.
- ESLint: passed, 0 errors, 20 pre-existing warnings.

Known limitation (pre-existing, out of scope for Phase 0/1): there is no order-cancellation/refund endpoint anywhere in the codebase, so the `order_cancelled` / `order_refunded` events defined in the event taxonomy (`services/events.py`) are never emitted. This does not affect the implemented Phase 0/1 flows (creation → completion).

## Phase 2

Implemented and hardened:

- Migrations `0003_phase2_analytics_competitors.sql` and `0004_phase2_hardening.sql` are applied to the configured database.
- Every analytics and competitor API now requires both restaurant-admin authentication and its backend feature entitlement.
- Item analytics persist a 30-day menu matrix classification (`HERO`, `LEAKING`, `HIDDEN_WINNER`, `WEAK`, or `INSUFFICIENT_DATA`) with baselines, confidence, richer unique-session funnel counts, refunds, and discounts.
- Search conversion follows later events from the same session instead of requiring the search query on downstream events. Checkout, source, customer, chat, and basket aggregates expose richer counts and rates; basket evidence uses completed orders and bidirectional confidence.
- Competitor storage now includes locations, sources, products, deals, and human-approved normalized product comparisons. Existing competitor CRUD and verification remain compatible.
- API query sizes and date ranges are bounded. Manual admin job requests are limited per tenant/hour. The analytics dashboard displays menu classifications and honest sample warnings.

Live verification:

- Ran the full aggregate job successfully for tenant 1.
- Confirmed an entitlement override disables an analytics endpoint with HTTP 403, then removed the temporary override.
- Confirmed the item analytics and competitor-product endpoints return tenant-scoped responses.
- Temporary verification data was deleted afterward.

Residual Phase 2 boundaries:

- Aggregates are tenant-wide (`location_id = 0`); per-location and per-item source dimensions are not yet materialized.
- Chat intent analytics exist, but a durable chat-session-to-order identity bridge and recommendation-card events do not yet exist.
- The current admin competitor page covers competitor CRUD/verification; product, deal, and comparison management is available through the API but does not yet have a dedicated UI.

## Phase 3

Implemented and applied:

- Migration `0005_phase3_opportunity_system.sql` adds opportunities, immutable evidence snapshots, action history, comments, and AI generation logs with tenant indexes, bounded score constraints, and stable fingerprint uniqueness.
- Deterministic detectors cover menu-matrix leaks/hidden winners/weak items, search no-results, checkout drop/payment/minimum-order friction, basket bundles, campaign mismatch, chat objections, and approved competitor price gaps.
- Priority is bounded to 0-100 from impact, confidence, inverse effort, and urgency. Data-quality warnings/errors reduce confidence. Stable fingerprints deduplicate recurring findings, record trends, preserve terminal decisions, and expire absent active findings.
- `opportunities.detect_daily` and `opportunities.generate_weekly_cards` are durable jobs. Weekly AI explanations use aggregate evidence only, a provider abstraction, validated structured output, failure-safe disabled behavior without an API key, and complete generation audit logs.
- Admin APIs and `/admin/opportunities` support bounded listing/filtering, evidence detail, view history, comments, approve/dismiss transitions, row locking, conflict responses, and tenant-scoped audit records.
- The feature is protected by `opportunities.weekly_cards`; comment creation and manual job queueing have per-tenant hourly limits.

Live verification:

- Applied migrations `0004` and `0005` and confirmed `schema_migrations` contains `0000` through `0005`.
- Ran detection successfully. Low current data correctly produced zero fabricated opportunities.
- Exercised list, detail/view history, comment, approve, repeated-approve conflict (HTTP 409), and cleanup with a temporary opportunity.
- Backend tests: 48 passed. Python compilation and frontend production build passed. ESLint has 0 errors and 19 pre-existing warnings. Full `npm audit` reports 0 known vulnerabilities.

Residual Phase 3 boundaries:

- Opportunity conversion into experiments and missions is now implemented by Phases 4/5; target-specific editing after conversion remains in those dashboards.
- The OpenAI path is implemented but was not invoked during live verification, avoiding external data transfer and API cost.
- No implementation can guarantee the absence of every future defect. Remaining platform-level risks include browser token storage, lack of PostgreSQL RLS, process-local rate limits, and one database connection per dependency rather than pooled requests.

## Phase 4

Implemented and applied:

- Migration `0006_phase4_experiment_engine.sql` adds experiments, variants, sticky assignments, render-only exposures, authoritative outcomes, and evaluation results.
- Admin APIs/UI support create, inspect, approve, start, pause, and evaluate. Approved opportunities convert transactionally into reviewable experiments.
- Public APIs perform deterministic weighted assignment, allocation/audience checks, conflict exclusion, exposure idempotency, and tenant ownership validation.
- Evaluation attributes delivered orders after exposure, requires minimum sample per variant, uses Bonferroni-adjusted two-proportion confidence intervals, and enforces contribution-margin, refund-rate, and cancellation-rate guardrails.
- `ExperimentText` is the reusable frontend renderer; the home promo slot is the first integration.

## Phase 5

Implemented and applied:

- Migration `0007_phase5_first_missions.sql` adds customer profiles/segments, generic missions, audiences, guardrails, actions, holdouts, results/events, campaign messages, and delivery history.
- Admin APIs/UI support create, inspect, approve, start, pause, cancel, and evaluate. Approved opportunities convert transactionally into missions.
- Abandoned-cart recovery, intelligent bundle, and lapsed-customer win-back are implemented with deterministic eligibility, treatment/holdout assignment, incremental reporting, and emergency pause/cancel controls.
- Mock-only email/SMS/WhatsApp provider interfaces enforce contact, consent, suppression, frequency, mission-state, and customer eligibility checks before recording delivery.
- Customer profiles include reorder timing, lifetime value/margin, preferred categories/location/daypart, discount dependency, favorite-item evidence, and initial deterministic segments.

Verification:

- Applied migrations `0006`, `0007`, and hardening migration `0008`; `schema_migrations` contains `0000` through `0008`.
- Live experiment create/approve/start, sticky assignment, and idempotent exposure requests succeeded.
- A disposable consented abandoned cart produced a mock `SENT` delivery, treatment assignment, abandoned status, and result snapshot; all synthetic data was removed.
- Backend: 59 tests plus 4 subtests passed. Focused Ruff and mypy checks passed.
- Frontend production build passed; ESLint has 0 errors and 19 pre-existing warnings. Full npm audit reports 0 known vulnerabilities.

Boundaries:

- Phase 4 currently evaluates `order_conversion`; additional metric-specific statistical models can be added without changing assignment/exposure storage.
- Phase 5 has mock messaging only. Production provider credentials/webhooks are Phase 8 integration work.
- Phase 6 uses first-party capacity/order/menu/concept data only. Delivery-time provider integrations and paid acquisition cost imports remain later integrations.
- Platform-level RLS, browser token storage, edge rate limiting, and database connection pooling remain hardening work.

## Phase 6

Implemented and applied:

- Migration `0009_phase6_operational_missions.sql` adds capacity settings, inventory guardrails, quiet-hour candidates, product concepts, concept variants, interest events, waitlist entries, and preorder reservations.
- Quiet-hour demand missions evaluate historical quiet windows, capacity utilization, cancellation rate, margin-qualified inventory, live capacity, stock guardrails, maximum redemptions, and deterministic treatment/holdout assignment.
- New-product demand tests support concept pages that are explicitly labeled `COMING SOON`, `LIMITED TEST`, `PREORDER`, or `JOIN WAITLIST`; public APIs record interest, waitlist, and preorder intent without creating live menu orders.
- Admin UI now includes Operational Missions for capacity, inventory, and concept workflows. Public UI includes `/concepts` and a home-page quiet-hour banner integration.
- Scheduled/operator jobs include `missions.evaluate_quiet_hours` and `missions.evaluate_product_demand_tests`.

Verification:

- Applied migration `0009`; `schema_migrations` contains Phase 6.
- Transactional smoke test created synthetic capacity/menu/mission/concept data, detected a quiet-hour candidate, evaluated quiet-hour guardrails, recorded product-demand waitlist interest, generated product-demand mission metrics, and rolled all synthetic rows back.
- Backend: 64 tests plus 4 subtests passed. Focused Ruff `F,E9` checks passed on touched backend files.
- Frontend OpenAPI generation, production build, and ESLint passed. ESLint still reports 19 pre-existing warnings outside Phase 6 files.
- `npm audit --audit-level=high` passed; full audit still reports moderate transitive `js-yaml` advisories under `@redocly/openapi-core`.

## Phase 7

Implemented and applied:

- Migration `0010_phase7_8_advanced_conversion_scale.sql` adds Order Architect request/suggestion records, private offers, private offer redemptions, merchandising events, Demand Twin snapshots, benchmarks, integration accounts, queue health snapshots, and performance reviews.
- Public Order Architect endpoints build budget/dietary-aware suggestions from live menu availability and server prices; suggestions can also persist a server cart.
- Private offers are admin-managed, lifecycle-controlled, and validated server-side at checkout against tenant, subject, subtotal, maximum redemption, and minimum-margin guardrails.
- Personalized merchandising is backend-driven and rate-limited; it can return eligible private offers and first-party menu recommendations.
- Tenant Demand Twin snapshots use verified first-party aggregate tables only and suppress low-sample segments/source mixes by privacy threshold.
- Frontend includes `/order-architect`, a personalized merchandising home section, private-offer checkout input, and `/admin/advanced-conversion`.

Verification:

- Applied migration `0010`.
- Transactional smoke test created an Order Architect suggestion, validated a synthetic private offer, generated a Demand Twin snapshot, generated a privacy-thresholded benchmark snapshot, created a performance review, and rolled synthetic data back.
- Backend: 67 tests plus 4 subtests passed. Focused Ruff `F,E9` checks passed on touched backend files.
- Frontend OpenAPI generation, production build, and ESLint passed. ESLint still reports 19 pre-existing warnings outside Phase 7/8 files.

## Phase 8

Implemented and applied:

- Privacy-thresholded neighborhood benchmark snapshots return `INSUFFICIENT_PEERS` unless the peer threshold is met.
- Integration accounts support messaging and advertising provider configuration without storing raw secrets in the database; records store only a secret reference and settings.
- Messaging provider abstraction now supports mock by default and opt-in SendGrid/Twilio delivery via environment credentials. Missing or unsupported production configuration fails closed.
- Optional psycopg2 connection pooling can be enabled with `DB_POOL_ENABLED=true`, `DB_POOL_MIN_CONNECTIONS`, and `DB_POOL_MAX_CONNECTIONS`; the default remains the known safe per-operation connection mode.
- Queue health and performance review jobs capture pending/running/failed jobs, latency, pooling status, and partition review recommendations. Additional Phase 8 indexes were added for event/order/job review paths.
- Admin UI includes `/admin/scale-integrations` for benchmark, performance, and integration account workflows.

Verification:

- Same `0010` migration and transactional smoke test covered benchmark/performance generation.
- `npm audit --audit-level=high` passed; full audit still reports moderate transitive `js-yaml` advisories under `@redocly/openapi-core`.

Boundaries:

- Production messaging is implemented as opt-in provider scaffolding; no real send occurs unless provider environment variables are configured.
- Advertising integrations are account/test scaffolding only; campaign import/export adapters remain future provider-specific work.
- Database partitioning is reviewed and indexed, not automatically converted, because repartitioning existing live tables is a dedicated operational migration.
