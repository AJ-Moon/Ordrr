import json
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from db import get_db
from dependencies.auth import TenantContext, TokenData, get_current_admin, get_optional_current_user, resolve_public_tenant
from services.advanced_conversion import (
    build_order_architect_suggestion,
    list_personalized_merchandising,
    validate_private_offer,
)
from services.commerce import RequestedLine, persist_cart_snapshot, price_menu_lines
from services.consent import ensure_customer_with_cursor
from services.entitlements import has_feature
from services.jobs import enqueue_job
from services.rate_limits import consume_intervention_rate

router = APIRouter()


class OrderArchitectRequest(BaseModel):
    visitorId: str = Field(min_length=8, max_length=120)
    sessionId: str = Field(min_length=8, max_length=120)
    budgetCents: Optional[int] = Field(default=None, ge=0, le=200000)
    partySize: int = Field(default=1, ge=1, le=30)
    dietaryConstraints: list[str] = Field(default_factory=list, max_length=12)
    excludedIngredients: list[str] = Field(default_factory=list, max_length=30)
    preferences: dict[str, Any] = Field(default_factory=dict)


class OrderArchitectCartRequest(OrderArchitectRequest):
    cartId: str = Field(min_length=8, max_length=120)


class PrivateOfferCreate(BaseModel):
    code: str = Field(min_length=3, max_length=80)
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=3000)
    targetSegment: Optional[str] = Field(default=None, max_length=80)
    customerId: Optional[str] = Field(default=None, max_length=80)
    visitorId: Optional[str] = Field(default=None, max_length=120)
    discountType: Literal["PERCENT", "FIXED"]
    discountValue: int = Field(gt=0)
    maxDiscountCents: Optional[int] = Field(default=None, ge=0)
    minimumSubtotalCents: int = Field(default=0, ge=0)
    minimumMarginCents: int = Field(default=0)
    maxRedemptions: Optional[int] = Field(default=None, ge=1)
    startsAt: Optional[datetime] = None
    endsAt: Optional[datetime] = None
    rules: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_offer(self):
        if self.discountType == "PERCENT" and self.discountValue > 100:
            raise ValueError("Percent private offers cannot exceed 100")
        if self.endsAt and self.startsAt and self.endsAt <= self.startsAt:
            raise ValueError("endsAt must be after startsAt")
        return self


class PrivateOfferValidateRequest(BaseModel):
    code: str = Field(min_length=3, max_length=80)
    visitorId: Optional[str] = Field(default=None, max_length=120)
    cartId: Optional[str] = Field(default=None, max_length=120)
    items: list[dict[str, int]] = Field(default_factory=list, max_length=100)


class MerchandisingRequest(BaseModel):
    visitorId: str = Field(min_length=8, max_length=120)
    sessionId: str = Field(min_length=8, max_length=120)
    placement: str = Field(default="HOME", min_length=2, max_length=80)
    segment: Optional[str] = Field(default=None, max_length=80)


class IntegrationAccountInput(BaseModel):
    provider: str = Field(min_length=2, max_length=80)
    integrationType: Literal["MESSAGING", "ADVERTISING"]
    channel: Optional[str] = Field(default=None, max_length=40)
    status: Literal["DISABLED", "CONFIGURED"] = "DISABLED"
    secretReference: Optional[str] = Field(default=None, max_length=200)
    settings: dict[str, Any] = Field(default_factory=dict)


def _require_feature_or_empty(tenant_id: int, feature_key: str) -> bool:
    return has_feature(tenant_id, feature_key)


def _offer_dict(row: tuple) -> dict[str, Any]:
    return {
        "id": row[0],
        "code": row[1],
        "title": row[2],
        "description": row[3],
        "targetSegment": row[4],
        "discountType": row[5],
        "discountValue": row[6],
        "minimumSubtotalCents": row[7],
        "status": row[8],
        "updatedAt": row[9].isoformat(),
    }


@router.post("/order-architect/suggest")
def suggest_order_architect(
    body: OrderArchitectRequest,
    tenant: TenantContext = Depends(resolve_public_tenant),
    user: Optional[TokenData] = Depends(get_optional_current_user),
):
    if not _require_feature_or_empty(tenant.id, "conversion.order_architect"):
        return {"status": "DISABLED", "items": []}
    consume_intervention_rate(tenant.id, "order_architect", "ORDER_ARCHITECT_RATE_PER_MINUTE", 120)
    with get_db() as conn:
        with conn.cursor() as cur:
            customer_id = ensure_customer_with_cursor(cur, tenant.id, user.id, user.email) if user else None
            return build_order_architect_suggestion(
                cur,
                tenant_id=tenant.id,
                visitor_id=body.visitorId,
                session_id=body.sessionId,
                customer_id=customer_id,
                budget_cents=body.budgetCents,
                party_size=body.partySize,
                dietary_constraints=body.dietaryConstraints,
                excluded_ingredients=body.excludedIngredients,
                preferences=body.preferences,
            )


