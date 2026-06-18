from typing import Iterable

from fastapi import HTTPException

from db import get_db
from services.audit import record_audit

CONSENT_CHANNELS = {"email", "sms", "whatsapp", "push"}
CONSENT_STATUSES = {"granted", "denied", "withdrawn", "unknown"}


def validate_consent(channel: str, status: str) -> tuple[str, str]:
    normalized_channel = channel.strip().lower()
    normalized_status = status.strip().lower()
    if normalized_channel not in CONSENT_CHANNELS:
        raise HTTPException(status_code=422, detail=f"Unsupported consent channel: {channel}")
    if normalized_status not in CONSENT_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unsupported consent status: {status}")
    return normalized_channel, normalized_status


def ensure_customer(tenant_id: int, user_id: str, email: str) -> str:
    with get_db() as conn:
        with conn.cursor() as cur:
            return ensure_customer_with_cursor(cur, tenant_id, user_id, email)


def ensure_customer_with_cursor(cursor, tenant_id: int, user_id: str, email: str) -> str:
    cursor.execute(
        "SELECT id FROM customers WHERE tenant_id = %s AND user_id = %s",
        (tenant_id, user_id),
    )
    row = cursor.fetchone()
    if row:
        return str(row[0])
    cursor.execute(
        """INSERT INTO customers (tenant_id, user_id, email)
           VALUES (%s, %s, %s) RETURNING id""",
        (tenant_id, user_id, email),
    )
    return str(cursor.fetchone()[0])


def list_consents(tenant_id: int, customer_id: str) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT channel, status, source, policy_version, recorded_at
                   FROM customer_consents
                   WHERE tenant_id = %s AND customer_id = %s
                   ORDER BY channel""",
                (tenant_id, customer_id),
            )
            rows = cur.fetchall()
    return [
        {
            "channel": row[0],
            "status": row[1],
            "source": row[2],
            "policyVersion": row[3],
            "recordedAt": row[4].isoformat(),
        }
        for row in rows
    ]


def update_consents(
    *,
    tenant_id: int,
    customer_id: str,
    user_id: str,
    updates: Iterable[dict],
) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            for update in updates:
                channel, consent_status = validate_consent(update["channel"], update["status"])
                cur.execute(
                    """INSERT INTO customer_consents
                       (tenant_id, customer_id, channel, status, source, policy_version, recorded_at)
                       VALUES (%s, %s, %s, %s, %s, %s, NOW())
                       ON CONFLICT (tenant_id, customer_id, channel)
                       DO UPDATE SET status = EXCLUDED.status,
                                     source = EXCLUDED.source,
                                     policy_version = EXCLUDED.policy_version,
                                     recorded_at = NOW(), updated_at = NOW()""",
                    (
                        tenant_id,
                        customer_id,
                        channel,
                        consent_status,
                        update.get("source", "account_settings"),
                        update.get("policyVersion", "1"),
                    ),
                )
                if consent_status in {"denied", "withdrawn"}:
                    cur.execute(
                        """INSERT INTO communication_suppressions
                           (tenant_id, customer_id, channel, reason, active)
                           VALUES (%s, %s, %s, 'consent_withdrawn', TRUE)
                           ON CONFLICT (tenant_id, customer_id, channel)
                           DO UPDATE SET reason = EXCLUDED.reason, active = TRUE, updated_at = NOW()""",
                        (tenant_id, customer_id, channel),
                    )
                elif consent_status == "granted":
                    cur.execute(
                        """UPDATE communication_suppressions
                           SET active = FALSE, updated_at = NOW()
                           WHERE tenant_id = %s AND customer_id = %s AND channel = %s
                             AND reason = 'consent_withdrawn'""",
                        (tenant_id, customer_id, channel),
                    )
                record_audit(
                    cur,
                    tenant_id=tenant_id,
                    actor_type="customer",
                    actor_id=user_id,
                    action="consent.updated",
                    resource_type="customer_consent",
                    resource_id=f"{customer_id}:{channel}",
                    after={"channel": channel, "status": consent_status},
                )
    return list_consents(tenant_id, customer_id)
