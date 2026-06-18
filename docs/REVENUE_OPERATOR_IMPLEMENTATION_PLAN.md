# Revenue Operator Implementation Plan

## Principles

- FastAPI remains authoritative for tenant access, prices, eligibility, financial results, and intervention decisions.
- Existing customer website, admin workflows, and route contracts remain compatible while versioned `/api/v1` APIs are introduced.
- Direct SQL remains temporarily; repository boundaries are added before considering an ORM migration.
- Each phase requires schema, backend logic, authorization, frontend behavior, tests, and updated status documentation.

## Phase 0: inspection and security

Status: implemented in code; database migration and live integration tests remain environment-dependent.

- Strict tenant dependencies and cross-tenant token checks.
- Feature entitlement schema and service.
- Audit log schema/service plus key mutation logging.
- Customer identity, consent, and suppression foundation.
- Versioned Phase 0 APIs and documentation.

Migration: `0001_phase0_security_foundation.sql`.

## Phase 1: event and commerce foundation

Status: implemented in code; migrations and live database integration remain environment-dependent.

- Normalize carts, cart lines, order items, price/cost snapshots, and integer monetary columns.
- Make order creation load menu prices and availability from PostgreSQL.
- Add canonical `analytics_events`, server-event outbox, visitor/session identity, batch ingestion, deduplication, limits, and frontend tracker.
- Add one durable worker framework, `job_runs`, scheduled aggregation, retention, and job admin UI. The implementation uses PostgreSQL `FOR UPDATE SKIP LOCKED` to avoid adding Redis before queue throughput requires it.
- Add raw-event and chat-content retention controls and data-quality checks.

Compatibility risk: existing JSONB order items and float-valued frontend contracts require dual-read/dual-write migration.

Migration: `0002_phase1_event_commerce_foundation.sql`.

## Phase 2: analytics MVP

Status: implemented, hardened, migrated, and verified against the live database.

Dependencies: reliable events and authoritative order links.

- Daily item/funnel/search/checkout/source/chat/customer aggregate tables.
- Item funnel and menu matrix.
- Search gaps, checkout friction, acquisition/campaign conversion, chat objections, and basket associations.
- Manual competitor CRUD and verification.
- Dashboard pages with date/source filters and honest empty states.

Migration: `0003_phase2_analytics_competitors.sql`.

Hardening migration: `0004_phase2_hardening.sql` adds persisted menu classifications, richer aggregate columns, basket candidates, and normalized competitor products/deals/comparisons. Phase 2 APIs now enforce entitlements and bounded result sizes.

Known limitations: rollups remain tenant-wide (`location_id = 0`), chat sessions are not durably linked to orders, and normalized competitor subresources do not yet have a dedicated admin UI.

## Phase 3: opportunity system

Status: implemented, migrated, and live-smoke-tested.

- Deterministic detectors, evidence snapshots, confidence/data-quality penalties, scoring, lifecycle, and weekly cards.
- OpenAI provider abstraction only for explanations after evidence is fixed.
- Opportunity list/detail/comment/approval/dismissal APIs and admin UI.

Migration: `0005_phase3_opportunity_system.sql`.

Experiment/mission conversion is implemented by Phases 4/5. The OpenAI code path is implemented with validated structured output and audit logs, but live verification did not send data to OpenAI or incur API cost.

## Phase 4: experiments

Status: implemented, migrated, and live-smoke-tested.

- Experiment/variant/assignment/exposure/outcome schema.
- Sticky backend assignment, mutually exclusive conflict groups, frontend rendering abstraction, and evaluation jobs.
- Guardrails for sample size, margin, refunds, and operational outcomes.

Migration: `0006_phase4_experiment_engine.sql`.

The first statistical model is binary order conversion using adjusted two-proportion confidence intervals. The schema and result JSON support later metric-specific evaluators.

## Phase 5: first missions

Status: implemented, migrated, and live-smoke-tested.

- Generic mission/actions/executions/holdouts schema.
- Mock messaging adapter and message delivery ledger.
- Abandoned cart, bundle, and lapsed-customer workflows with approvals and holdout reporting.

Migration: `0007_phase5_first_missions.sql`.

Only the mock messaging provider is enabled. Production delivery providers remain an explicit later integration.

Shared hardening migration: `0008_phase45_hardening.sql` adds database-backed per-tenant public assignment/exposure rate windows.

## Phase 6: operational missions

Status: implemented, migrated, and live-smoke-tested.

- Quiet-hour capacity settings, candidate detection, live capacity pause, stock guardrails, public banner assignment, and incremental reporting.
- Inventory guardrails for constrained/low-stock menu items used by operational missions.
- New-product concepts, variants, public concept pages, qualified interest, waitlist, preorder reservation, and demand-test reporting.

Migration: `0009_phase6_operational_missions.sql`.

## Phase 7: advanced conversion

Status: implemented, migrated, and live-smoke-tested.

- Order Architect with budget/dietary constraints and server-validated carts.
- Private offers, server-side checkout validation, redemption records, and backend-driven personalized merchandising.
- Tenant Demand Twin snapshot based only on verified first-party aggregates.

## Phase 8: future scale

Status: implemented, migrated, and live-smoke-tested.

- Privacy-thresholded neighborhood benchmark scaffolding.
- Production messaging and advertising integration account scaffolding; SendGrid/Twilio providers are opt-in and fail closed without credentials.
- Queue health snapshots, optional psycopg2 connection pooling, partition/index review, and performance review records.

Migration: `0010_phase7_8_advanced_conversion_scale.sql`.

## API and frontend type strategy

FastAPI OpenAPI is the source of truth. Add an OpenAPI TypeScript generator in Phase 1, commit generated types, and make CI fail when generated output is stale.

## Test strategy

- Unit: tenancy, money, attribution, funnels, scoring, assignment, consent, guardrails.
- Integration: cross-tenant access, event deduplication, server events, jobs, opportunity/experiment/mission transitions.
- Frontend: empty states, approvals, assignments, error handling, route protection.
- End-to-end: tenant isolation and complete order-to-measurement workflows using synthetic demo data.

## Migration controls

- Apply ordered SQL with `backend/scripts/migrate.py` under an advisory lock.
- Back up before destructive changes.
- Prefer additive columns/tables and dual reads before removing legacy fields.
- Do not apply migrations automatically at web-process startup.