@router.post("/order-architect/cart")
def create_order_architect_cart(
    body: OrderArchitectCartRequest,
    tenant: TenantContext = Depends(resolve_public_tenant),
    user: Optional[TokenData] = Depends(get_optional_current_user),
):
    suggestion = suggest_order_architect(body, tenant, user)
    if suggestion.get("status") != "COMPLETED":
        return suggestion
    with get_db() as conn:
        with conn.cursor() as cur:
            lines = price_menu_lines(
                cur,
                tenant.id,
                [RequestedLine(menu_item_id=item["menuItemId"], quantity=item["quantity"]) for item in suggestion["items"]],
            )
            customer_id = ensure_customer_with_cursor(cur, tenant.id, user.id, user.email) if user else None
            persist_cart_snapshot(
                cur,
                tenant_id=tenant.id,
                cart_id=body.cartId,
                visitor_id=body.visitorId,
                session_id=body.sessionId,
                customer_id=customer_id,
                user_id=user.id if user else None,
                lines=lines,
            )
            cur.execute(
                "UPDATE order_architect_suggestions SET cart_id=%s WHERE tenant_id=%s AND id=%s",
                (body.cartId, tenant.id, suggestion["suggestionId"]),
            )
    return {**suggestion, "cartId": body.cartId}


@router.get("/private-offers")
def list_private_offers(admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    if not has_feature(tenant_id, "conversion.private_offers"):
        raise HTTPException(status_code=403, detail="Feature 'conversion.private_offers' is not enabled")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,code,title,description,target_segment,discount_type,discount_value,
                          minimum_subtotal_cents,status,updated_at
                   FROM private_offers WHERE tenant_id=%s ORDER BY updated_at DESC LIMIT 100""",
                (tenant_id,),
            )
            return {"items": [_offer_dict(row) for row in cur.fetchall()]}


@router.post("/private-offers", status_code=201)
def create_private_offer(body: PrivateOfferCreate, admin: dict = Depends(get_current_admin)):
    tenant_id, actor_id = int(admin["restaurant_id"]), str(admin["id"])
    if not has_feature(tenant_id, "conversion.private_offers"):
        raise HTTPException(status_code=403, detail="Feature 'conversion.private_offers' is not enabled")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO private_offers
                   (tenant_id,code,title,description,target_segment,customer_id,visitor_id,discount_type,
                    discount_value,max_discount_cents,minimum_subtotal_cents,minimum_margin_cents,
                    max_redemptions,starts_at,ends_at,rules,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                   RETURNING id,code,title,description,target_segment,discount_type,discount_value,
                             minimum_subtotal_cents,status,updated_at""",
                (
                    tenant_id,
                    body.code.strip().upper(),
                    body.title.strip(),
                    body.description.strip(),
                    body.targetSegment,
                    body.customerId,
                    body.visitorId,
                    body.discountType,
                    body.discountValue,
                    body.maxDiscountCents,
                    body.minimumSubtotalCents,
                    body.minimumMarginCents,
                    body.maxRedemptions,
                    body.startsAt,
                    body.endsAt,
                    json.dumps(body.rules),
                    actor_id,
                ),
            )
            return _offer_dict(cur.fetchone())


@router.post("/private-offers/validate")
def validate_offer_public(
    body: PrivateOfferValidateRequest,
    tenant: TenantContext = Depends(resolve_public_tenant),
    user: Optional[TokenData] = Depends(get_optional_current_user),
):
    if not has_feature(tenant.id, "conversion.private_offers"):
        return {"valid": False, "reason": "disabled"}
    with get_db() as conn:
        with conn.cursor() as cur:
            customer_id = ensure_customer_with_cursor(cur, tenant.id, user.id, user.email) if user else None
            lines = price_menu_lines(
                cur,
                tenant.id,
                [RequestedLine(menu_item_id=int(item["menuItemId"]), quantity=int(item["quantity"])) for item in body.items],
            )
            subtotal = sum(line.line_revenue_cents for line in lines)
            margins = [line.line_margin_cents for line in lines]
            margin_before = sum(int(value or 0) for value in margins) if all(value is not None for value in margins) else None
            offer = validate_private_offer(
                cur,
                tenant_id=tenant.id,
                code=body.code,
                subtotal_cents=subtotal,
                estimated_margin_before_discount_cents=margin_before,
                visitor_id=body.visitorId,
                customer_id=customer_id,
            )
            return {"valid": True, "offer": offer}


