# API Contract

## Existing compatibility APIs

The current customer and admin application continues to use `/api/auth`, `/api/menu`, `/api/orders`, `/api/admin`, `/api/platform-admin`, `/api/theme`, `/api/chat`, and related routes.

## Versioned APIs

- `GET /api/v1/admin/features`: effective tenant entitlements. Requires a restaurant-admin JWT.
- `GET /api/v1/admin/audit-logs?limit=100`: tenant-scoped audit records. Requires a restaurant-admin JWT.
- `GET /api/v1/customers/me/consents`: current customer's channel consents.
- `PUT /api/v1/customers/me/consents`: upsert one to four channel consent records.
- `GET /api/v1/customers/me/export`: export the authenticated customer's profile, consent, and order data.
- `DELETE /api/v1/customers/me`: anonymize the authenticated customer after the body confirms `{"confirmation":"DELETE"}`.
- `POST /api/v1/events/batch`: accept up to 100 canonical browser events with per-event accepted, duplicate, or rejected results.
- `POST /api/v1/carts/sync`: price and persist a browser cart from authoritative menu records.
- `GET /api/v1/admin/jobs`: list tenant-scoped durable jobs.
- `POST /api/v1/admin/jobs/{job_name}/run`: enqueue an allowlisted job, subject to a per-tenant hourly limit.
- `GET /api/v1/data-quality`: return the latest tenant-scoped quality checks.

### Phase 2: analytics and competitors

All endpoints below require a restaurant-admin JWT and are scoped to the admin's tenant. `from`/`to` query parameters are ISO dates (default: last 30 days, max range 366 days).

- `GET /api/v1/analytics/overview?from&to`: tenant-wide funnel totals, revenue, contribution margin, and conversion rate.
- `GET /api/v1/analytics/items?from&to&category&itemId&limit`: item funnel, persisted menu-matrix classification, baselines, unique-session counts, checkout/purchase rates, discounts, refunds, revenue, and margin.
- `GET /api/v1/analytics/funnel?from&to`: daily funnel series (sessions through completed orders and revenue).
- `GET /api/v1/analytics/search?from&to&limit`: search gaps grouped by normalized query, ordered by zero-result searches.
- `GET /api/v1/analytics/checkout?from&to`: checkout friction by step, with drop-off rate.
- `GET /api/v1/analytics/sources?from&to&source&medium` and `GET /api/v1/analytics/acquisition`: acquisition/campaign conversion by source/medium/campaign.
- `GET /api/v1/analytics/chat?from&to` and `GET /api/v1/analytics/chatbot`: chat intents with message, recommendation, click, and linked-order counts where available.
- `GET /api/v1/analytics/baskets?limit`: most recent basket-association window, item pairs ranked by lift.
- `GET /api/v1/analytics/customers?from&to`: new vs. returning customer segments with order count and revenue.
- `GET /api/v1/competitors`: list tenant competitors.
- `POST /api/v1/competitors`: create a competitor (name, website, address, notes, currency, reference item/price, status).
- `PUT /api/v1/competitors/{id}`: update a competitor; changing the reference price updates `observedAt`.
- `DELETE /api/v1/competitors/{id}`: remove a competitor.
- `POST /api/v1/competitors/{id}/verify`: mark a competitor's data as freshly verified.
- `GET|POST /api/v1/competitors/products`: list or create tenant-scoped competitor products.
- `GET|POST /api/v1/competitors/deals`: list or create tenant-scoped competitor deals.
- `GET|POST /api/v1/competitors/comparisons`: list or create normalized own-item-to-competitor-product comparisons.
- `POST /api/v1/competitors/comparisons/{id}/approve`: human-approve a comparison before it can feed opportunity detection.

All Phase 2 endpoints require their matching feature entitlement. List limits are bounded server-side; item results allow at most 500 rows and competitor nested-resource results allow at most 200.

### Phase 3: opportunities

All endpoints require restaurant-admin authentication and the `opportunities.weekly_cards` entitlement.

- `GET /api/v1/opportunities?status&opportunityType&limit&offset`: bounded tenant-scoped cards ordered by priority.
- `GET /api/v1/opportunities/{id}`: card, evidence snapshots, action history, and comments; records a view action.
- `POST /api/v1/opportunities/{id}/approve`: atomically approve an active recommendation and write action/audit history.
- `POST /api/v1/opportunities/{id}/dismiss`: atomically dismiss an active recommendation with an optional reason.
- `POST /api/v1/opportunities/{id}/comments`: add a comment of at most 2,000 characters, limited to 30 comments per tenant/admin hour.

Repeated or invalid terminal transitions return HTTP 409. Unknown tenant-owned resources return 404 rather than crossing tenant boundaries.

### Phase 4: experiments

- `GET|POST /api/v1/experiments`: bounded tenant list or create an experiment with 2-10 weighted variants and exactly one control.
- `GET /api/v1/experiments/{id}`: configuration, variants, and latest evaluation.
- `POST /api/v1/experiments/{id}/approve|start|pause|evaluate`: guarded lifecycle/evaluation actions.
- `POST /api/v1/experiment-assignments/active`: public active assignment by placement and visitor.
- `POST /api/v1/experiments/{id}/assignment`: public assignment for a known experiment.
- `POST /api/v1/experiments/{id}/exposure`: idempotent render exposure for a matching active assignment.
- `POST /api/v1/opportunities/{id}/create-experiment`: convert one approved opportunity transactionally.

### Phase 5: missions

- `GET|POST /api/v1/missions`: bounded tenant list or create an entitled Phase 5 mission.
- `GET /api/v1/missions/{id}`: configuration, actions, and latest incremental result.
- `POST /api/v1/missions/{id}/approve|start|pause|cancel|evaluate`: guarded lifecycle/evaluation actions.
- `POST /api/v1/mission-assignments/bundle`: public, margin-qualified intelligent-bundle assignment with deterministic holdout.
- `POST /api/v1/opportunities/{id}/create-mission`: convert one approved opportunity transactionally.

Experiment/mission IDs supplied through browser analytics are checked for tenant ownership; variant IDs must belong to the supplied experiment.

The analytics endpoints read from the Phase 1/2 daily aggregate tables and do not support a `locationId` filter — `aggregate_daily` only writes tenant-wide (`location_id = 0`) rollups, so all results are tenant-wide. `daily_chat_metrics` and `daily_customer_metrics` are populated by `analytics.aggregate_daily`; `basket_associations` is recomputed over a rolling window (`BASKET_ASSOCIATION_WINDOW_DAYS`, default 90 days, minimum 7).

Consent body:

```json
{
  "consents": [
    {"channel": "email", "status": "granted", "source": "account_settings", "policyVersion": "1"}
  ]
}
```

Event ingestion is limited by payload size, batch count, timestamp age, tenant ownership, and a per-tenant minute window. Server event names cannot be submitted through the browser endpoint.

All tenant-owned authenticated requests are checked against the verified request domain. `X-Restaurant-ID` is accepted only for local development when explicitly enabled. Experiment and mission conversion endpoints remain later-phase work.
