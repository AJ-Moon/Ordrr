import json
from typing import Any, Optional

from db import get_db


def record_audit(
    cursor,
    *,
    tenant_id: Optional[int],
    actor_type: str,
    actor_id: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    before: Optional[dict[str, Any]] = None,
    after: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    cursor.execute(
        """INSERT INTO audit_logs
           (tenant_id, actor_type, actor_id, action, resource_type, resource_id,
            before_data, after_data, metadata)
           VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)""",
        (
            tenant_id,
            actor_type,
            actor_id,
            action,
            resource_type,
            resource_id,
            json.dumps(before or {}),
            json.dumps(after or {}),
            json.dumps(metadata or {}),
        ),
    )


def write_audit(**kwargs: Any) -> None:
    with get_db() as conn:
        with conn.cursor() as cursor:
            record_audit(cursor, **kwargs)
