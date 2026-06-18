# ORDER — Security Remediation Status

This documents the fixes applied in response to the multi-tenant SaaS audit, how to
deploy them, and the items that still require action outside the repository.

## How to deploy these changes

1. **Apply the new migrations** with the database **owner/superuser** DSN
   (0011 = tenant/user status, real plans, subscriptions, domain verification, order
   idempotency, durable auth throttling, invitations; 0012 = Row-Level Security;
   0013 = chat_sessions table for the AI chatbot):
   ```bash
   cd backend
   DATABASE_URL=<owner-dsn> python scripts/migrate.py --dry-run   # review
   DATABASE_URL=<owner-dsn> python scripts/migrate.py             # apply 0011–0013
   ```
   Both migrations are idempotent. 0011's app-level code degrades gracefully if it runs
   before the migration; 0012 is a no-op for the app until you cut the runtime over to
   the `order_app` role (step 5).

   > Note: run migrations, seeds, and the `scripts/*` admin tooling with the **owner**
   > DSN. Only the running web app + `scripts/worker.py` use the `order_app` DSN.

2. **Set production environment variables** (backend):
   - `APP_ENV=production` — **critical**. Hard-disables the `X-Restaurant-ID` dev header,
     the `DEFAULT_RESTAURANT_ID` fallback, and any cross-tenant token tolerance.
   - `TRUST_FORWARDED_HOST=true` — **only** if the backend sits behind a trusted proxy /
     platform rewrite that forwards the original customer host in `X-Forwarded-Host`
     (Vercel, Cloudflare, nginx). Required for custom-domain tenant resolution.
   - `AUTH_RATE_LIMIT_PER_MINUTE` (default 10), `PLATFORM_DOMAIN_TARGET` (CNAME shown in
     domain setup instructions).

3. **Install the new dependency**: `pip install -r backend/requirements.txt` (adds
   `dnspython` for DNS TXT verification).

4. **Point the frontend `/api` rewrite at the real backend host** in
   `frontend/vercel.json` (replace `REPLACE_WITH_BACKEND_HOST`).

5. **Cut the runtime over to the non-bypass `order_app` role** (this is what turns
   RLS on). Migration 0012 created the role with `NOLOGIN` and no password so no secret
   lives in the repo. On the database (owner connection):
   ```sql
   ALTER ROLE order_app WITH LOGIN PASSWORD '<strong-secret>';
   ```
   Then set the running app's (and worker's) `DATABASE_URL` to connect as `order_app`.
   Because `order_app` lacks `BYPASSRLS`, the database now enforces tenant isolation;
   until you switch, the code still runs correctly as the owner (RLS simply inactive),
   so the cutover is safe to do last and to roll back by repointing `DATABASE_URL`.

   Verify with the bundled proof (skips unless both DSNs are set):
   ```bash
   RLS_OWNER_DSN=<owner-dsn> RLS_APP_DSN=<order_app-dsn> \
     python -m pytest tests/test_rls_isolation.py -v
   ```

## Fixed in this pass (code)

| Area | What changed | Files |
|---|---|---|
| Prod tenant safety | Dev tenant header / default-tenant fallback / cross-tenant token tolerance are hard-disabled in production (`APP_ENV` **or** `ENVIRONMENT`). Local/empty host is refused in prod. | `dependencies/auth.py` |
| Host propagation | Tenant hostname read from `X-Forwarded-Host` when `TRUST_FORWARDED_HOST` is set, fixing custom-domain routing behind a proxy. Header is ignored when not trusted (no spoofing). | `dependencies/auth.py` |
| Realtime PII leak | Removed the browser Supabase Realtime subscription on `orders`; live updates now poll the tenant-scoped admin API. | `frontend/.../AdminCurrentOrders.tsx` |
| Login brute-force | Durable, multi-instance per-(scope, IP, account) throttle on customer/admin/platform login. | `services/rate_limits.py`, `routers/auth.py`, `routers/admin.py`, `routers/platform_admin.py` |
| User/tenant lifecycle | Disabled admins and suspended/cancelled restaurants lose admin access immediately; suspended tenants' public storefronts go offline. Last-login stamped. | migration 0011, `dependencies/auth.py`, `routers/admin.py` |
| Domain verification | New/added domains are **unverified by default** with a verification token; DNS-TXT and HTTP well-known proofs; `/verify` endpoint flips `verified` only on real proof. | migration 0011, `services/domains.py`, `routers/platform_admin.py` |
| Subscription plans | Three real **priced** plans (Starter/Growth/Pro) with currency, monthly/annual price, trial; `subscriptions` state machine; plan assignment + plan history; new tenants start on a Starter trial. | migration 0011, `routers/platform_admin.py` |
| Tenant lifecycle admin | Super-admin `PATCH /tenants/{id}/status` (active/trialing/suspended/cancelled), `GET /plans`, `POST /tenants/{id}/plan`, `GET /tenants/{id}/subscription`. | `routers/platform_admin.py` |
| Order idempotency | `idempotencyKey` on order creation; duplicate submissions return the original order (unique per tenant). | migration 0011, `routers/orders.py` |
| CORS | Removed invalid wildcard `Access-Control-Allow-Origin: *` on `/api/*` (calls are same-origin via the rewrite). | `frontend/vercel.json` |

Tests added: `backend/tests/test_security_hardening.py` (production fail-closed, forwarded-host
trust, token tenant binding, suspended-tenant storefront block). Existing tenancy tests still pass.

