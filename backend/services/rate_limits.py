import os
from typing import Optional

from fastapi import HTTPException, Request

from db import get_db


def _client_ip(request: Optional[Request]) -> str:
    if request is None:
        return "unknown"
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()[:60]
    client = request.client
    return (client.host if client else "unknown")[:60]


def consume_auth_rate(request: Optional[Request], scope: str, identifier: str) -> None:
    """Durable, multi-instance login/auth throttle.

    Counts attempts per (scope, client-IP, identifier) in fixed 1-minute windows and
    raises 429 once the limit is exceeded. Backed by auth_rate_windows so the limit
    holds across instances/restarts. Fails OPEN if the table is missing (migration
    0011 not yet applied) so it never bricks login.
    """
    limit = max(1, int(os.getenv("AUTH_RATE_LIMIT_PER_MINUTE", "10")))
    ip = _client_ip(request)
    bucket = f"{scope}:{ip}:{(identifier or '').strip().lower()}"[:160]
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO auth_rate_windows (bucket, window_start, request_count)
                       VALUES (%s, date_trunc('minute', NOW()), 1)
                       ON CONFLICT (bucket, window_start) DO UPDATE SET
                         request_count = auth_rate_windows.request_count + 1,
                         updated_at = NOW()
                       RETURNING request_count""",
                    (bucket,),
                )
                count = int(cursor.fetchone()[0])
    except Exception as exc:  # pragma: no cover - defensive
        from psycopg2 import errors as _pg_errors

        if isinstance(exc, _pg_errors.UndefinedTable):
            return
        raise
    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please wait a minute and try again.",
        )


def consume_intervention_rate(tenant_id: int, scope: str, env_key: str, default_limit: int) -> int:
    limit = max(1, int(os.getenv(env_key, str(default_limit))))
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO intervention_request_windows (tenant_id,scope,window_start,request_count)
                   VALUES (%s,%s,date_trunc('minute',NOW()),1)
                   ON CONFLICT (tenant_id,scope,window_start) DO UPDATE SET
                     request_count=intervention_request_windows.request_count+1,updated_at=NOW()
                   RETURNING request_count""",
                (tenant_id, scope),
            )
            count = int(cursor.fetchone()[0])
    if count > limit:
        raise HTTPException(status_code=429, detail=f"{scope} rate limit exceeded")
    return count
