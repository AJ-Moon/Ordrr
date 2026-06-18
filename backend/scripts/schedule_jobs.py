#!/usr/bin/env python3
from datetime import datetime, timezone

from db import get_db
from services.jobs import enqueue_job


def main() -> None:
    now = datetime.now(timezone.utc)
    daily_key = now.strftime("%Y-%m-%d")
    hourly_key = now.strftime("%Y-%m-%dT%H")
    # Cron job: enqueues work for every tenant, so it runs in platform context.
    with get_db(platform=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM restaurants ORDER BY id")
            tenant_ids = [int(row[0]) for row in cur.fetchall()]
            for tenant_id in tenant_ids:
                enqueue_job(cur, tenant_id=tenant_id, job_name="analytics.aggregate_hourly", idempotency_key=f"hourly:{tenant_id}:{hourly_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="analytics.aggregate_daily", idempotency_key=f"daily:{tenant_id}:{daily_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="data_quality.refresh", idempotency_key=f"quality:{tenant_id}:{daily_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="privacy.expire_old_raw_events", idempotency_key=f"retention:{tenant_id}:{daily_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="missions.evaluate_abandoned_carts", idempotency_key=f"abandoned:{tenant_id}:{hourly_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="missions.evaluate_bundles", idempotency_key=f"bundles:{tenant_id}:{hourly_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="missions.evaluate_quiet_hours", idempotency_key=f"quiet-hours:{tenant_id}:{hourly_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="missions.evaluate_product_demand_tests", idempotency_key=f"product-demand:{tenant_id}:{hourly_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="missions.monitor_running", idempotency_key=f"mission-monitor:{tenant_id}:{hourly_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="experiments.evaluate", idempotency_key=f"experiments:{tenant_id}:{hourly_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="opportunities.detect_daily", idempotency_key=f"opportunities-daily:{tenant_id}:{daily_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="customers.refresh_segments", idempotency_key=f"segments:{tenant_id}:{daily_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="missions.evaluate_lapsed_customers", idempotency_key=f"lapsed:{tenant_id}:{daily_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="conversion.refresh_demand_twin", idempotency_key=f"demand-twin:{tenant_id}:{daily_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="network.refresh_benchmarks", idempotency_key=f"benchmarks:{tenant_id}:{daily_key}")
                enqueue_job(cur, tenant_id=tenant_id, job_name="platform.performance_review", idempotency_key=f"performance-review:{tenant_id}:{daily_key}")
                if now.weekday() == 0:
                    weekly_key = now.strftime("%G-W%V")
                    enqueue_job(cur, tenant_id=tenant_id, job_name="opportunities.generate_weekly_cards", idempotency_key=f"opportunities-weekly:{tenant_id}:{weekly_key}")


if __name__ == "__main__":
    main()