## CRITICAL — must be done outside the repo (cannot be fixed in code)

1. **Rotate every secret that was present in `backend/.env`.** These are live and were
   exposed: Supabase DB password, `SUPABASE_SERVICE_KEY`, `OPENAI_API_KEY`, `JWT_SECRET`,
   and the seed admin/platform passwords. Rotate all of them, then store secrets in the
   host's secret manager — never in a working-tree `.env`. (Rotating `JWT_SECRET`
   invalidates existing tokens, forcing re-login — acceptable.)
2. **Confirm Supabase Realtime / RLS posture.** Even with the frontend subscription removed,
   verify that Realtime is **not** publishing the `orders` (or other tenant) tables to the
   anon role, since the anon key is public. Prefer enabling RLS (see below) or disabling
   Realtime for tenant tables.
3. **Custom-domain TLS** must be provisioned by the edge/platform (Vercel custom domains,
   Cloudflare for SaaS, or Caddy on-demand TLS). The app verifies *ownership*; it does not
   issue certificates.

## Database Row-Level Security — IMPLEMENTED (migration 0012)

Tenant isolation is now enforced by the database itself, not just by `WHERE` clauses:

- Migration `0012_row_level_security.sql` creates a `NOBYPASSRLS` app role (`order_app`),
  an `app` helper schema (`app.current_tenant()`, `app.is_platform()`), and — via a loop
  over every table with a `restaurant_id`/`tenant_id` column — enables **forced** RLS with
  a `USING (tenant_col = app.current_tenant() OR app.is_platform())` policy (96 tables).
  Bootstrap/reference tables (`restaurants`, `domains`, `platform_admins`, `plans`, …) get
  read-open / platform-write policies; `order_claims` is scoped through its parent order.
- `db.py` applies the per-request context as session GUCs (`app.tenant_id` / `app.is_platform`)
  on every connection. `TenantContextMiddleware` (in `main.py`, pure-ASGI so the context
  reliably propagates into the sync threadpool) sets the tenant from the request host (or dev
  header) for normal routes and platform mode for `/api/platform-admin/*`. The worker claims
  jobs cross-tenant then narrows to each job's tenant.
- With no context, **zero** tenant rows are visible (fail-safe deny). Proven end-to-end as the
  `order_app` role: unscoped `SELECT * FROM orders` returns only the current tenant; cross-tenant
  reads return nothing; cross-tenant writes are rejected by the policy; platform context sees all.
  Regression-locked by `tests/test_rls_isolation.py`.

## AI features — verified

Three AI features exist; all now work end-to-end and are tenant-isolated:

- **AI chatbot** (`routers/chatbot.py`, `POST /api/chat`): real OpenAI function-calling
  order assistant. It was **broken on a clean deploy** because the `chat_sessions` table
  it uses was never created by any migration — fixed by `0013_chat_sessions.sql` (table +
  RLS + index). It is now **plan-gated** by `ai.chatbot` (graceful "unavailable" response,
  not an error, when disabled) and **usage-metered** against the plan's AI allowance.
  Order placement **re-prices server-side** from `menu_items` and ignores the model's
  claimed prices. Proven end-to-end under RLS: a bogus $0.01 unit price from the model
  produced a correct $20.00 order; a non-entitled tenant was gated; sessions/orders stayed
  tenant-isolated. Throttled per-tenant and per-session before any OpenAI spend.
- **Order Architect** (`routers/advanced_conversion.py`, `POST /api/v1/order-architect/*`):
  deterministic recommendation engine gated by `conversion.order_architect`; returns
  `COMPLETED` with structured items when enabled, `DISABLED` otherwise; rate-limited.
- **Opportunity cards** (`services/ai/provider.py` + `services/opportunities.py`): real
  OpenAI **structured-output** generation with Pydantic validation, evidence hashing, token
  accounting, and logging to `ai_generation_logs`. Falls back to a `DisabledAIProvider`
  (validation `skipped`) when `OPENAI_API_KEY` is absent — no crash, no silent failure.

Regression-locked by `tests/test_chatbot_gate.py` (gate/metering) and the existing
`tests/test_phase7_8_advanced_conversion.py` (order architect) / opportunity tests.

Note: the only AI dependency is `OPENAI_API_KEY`. Set it in the backend environment;
without it the chatbot returns its graceful message and opportunity generation is skipped.

## Remaining hardening

- **Plan gating of core features.** The entitlement engine is wired, but existing tenants are
  still mapped to the all-disabled `legacy` plan. Migrate existing tenants onto real plans
  *before* enforcing `core.online_ordering` / `core.menu_items` / `core.admin_seats` /
  `core.custom_domain`, otherwise live tenants would lose function.
- **Full RBAC matrix.** `require_tenant_role` and per-account status enforcement now exist;
  applying a complete owner/manager/staff/read-only matrix to every admin route needs the
  role taxonomy defined as a product decision.
- **Invitation flow.** The `admin_invitations` table exists; the create/accept endpoints
  (single-use, expiring token; owner sets their own password) still need to be wired to
  replace plaintext-password tenant onboarding.
- **Billing integration** (Stripe webhooks w/ signature + idempotency), Redis for hot
  counters/cache, object storage + CDN for uploads, async retryable email, monitoring/error
  tracking, backups, and load testing remain infrastructure work.
