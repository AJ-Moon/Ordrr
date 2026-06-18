# Security Model

- Public tenant context comes from a verified domain record. Unknown production domains return 404.
- Local tenant selection requires `ALLOW_DEV_TENANT_HEADER=true`; never enable it on an internet-facing deployment.
- Customer and restaurant-admin JWT tenant claims must match explicit domain/header tenant context.
- Platform-admin endpoints use a separate token type.
- Every tenant query must include `tenant_id`/`restaurant_id`; PostgreSQL RLS is not currently available as a second boundary.
- Entitlements are enforced by backend dependencies/services, never only by hidden navigation.
- Every Phase 2 analytics/competitor endpoint and every Phase 3 opportunity endpoint has a server-side entitlement dependency.
- Audit records are append-only at the application layer and tenant-scoped on read.
- Order and cart prices, availability, costs, totals, and margin are loaded and calculated by FastAPI. Client and chatbot price/name fields are compatibility hints only.
- Browser analytics may submit only the client event allowlist. Order lifecycle and other server events are emitted inside the same database transaction as the authoritative change.
- Event entity IDs are checked for tenant ownership before insertion; event IDs are tenant-scoped deduplication keys.
- Opportunity writes use tenant predicates and row locks; invalid repeated terminal transitions return 409 and all views/decisions/comments are recorded.
- AI explanation input is restricted to aggregate evidence fixed by deterministic detectors. Structured output is validated and every generation attempt is logged; AI cannot approve or execute an action.
- Experiment assignment is server-owned, sticky, allocation-bounded, conflict-aware, and tenant-scoped. Exposure requires a matching active assignment and an idempotency key.
- Mission actions require human approval/start, deterministic eligibility and holdout assignment, mission state, contact, consent, suppression, frequency, and configured capacity checks.
- Messaging is mock by default. Phase 8 production providers are opt-in through environment credentials and fail closed when configuration is missing or unsupported.
- Private offers are validated by FastAPI at checkout against tenant, subject, redemption limit, subtotal, and contribution-margin guardrails. Browser-entered offer codes are not authoritative.
- Demand Twin and benchmark snapshots use aggregate first-party tables and privacy thresholds; benchmark snapshots return `INSUFFICIENT_PEERS` instead of exposing low-peer metrics.
- Public experiment/mission assignment and exposure endpoints have database-backed per-tenant minute limits and bounded JSON payloads.
- The public AI chat endpoint (`POST /api/chat`) is throttled before any OpenAI spend by a per-tenant ceiling (`CHATBOT_RATE_LIMIT_PER_MINUTE`, default 120) and a tighter per-session cap (`CHATBOT_SESSION_RATE_LIMIT_PER_MINUTE`, default 15), bounding cost/abuse.
- Rate-limit window tables (`event_ingestion_windows`, `intervention_request_windows`) are pruned hourly by the `privacy.expire_old_raw_events` job so they cannot grow without bound.
- API date/list sizes, event ingestion, manual job queueing, and opportunity comments are bounded. Current application rate windows are database-backed but are not a substitute for an edge/global limiter.
- Secrets belong only in environment variables. SQL backups, `.env`, JWT secrets, service keys, and customer exports must not enter source control.

Immediate hardening still required: Supabase RLS verification, secure browser token strategy, token revocation/rotation, distributed/global request rate limiting, production DB pool sizing, structured security logs, automated cross-tenant database integration tests, and provider-specific advertising security review.
