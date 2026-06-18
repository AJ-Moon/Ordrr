# Operations Runbook

## Migrations

From `backend/`, load the intended environment and run:

```bash
python scripts/migrate.py --dry-run
python scripts/migrate.py
```

Take a PostgreSQL backup first. Migrations are not applied automatically by the web process.

## Application checks

```bash
python3 -m compileall -q backend
(cd backend && python3 -m unittest discover -s tests -p 'test_*.py' -v)
(cd frontend && npm run build)
(cd frontend && npm run lint)
```

The checked-in `backend/.venv` may not match the current machine. Rebuild it from `requirements.txt` if its native packages fail to import.

## Jobs and schedules

Phase 1 uses PostgreSQL `job_runs` as both durable queue and execution ledger. Run one or more workers:

```bash
cd backend
python3 scripts/worker.py
```

Call the scheduler hourly from cron or the deployment scheduler. Idempotency keys make repeated invocations safe:

```bash
cd backend
python3 scripts/schedule_jobs.py
```

Use `python3 scripts/worker.py --once` for a single queued job. Restaurant admins can inspect and enqueue allowlisted jobs at `/admin/operations`; queueing does not execute work unless a worker is running.

Phase 2/3 jobs include:

- `analytics.aggregate_daily`: daily rollups plus customer, chat, basket, and menu-matrix refresh.
- `analytics.refresh_menu_matrix`: refresh persisted item classifications directly.
- `opportunities.detect_daily`: deterministic detection and lifecycle refresh.
- `opportunities.generate_weekly_cards`: detection plus bounded AI explanation generation; scheduled on Mondays.
- `experiments.evaluate`: materialize post-exposure order outcomes and guarded statistical results.
- `customers.refresh_segments`: refresh deterministic customer profiles and segment memberships.
- `missions.evaluate_abandoned_carts`, `missions.evaluate_bundles`, `missions.evaluate_lapsed_customers`: execute/measure the first missions.
- `missions.monitor_running`: complete expired missions and refresh results.

Manual admin queue requests default to 20 per tenant/hour (`ADMIN_JOB_RATE_LIMIT_PER_HOUR`). The opportunity detector defaults to a 30-day window, 50 candidates, and 8 weekly AI cards. See `backend/.env.example` for all bounds. Without `OPENAI_API_KEY`, weekly card generation logs a disabled result and leaves deterministic opportunities usable.

Keep `MESSAGING_PROVIDER=mock` until a later production provider implementation has credentials, webhook verification, delivery reconciliation, and operational approval. Phase 5 intentionally fails closed for any other provider value.

## Retention and event limits

- `EVENT_BATCH_MAX_BYTES` defaults to 262144.
- `EVENT_RATE_LIMIT_PER_MINUTE` defaults to 3000 per tenant.
- `RAW_EVENT_RETENTION_DAYS` defaults to 400 and cannot be set below 30 by the worker.
- `CHAT_CONTENT_RETENTION_DAYS` defaults to 90.
- `ABANDONED_CART_MINUTES` defaults to 30 and cannot be set below 10.
- Opportunity comments are limited to 30 per tenant/admin hour and 2,000 characters each.

## Demo data

`backend/scripts/seed_demo.py` populates a deterministic demo dataset for an
existing tenant so every revenue-operator dashboard shows live data. It seeds
realistic ingredient/packaging costs, ~28 days of analytics events, carts (incl.
abandoned), completed (`delivered`) orders with line-item margin snapshots,
search queries (incl. zero-result), competitors/products/deals/comparison, one
controlled experiment, and one of each first-phase mission — then runs the real
aggregation + opportunity-detection job handlers. It is engineered so one item
reads as LEAKING (high attention, weak add-to-cart) and one as HIDDEN_WINNER
(low attention, strong conversion).

```
cd backend && python -m scripts.seed_demo --tenant 1 --days 28
```

The seed is idempotent: events/orders use deterministic ids with
`ON CONFLICT DO NOTHING`, and competitors/experiments/missions are skipped when a
same-named entity already exists. Event inserts are batched with
`execute_values` (one round-trip per day) to stay fast and cheap against a remote
database. Never point it at a production tenant that holds real customer data.

## Tenant incident

Disable the affected domain or admin account, preserve audit logs, rotate `JWT_SECRET` if token integrity is in doubt, and inspect all tenant-scoped mutations. A secret rotation invalidates every existing JWT.

## Database incident

The API returns 503 for database connectivity errors. Verify `DATABASE_URL`, SSL mode, Supabase/PostgreSQL availability, connection limits, and recent migrations before restarting application processes.
