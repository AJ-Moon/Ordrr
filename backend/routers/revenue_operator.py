from datetime import datetime, timezone
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from db import get_db
from dependencies.auth import TokenData, get_current_admin, get_current_user
from services.consent import ensure_customer, list_consents, update_consents
from services.jobs import enqueue_job
from services.audit import record_audit

router = APIRouter()


class ConsentUpdate(BaseModel):
    channel: Literal["email", "sms", "whatsapp", "push"]
    status: Literal["granted", "denied", "withdrawn", "unknown"]
    source: str = Field(default="account_settings", max_length=80)
    policyVersion: str = Field(default="1", max_length=40)


class ConsentUpdateRequest(BaseModel):
    consents: list[ConsentUpdate] = Field(min_length=1, max_length=4)


class CustomerDeletionRequest(BaseModel):
    confirmation: Literal["DELETE"]


RUNNABLE_PHASE1_JOBS = {
    "analytics.aggregate_hourly",
    "analytics.aggregate_daily",
    "analytics.refresh_item_metrics",
    "analytics.refresh_checkout_metrics",
    "analytics.refresh_source_metrics",
    "analytics.refresh_search_metrics",
    "analytics.refresh_chat_metrics",
    "analytics.refresh_customer_metrics",
    "analytics.refresh_basket_associations",
    "analytics.refresh_menu_matrix",
    "opportunities.detect_daily",
    "opportunities.generate_weekly_cards",
    "data_quality.refresh",
    "privacy.expire_old_raw_events",
    "missions.evaluate_abandoned_carts",
    "experiments.evaluate",
    "customers.refresh_segments",
    "missions.evaluate_bundles",
    "missions.evaluate_lapsed_customers",
    "missions.evaluate_quiet_hours",
    "missions.evaluate_product_demand_tests",
    "missions.monitor_running",
    "conversion.refresh_demand_twin",
    "network.refresh_benchmarks",
    "platform.performance_review",
}


@router.get("/admin/features")
def list_features(admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT f.feature_key, f.description,
                          COALESCE(o.enabled, pe.enabled, f.default_enabled) AS enabled,
                          COALESCE(o.limit_value, pe.limit_value, f.default_limit) AS limit_value,
                          CASE WHEN o.feature_key IS NOT NULL THEN 'tenant_override'
                               WHEN pe.feature_key IS NOT NULL THEN 'plan'
                               ELSE 'default' END AS source
                   FROM feature_definitions f
                   LEFT JOIN tenant_feature_overrides o
                     ON o.tenant_id = %s AND o.feature_key = f.feature_key
                   LEFT JOIN LATERAL (
                       SELECT pe.feature_key, pe.enabled, pe.limit_value
                       FROM tenant_plans tp
                       JOIN plan_entitlements pe ON pe.plan_id = tp.plan_id
                       WHERE tp.tenant_id = %s AND pe.feature_key = f.feature_key
                         AND tp.starts_at <= CURRENT_DATE
                         AND (tp.ends_at IS NULL OR tp.ends_at >= CURRENT_DATE)
                       ORDER BY tp.starts_at DESC LIMIT 1
                   ) pe ON TRUE
                   ORDER BY f.feature_key""",
                (tenant_id, tenant_id),
            )
            rows = cur.fetchall()
    return [
        {"key": row[0], "description": row[1], "enabled": row[2], "limit": row[3], "source": row[4]}
        for row in rows
    ]


@router.get("/admin/audit-logs")
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    admin: dict = Depends(get_current_admin),
):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, actor_type, actor_id, action, resource_type, resource_id,
                          before_data, after_data, metadata, created_at
                   FROM audit_logs WHERE tenant_id = %s
                   ORDER BY created_at DESC LIMIT %s""",
                (tenant_id, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "id": row[0], "actorType": row[1], "actorId": row[2], "action": row[3],
            "resourceType": row[4], "resourceId": row[5], "before": row[6],
            "after": row[7], "metadata": row[8], "createdAt": row[9].isoformat(),
        }
        for row in rows
    ]


@router.get("/admin/jobs")
def list_jobs(
    limit: int = Query(default=100, ge=1, le=500),
    admin: dict = Depends(get_current_admin),
):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, job_name, idempotency_key, status, run_after, started_at,
                          completed_at, attempt, max_attempts, error_code, error_message,
                          metadata, created_at
                   FROM job_runs WHERE tenant_id = %s
                   ORDER BY created_at DESC LIMIT %s""",
                (tenant_id, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "id": row[0], "jobName": row[1], "idempotencyKey": row[2], "status": row[3],
            "runAfter": row[4].isoformat() if row[4] else None,
            "startedAt": row[5].isoformat() if row[5] else None,
            "completedAt": row[6].isoformat() if row[6] else None,
            "attempt": row[7], "maxAttempts": row[8], "errorCode": row[9],
            "errorMessage": row[10], "metadata": row[11],
            "createdAt": row[12].isoformat() if row[12] else None,
        }
        for row in rows
    ]


@router.post("/admin/jobs/{job_name}/run", status_code=202)
def run_job(job_name: str, admin: dict = Depends(get_current_admin)):
    if job_name not in RUNNABLE_PHASE1_JOBS:
        raise HTTPException(status_code=404, detail="Unknown Phase 1 job")
    tenant_id = int(admin["restaurant_id"])
    key = f"manual:{tenant_id}:{job_name}:{datetime.now(timezone.utc).isoformat()}"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT count(*) FROM job_runs WHERE tenant_id = %s
                   AND metadata->>'trigger' = 'admin' AND created_at >= NOW() - INTERVAL '1 hour'""",
                (tenant_id,),
            )
            limit = max(1, int(os.getenv("ADMIN_JOB_RATE_LIMIT_PER_HOUR", "20")))
            if int(cur.fetchone()[0]) >= limit:
                raise HTTPException(status_code=429, detail="Manual job rate limit exceeded")
            job_id = enqueue_job(
                cur,
                tenant_id=tenant_id,
                job_name=job_name,
                idempotency_key=key,
                metadata={"trigger": "admin", "actorId": str(admin["id"])},
            )
    return {"id": job_id, "status": "queued", "jobName": job_name}


