import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


def enqueue_job(
    cursor,
    *,
    job_name: str,
    idempotency_key: str,
    tenant_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
    run_after: Optional[datetime] = None,
    max_attempts: int = 3,
) -> Optional[int]:
    cursor.execute(
        """INSERT INTO job_runs
           (tenant_id, job_name, idempotency_key, status, run_after, max_attempts, metadata)
           VALUES (%s,%s,%s,'queued',%s,%s,%s::jsonb)
           ON CONFLICT (job_name, idempotency_key) DO NOTHING
           RETURNING id""",
        (
            tenant_id, job_name, idempotency_key,
            run_after or datetime.now(timezone.utc), max_attempts, json.dumps(metadata or {}),
        ),
    )
    row = cursor.fetchone()
    return int(row[0]) if row else None


def retry_delay(attempt: int) -> timedelta:
    return timedelta(seconds=min(3600, 30 * (2 ** max(0, attempt - 1))))