@router.post("/private-offers/{offer_id}/{action}")
def transition_private_offer(offer_id: int, action: Literal["approve", "start", "pause", "complete", "cancel"], admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    transitions = {
        "approve": ({"DRAFT"}, "APPROVED"),
        "start": ({"APPROVED", "PAUSED"}, "RUNNING"),
        "pause": ({"RUNNING"}, "PAUSED"),
        "complete": ({"RUNNING", "PAUSED"}, "COMPLETED"),
        "cancel": ({"DRAFT", "APPROVED", "RUNNING", "PAUSED"}, "CANCELLED"),
    }
    allowed, target = transitions[action]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM private_offers WHERE tenant_id=%s AND id=%s FOR UPDATE", (tenant_id, offer_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Private offer not found")
            if row[0] not in allowed:
                raise HTTPException(status_code=409, detail=f"Offer cannot {action} from {row[0]}")
            cur.execute("UPDATE private_offers SET status=%s,updated_at=NOW() WHERE tenant_id=%s AND id=%s", (target, tenant_id, offer_id))
    return {"id": offer_id, "status": target}


@router.post("/personalized-merchandising")
def personalized_merchandising(
    body: MerchandisingRequest,
    tenant: TenantContext = Depends(resolve_public_tenant),
    user: Optional[TokenData] = Depends(get_optional_current_user),
):
    if not has_feature(tenant.id, "conversion.private_offers"):
        return {"offers": [], "items": []}
    consume_intervention_rate(tenant.id, "personalized_merchandising", "MERCHANDISING_RATE_PER_MINUTE", 1000)
    with get_db() as conn:
        with conn.cursor() as cur:
            customer_id = ensure_customer_with_cursor(cur, tenant.id, user.id, user.email) if user else None
            return list_personalized_merchandising(
                cur,
                tenant_id=tenant.id,
                visitor_id=body.visitorId,
                session_id=body.sessionId,
                placement=body.placement,
                customer_id=customer_id,
                segment=body.segment,
            )