@router.get("/data-quality")
def get_data_quality(admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT check_key, status, affected_count, details, checked_at
                   FROM data_quality_checks WHERE tenant_id = %s
                   ORDER BY CASE status WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                            check_key""",
                (tenant_id,),
            )
            rows = cur.fetchall()
    return {
        "status": "not_run" if not rows else (
            "error" if any(row[1] == "error" for row in rows) else
            "warning" if any(row[1] == "warning" for row in rows) else "ok"
        ),
        "checks": [
            {
                "key": row[0], "status": row[1], "affectedCount": row[2],
                "details": row[3], "checkedAt": row[4].isoformat(),
            }
            for row in rows
        ],
    }


@router.get("/customers/me/consents")
def get_my_consents(user: TokenData = Depends(get_current_user)):
    customer_id = ensure_customer(user.restaurant_id, user.id, user.email)
    return {"customerId": customer_id, "consents": list_consents(user.restaurant_id, customer_id)}


@router.put("/customers/me/consents")
def put_my_consents(body: ConsentUpdateRequest, user: TokenData = Depends(get_current_user)):
    customer_id = ensure_customer(user.restaurant_id, user.id, user.email)
    consents = update_consents(
        tenant_id=user.restaurant_id,
        customer_id=customer_id,
        user_id=user.id,
        updates=[item.model_dump() for item in body.consents],
    )
    return {"customerId": customer_id, "consents": consents}


@router.get("/customers/me/export")
def export_my_data(user: TokenData = Depends(get_current_user)):
    customer_id = ensure_customer(user.restaurant_id, user.id, user.email)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT email, first_name, last_name, phone, created_at
                   FROM users WHERE id = %s AND restaurant_id = %s""",
                (user.id, user.restaurant_id),
            )
            profile = cur.fetchone()
            cur.execute(
                """SELECT id, items, subtotal, discount_amount, delivery_charge, total,
                          status, order_type, payment_method, created_at
                   FROM orders WHERE restaurant_id = %s
                     AND (user_id = %s OR claimed_by_user_id = %s)
                   ORDER BY created_at DESC""",
                (user.restaurant_id, user.id, user.id),
            )
            orders = cur.fetchall()
            record_audit(
                cur,
                tenant_id=user.restaurant_id,
                actor_type="customer",
                actor_id=user.id,
                action="customer_data.exported",
                resource_type="customer",
                resource_id=customer_id,
            )
    return {
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "email": profile[0], "firstName": profile[1], "lastName": profile[2],
            "phone": profile[3], "createdAt": profile[4].isoformat(),
        } if profile else None,
        "consents": list_consents(user.restaurant_id, customer_id),
        "orders": [
            {
                "id": row[0], "items": row[1], "subtotal": float(row[2] or 0),
                "discountAmount": float(row[3] or 0), "deliveryCharge": float(row[4] or 0),
                "total": float(row[5] or 0), "status": row[6], "orderType": row[7],
                "paymentMethod": row[8], "createdAt": row[9].isoformat(),
            }
            for row in orders
        ],
    }


@router.delete("/customers/me", status_code=202)
def anonymize_my_data(
    body: CustomerDeletionRequest,
    user: TokenData = Depends(get_current_user),
):
    _ = body
    customer_id = ensure_customer(user.restaurant_id, user.id, user.email)
    anonymous_email = f"deleted+{user.id}@invalid.local"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE users SET email = %s, first_name = '', last_name = '', phone = ''
                   WHERE id = %s AND restaurant_id = %s""",
                (anonymous_email, user.id, user.restaurant_id),
            )
            cur.execute(
                """UPDATE customers SET email = NULL, phone = NULL, first_name = '', last_name = '',
                   anonymized_at = NOW(), updated_at = NOW()
                   WHERE id = %s AND tenant_id = %s""",
                (customer_id, user.restaurant_id),
            )
            cur.execute(
                """UPDATE customer_consents SET status = 'withdrawn', source = 'customer_deletion',
                   recorded_at = NOW(), updated_at = NOW()
                   WHERE tenant_id = %s AND customer_id = %s""",
                (user.restaurant_id, customer_id),
            )
            cur.execute(
                """INSERT INTO communication_suppressions
                   (tenant_id, customer_id, channel, reason, active)
                   SELECT %s, %s, channel, 'customer_deletion', TRUE
                   FROM (VALUES ('email'),('sms'),('whatsapp'),('push')) AS channels(channel)
                   ON CONFLICT (tenant_id, customer_id, channel)
                   DO UPDATE SET reason = 'customer_deletion', active = TRUE, updated_at = NOW()""",
                (user.restaurant_id, customer_id),
            )
            cur.execute(
                "UPDATE analytics_events SET customer_id = NULL WHERE tenant_id = %s AND customer_id = %s",
                (user.restaurant_id, customer_id),
            )
            record_audit(
                cur,
                tenant_id=user.restaurant_id,
                actor_type="customer",
                actor_id=user.id,
                action="customer_data.anonymized",
                resource_type="customer",
                resource_id=customer_id,
            )
    return {"status": "anonymized"}
