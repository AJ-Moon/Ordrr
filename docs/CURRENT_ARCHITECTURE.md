# Current Architecture

## Repository shape

This workspace contains one application split into `backend/` and `frontend/`. It is not a conventional monorepo: there is no workspace-level package manager, Python project file, CI configuration, or project-scoped Git repository.

## Backend

- Framework: FastAPI. `requirements.txt` permits FastAPI 0.111 or newer; the available system runtime has FastAPI 0.136.1 and Pydantic 2.11.9.
- Runtime: Python 3.12.
- Entry point: `backend/main.py`.
- API organization: synchronous route modules under `backend/routers/` mounted below `/api`; new revenue-operator contracts are versioned below `/api/v1`.
- Database: PostgreSQL, apparently Supabase-hosted in the current environment.
- Data access: direct synchronous `psycopg2` SQL. There is no ORM, repository layer, or Alembic installation. Phase 8 adds optional psycopg2 pooling controlled by environment variables; the default remains fresh per-operation connections.
- Migrations: no prior migration system. Phase 0 adds ordered SQL migrations and `backend/scripts/migrate.py`.
- Configuration: environment variables loaded with `python-dotenv`.

## Frontend

- Framework: React 19 with React Router 7.
- Build: Vite 6, TypeScript 5.6, Tailwind CSS 4.
- State: React contexts for restaurant presentation, authentication, and cart state.
- API access: browser requests to relative `/api` paths; Vite proxies these to FastAPI in development.
- Supabase: the browser client is used for realtime order updates. It is not the primary authentication system.

## Authentication and authorization

- Customer, restaurant-admin, and platform-admin accounts are stored in PostgreSQL.
- Passwords use bcrypt.
- FastAPI issues custom HS256 JWTs using `JWT_SECRET`.
- Customer and admin JWTs contain `restaurant_id`; platform-admin JWTs are global.
- Phase 0 centralizes JWT verification and rejects tenant/domain mismatches.
- There is no token revocation, refresh-token rotation, MFA, or external identity provider integration.

## Tenant resolution and domain routing

- `domains` maps verified hostnames to `restaurants`.
- Public requests resolve a tenant from the HTTP host.
- Local development may use `X-Restaurant-ID` when `ALLOW_DEV_TENANT_HEADER=true`.
- Production no longer falls back to restaurant `1` for unknown domains.
- Existing tenant-owned SQL is generally filtered by `restaurant_id`; PostgreSQL RLS is not present.

## Cart and order flow

- The cart is browser state managed by `CartContext` and synchronized to normalized server cart tables.
- Checkout posts cart lines to `POST /api/orders/`.
- FastAPI reloads menu availability and prices, validates checkout eligibility, and owns delivery/reward calculations.
- Orders dual-write legacy JSONB/decimals and normalized immutable integer-money snapshots for compatibility.

## Theme and customer website

- `theme_settings` and `settings` drive tenant branding and public presentation.
- The frontend loads `/api/theme` and `/api/settings` at startup.
- Uploaded media is stored on the backend filesystem under `backend/static/uploads`.

## Analytics and chatbot

- Phase 1 provides a canonical event store, first-party visitor/session IDs, initial attribution, daily aggregates, and data-quality checks.
- The chatbot is a synchronous FastAPI route that calls OpenAI with `httpx` and can create orders.
- Chat messages are not yet retained/classified through a privacy-controlled analytics pipeline.

## Queue and scheduled jobs

- A PostgreSQL `job_runs` queue provides durability, idempotency, retry state, `SKIP LOCKED` workers, scheduling, and tenant admin visibility. Redis can be introduced when throughput justifies another operational dependency.
- OpenAI and other heavy work currently occurs inside HTTP request handling.

## Existing integrations

- Supabase browser client for realtime database subscriptions.
- OpenAI for menu parsing and chatbot responses.
- Mapbox search for delivery address UX.
- Mock messaging by default; optional SendGrid email and Twilio SMS/WhatsApp providers are available when explicitly configured. Advertising has tenant integration-account scaffolding, but no provider-specific campaign adapter yet.

## Testing and CI

- `TESTING.md` is a manual test guide.
- No automated backend/frontend test suite or CI workflow existed before Phase 0.
- No lint/type-check configuration existed for Python.

## Security and reliability risks

1. Sync database calls and AI calls can block request workers.
2. Legacy decimal fields remain during dual-write compatibility and need a later removal plan.
3. JWTs have no revocation or refresh lifecycle.
4. Browser tokens are stored in `localStorage`, increasing XSS impact.
5. Direct Supabase realtime access needs verified RLS policies; none are represented in the schema dump.
6. Database connections are opened per operation unless `DB_POOL_ENABLED=true`; pooling still needs production sizing and monitoring.
7. Backup/data SQL files and local `.env` files require strict exclusion from source control and artifact publishing.
8. Uploaded files live on ephemeral local disk and are not malware-scanned.
9. The global exception handler suppresses diagnostic correlation IDs and structured logging.

## Foundations added in Phase 0

- Strict hostname tenant resolution with development-only header selection.
- Shared customer/admin/platform-admin dependencies and tenant-role dependency factory.
- Feature definitions, plans, entitlements, overrides, and usage tables/services.
- Tenant-scoped audit log table, service, API, and writes on key commercial/admin mutations.
- Customer, identity, channel consent, and communication suppression tables.
- Customer self-service consent APIs.
- Versioned SQL migration runner.

## Missing foundations

Automated database/end-to-end tests, provider-specific advertising adapters, secure browser token strategy, token revocation, RLS verification, structured security logging, and production partition operations remain hardening work.