@router.get("/tenant-demand-twin/latest")
def latest_demand_twin(admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    if not has_feature(tenant_id, "conversion.demand_twin"):
        raise HTTPException(status_code=403, detail="Feature 'conversion.demand_twin' is not enabled")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT snapshot_date,window_start,window_end,privacy_threshold,metrics,segments,menu_insights,source_mix,generated_at
                   FROM tenant_demand_twins WHERE tenant_id=%s ORDER BY snapshot_date DESC LIMIT 1""",
                (tenant_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"snapshot": None}
            return {
                "snapshot": {
                    "snapshotDate": row[0].isoformat(),
                    "windowStart": row[1].isoformat(),
                    "windowEnd": row[2].isoformat(),
                    "privacyThreshold": row[3],
                    "metrics": row[4],
                    "segments": row[5],
                    "menuInsights": row[6],
                    "sourceMix": row[7],
                    "generatedAt": row[8].isoformat(),
                }
            }


@router.post("/tenant-demand-twin/refresh", status_code=202)
def queue_demand_twin(admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            job_id = enqueue_job(cur, tenant_id=tenant_id, job_name="conversion.refresh_demand_twin", idempotency_key=f"demand-twin:{tenant_id}:{datetime.utcnow().strftime('%Y%m%d')}")
    return {"jobId": job_id, "status": "queued" if job_id else "already_queued"}


@router.get("/neighborhood-benchmarks/latest")
def latest_benchmark(admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    if not has_feature(tenant_id, "network.neighborhood_benchmarks"):
        raise HTTPException(status_code=403, detail="Feature 'network.neighborhood_benchmarks' is not enabled")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT benchmark_date,neighborhood_key,privacy_threshold,peer_count,status,metrics,generated_at
                   FROM neighborhood_benchmark_snapshots WHERE tenant_id=%s ORDER BY benchmark_date DESC LIMIT 1""",
                (tenant_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"snapshot": None}
            return {"snapshot": {"benchmarkDate": row[0].isoformat(), "neighborhoodKey": row[1], "privacyThreshold": row[2], "peerCount": row[3], "status": row[4], "metrics": row[5], "generatedAt": row[6].isoformat()}}


@router.post("/neighborhood-benchmarks/refresh", status_code=202)
def queue_benchmark(admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            job_id = enqueue_job(cur, tenant_id=tenant_id, job_name="network.refresh_benchmarks", idempotency_key=f"benchmarks:{tenant_id}:{datetime.utcnow().strftime('%Y%m%d')}")
    return {"jobId": job_id, "status": "queued" if job_id else "already_queued"}


@router.get("/admin/performance-review/latest")
def latest_performance_review(admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT reviewed_at,database_pooling,queue_throughput,partition_recommendations,status
                   FROM performance_reviews WHERE tenant_id=%s ORDER BY reviewed_at DESC LIMIT 1""",
                (tenant_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"review": None}
            return {"review": {"reviewedAt": row[0].isoformat(), "databasePooling": row[1], "queueThroughput": row[2], "partitionRecommendations": row[3], "status": row[4]}}


@router.post("/admin/performance-review/refresh", status_code=202)
def queue_performance_review(admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            job_id = enqueue_job(cur, tenant_id=tenant_id, job_name="platform.performance_review", idempotency_key=f"performance-review:{tenant_id}:{datetime.utcnow().strftime('%Y%m%d%H')}")
    return {"jobId": job_id, "status": "queued" if job_id else "already_queued"}


@router.get("/admin/integrations")
def list_integrations(admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,provider,integration_type,channel,status,secret_reference,settings,last_checked_at,last_error,updated_at
                   FROM integration_accounts WHERE tenant_id=%s ORDER BY integration_type,provider,channel""",
                (tenant_id,),
            )
            return {
                "items": [
                    {
                        "id": row[0],
                        "provider": row[1],
                        "integrationType": row[2],
                        "channel": row[3],
                        "status": row[4],
                        "secretReference": row[5],
                        "settings": row[6],
                        "lastCheckedAt": row[7].isoformat() if row[7] else None,
                        "lastError": row[8],
                        "updatedAt": row[9].isoformat(),
                    }
                    for row in cur.fetchall()
                ]
            }


@router.post("/admin/integrations", status_code=201)
def upsert_integration(body: IntegrationAccountInput, admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    feature = "integrations.production_messaging" if body.integrationType == "MESSAGING" else "integrations.advertising"
    if not has_feature(tenant_id, feature):
        raise HTTPException(status_code=403, detail=f"Feature '{feature}' is not enabled")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id FROM integration_accounts
                   WHERE tenant_id=%s AND provider=%s AND integration_type=%s
                     AND COALESCE(channel,'') = COALESCE(%s,'')""",
                (tenant_id, body.provider, body.integrationType, body.channel),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    """UPDATE integration_accounts SET status=%s,secret_reference=%s,settings=%s::jsonb,updated_at=NOW()
                       WHERE tenant_id=%s AND id=%s RETURNING id""",
                    (body.status, body.secretReference, json.dumps(body.settings), tenant_id, existing[0]),
                )
            else:
                cur.execute(
                    """INSERT INTO integration_accounts
                       (tenant_id,provider,integration_type,channel,status,secret_reference,settings)
                       VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
                       RETURNING id""",
                    (tenant_id, body.provider, body.integrationType, body.channel, body.status, body.secretReference, json.dumps(body.settings)),
                )
            return {"id": int(cur.fetchone()[0]), "status": body.status}


@router.post("/admin/integrations/{integration_id}/test")
def test_integration(integration_id: int, admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT provider,integration_type,channel,secret_reference,status FROM integration_accounts WHERE tenant_id=%s AND id=%s", (tenant_id, integration_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Integration not found")
            configured = row[4] == "CONFIGURED" and bool(row[3])
            error = None if configured else "Integration requires CONFIGURED status and a secret reference"
            cur.execute(
                "UPDATE integration_accounts SET last_checked_at=NOW(),last_error=%s,status=%s,updated_at=NOW() WHERE tenant_id=%s AND id=%s",
                (error, "CONFIGURED" if configured else "FAILED", tenant_id, integration_id),
            )
            return {"ok": configured, "provider": row[0], "integrationType": row[1], "channel": row[2], "error": error}
