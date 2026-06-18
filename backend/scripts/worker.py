#!/usr/bin/env python3
import argparse
import json
import time
from datetime import datetime, timezone

from db import get_db
from services.analytics_jobs import JOB_HANDLERS
from services.jobs import retry_delay


def process_one() -> bool:
    # The worker is trusted infrastructure: it claims jobs across all tenants
    # (platform context), then narrows the RLS context to the claimed job's tenant
    # before running the handler, so handler queries stay scoped to that tenant.
    with get_db(platform=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, tenant_id, job_name, attempt, max_attempts, metadata
                   FROM job_runs
                   WHERE status IN ('queued','failed') AND run_after <= NOW() AND attempt < max_attempts
                   ORDER BY run_after, created_at
                   FOR UPDATE SKIP LOCKED LIMIT 1"""
            )
            row = cur.fetchone()
            if not row:
                return False
            job_id, tenant_id, job_name, attempt, max_attempts, metadata = row
            cur.execute(
                """UPDATE job_runs SET status = 'running', started_at = NOW(),
                   completed_at = NULL, attempt = attempt + 1, updated_at = NOW(),
                   error_code = NULL, error_message = NULL WHERE id = %s""",
                (job_id,),
            )

            # Narrow RLS context to this job's tenant for the handler and the
            # subsequent status updates (transaction-local; reverts on commit).
            cur.execute(
                "SELECT set_config('app.tenant_id', %s, true), set_config('app.is_platform', 'off', true)",
                (str(int(tenant_id)),),
            )

            cur.execute("SAVEPOINT job_execution")
            try:
                handler = JOB_HANDLERS.get(job_name)
                if not handler:
                    raise RuntimeError(f"No handler registered for {job_name}")
                handler(cur, int(tenant_id), metadata if isinstance(metadata, dict) else json.loads(metadata or "{}"))
                cur.execute("RELEASE SAVEPOINT job_execution")
                cur.execute(
                    "UPDATE job_runs SET status = 'succeeded', completed_at = NOW(), updated_at = NOW() WHERE id = %s",
                    (job_id,),
                )
            except Exception as exc:
                cur.execute("ROLLBACK TO SAVEPOINT job_execution")
                next_attempt = int(attempt) + 1
                terminal = next_attempt >= int(max_attempts)
                run_after = datetime.now(timezone.utc) + retry_delay(next_attempt)
                cur.execute(
                    """UPDATE job_runs SET status = 'failed', completed_at = NOW(), run_after = %s,
                       error_code = %s, error_message = %s, updated_at = NOW() WHERE id = %s""",
                    (run_after, "terminal" if terminal else "retryable", str(exc)[:2000], job_id),
                )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="ORDER durable PostgreSQL job worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()

    while True:
        worked = process_one()
        if args.once:
            return
        if not worked:
            time.sleep(max(0.2, args.poll_seconds))


if __name__ == "__main__":
    main()
