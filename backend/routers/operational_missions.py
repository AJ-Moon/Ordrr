import json
from datetime import time
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field, model_validator

from db import get_db
from dependencies.auth import TenantContext, get_current_admin, resolve_public_tenant
from services.entitlements import has_feature
from services.missions import assign_group
from services.rate_limits import consume_intervention_rate

router = APIRouter()

PresentationMode = Literal["COMING_SOON", "LIMITED_TEST", "PREORDER", "JOIN_WAITLIST"]
ConceptStatus = Literal["DRAFT", "NEEDS_APPROVAL", "APPROVED", "RUNNING", "PAUSED", "COMPLETED", "CANCELLED"]

MODE_LABELS = {
    "COMING_SOON": {"label": "COMING SOON", "cta": "Register interest"},
    "LIMITED_TEST": {"label": "LIMITED TEST", "cta": "Join limited test"},
    "PREORDER": {"label": "PREORDER", "cta": "Reserve preorder"},
    "JOIN_WAITLIST": {"label": "JOIN WAITLIST", "cta": "Join waitlist"},
}


class CapacitySettingInput(BaseModel):
    locationId: int = Field(gt=0)
    weekday: int = Field(ge=0, le=6)
    timeStart: time
    timeEnd: time
    normalCapacityOrders: int = Field(gt=0)
    maximumCapacityOrders: int = Field(gt=0)
    targetUtilization: float = Field(default=0.75, gt=0, le=1)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_window(self):
        if self.timeEnd <= self.timeStart:
            raise ValueError("timeEnd must be after timeStart")
        if self.maximumCapacityOrders < self.normalCapacityOrders:
            raise ValueError("maximumCapacityOrders must be at least normalCapacityOrders")
        return self


class InventoryGuardrailInput(BaseModel):
    availableQuantity: Optional[int] = Field(default=None, ge=0)
    lowStockThreshold: int = Field(default=0, ge=0)
    constrained: bool = False
    notes: Optional[str] = Field(default=None, max_length=2000)


class ConceptVariantInput(BaseModel):
    variantKey: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=2, max_length=160)
    imageUrl: Optional[str] = Field(default=None, max_length=1000)
    description: str = Field(min_length=10, max_length=3000)
    priceCents: Optional[int] = Field(default=None, ge=0)
    deal: dict[str, Any] = Field(default_factory=dict)
    servingClaim: Optional[str] = Field(default=None, max_length=160)
    weight: int = Field(default=1, gt=0, le=100)
    isControl: bool = False


class ProductConceptInput(BaseModel):
    missionId: Optional[int] = None
    name: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=20, max_length=5000)
    category: str = Field(min_length=2, max_length=80)
    estimatedCostCents: int = Field(ge=0)
    estimatedPreparationTimeMinutes: int = Field(gt=0, le=240)
    targetLocationId: Optional[int] = None
    targetSegment: Optional[str] = Field(default=None, max_length=80)
    presentationMode: PresentationMode
    variants: list[ConceptVariantInput] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_variants(self):
        if self.presentationMode == "PREORDER" and not any(v.priceCents is not None for v in self.variants):
            raise ValueError("Preorder concepts require at least one variant with priceCents")
        if len({v.variantKey for v in self.variants}) != len(self.variants):
            raise ValueError("Variant keys must be unique")
        return self


class ConceptInteractionInput(BaseModel):
    visitorId: str = Field(min_length=8, max_length=120)
    sessionId: str = Field(min_length=8, max_length=120)
    variantId: Optional[int] = None
    preferredPriceCents: Optional[int] = Field(default=None, ge=0)
    segment: Optional[str] = Field(default=None, max_length=80)
    geography: Optional[str] = Field(default=None, max_length=120)
    source: Optional[str] = Field(default=None, max_length=80)
    medium: Optional[str] = Field(default=None, max_length=80)
    campaign: Optional[str] = Field(default=None, max_length=120)
    properties: dict[str, Any] = Field(default_factory=dict)


class WaitlistInput(ConceptInteractionInput):
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def validate_contact(self):
        if not self.email and not self.phone and not self.visitorId:
            raise ValueError("Waitlist requires an email, phone, or visitorId")
        return self


class PreorderInput(WaitlistInput):
    quantity: int = Field(default=1, gt=0, le=20)
    priceCents: Optional[int] = Field(default=None, ge=0)
    depositCents: int = Field(default=0, ge=0)


def _require_feature(tenant_id: int, feature_key: str) -> None:
    if not has_feature(tenant_id, feature_key):
        raise HTTPException(status_code=403, detail=f"Feature '{feature_key}' is not enabled")


def _capacity_dict(row: tuple) -> dict[str, Any]:
    return {
        "id": row[0],
        "locationId": row[1],
        "weekday": row[2],
        "timeStart": row[3].isoformat(),
        "timeEnd": row[4].isoformat(),
        "normalCapacityOrders": row[5],
        "maximumCapacityOrders": row[6],
        "targetUtilization": float(row[7]),
        "enabled": row[8],
        "updatedAt": row[9].isoformat(),
    }


def _concept_dict(row: tuple, variants: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
    labels = MODE_LABELS[row[11]]
    return {
        "id": row[0],
        "missionId": row[1],
        "name": row[2],
        "description": row[3],
        "category": row[4],
        "estimatedCostCents": row[5],
        "estimatedPreparationTimeMinutes": row[6],
        "targetLocationId": row[7],
        "targetSegment": row[8],
        "status": row[9],
        "presentationMode": row[11],
        "presentationLabel": labels["label"],
        "ctaLabel": labels["cta"],
        "availabilityNotice": f"{labels['label']}: this product is not available for immediate ordering.",
        "createdAt": row[12].isoformat(),
        "updatedAt": row[13].isoformat(),
        "variants": variants or [],
    }


def _variant_dict(row: tuple) -> dict[str, Any]:
    return {
        "id": row[0],
        "variantKey": row[1],
        "name": row[2],
        "imageUrl": row[3],
        "description": row[4],
        "priceCents": row[5],
        "deal": row[6],
        "servingClaim": row[7],
        "weight": row[8],
        "isControl": row[9],
    }


@router.get("/capacity-settings")
def list_capacity_settings(admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    _require_feature(tenant_id, "missions.quiet_hour")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,location_id,weekday,time_start,time_end,normal_capacity_orders,
                          maximum_capacity_orders,target_utilization,enabled,updated_at
                   FROM capacity_settings WHERE tenant_id=%s ORDER BY weekday,time_start,location_id""",
                (tenant_id,),
            )
            return {"items": [_capacity_dict(row) for row in cur.fetchall()]}


@router.post("/capacity-settings", status_code=201)
def create_capacity_setting(body: CapacitySettingInput, admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    _require_feature(tenant_id, "missions.quiet_hour")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM branches WHERE restaurant_id=%s AND id=%s", (tenant_id, body.locationId))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Location not found")
            cur.execute(
                """INSERT INTO capacity_settings
                   (tenant_id,location_id,weekday,time_start,time_end,normal_capacity_orders,
                    maximum_capacity_orders,target_utilization,enabled)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id,location_id,weekday,time_start,time_end,normal_capacity_orders,
                             maximum_capacity_orders,target_utilization,enabled,updated_at""",
                (
                    tenant_id,
                    body.locationId,
                    body.weekday,
                    body.timeStart,
                    body.timeEnd,
                    body.normalCapacityOrders,
                    body.maximumCapacityOrders,
                    body.targetUtilization,
                    body.enabled,
                ),
            )
            return _capacity_dict(cur.fetchone())


@router.put("/capacity-settings/{setting_id}")
def update_capacity_setting(setting_id: int, body: CapacitySettingInput, admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    _require_feature(tenant_id, "missions.quiet_hour")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE capacity_settings SET location_id=%s,weekday=%s,time_start=%s,time_end=%s,
                          normal_capacity_orders=%s,maximum_capacity_orders=%s,target_utilization=%s,
                          enabled=%s,updated_at=NOW()
                   WHERE tenant_id=%s AND id=%s
                   RETURNING id,location_id,weekday,time_start,time_end,normal_capacity_orders,
                             maximum_capacity_orders,target_utilization,enabled,updated_at""",
                (
                    body.locationId,
                    body.weekday,
                    body.timeStart,
                    body.timeEnd,
                    body.normalCapacityOrders,
                    body.maximumCapacityOrders,
                    body.targetUtilization,
                    body.enabled,
                    tenant_id,
                    setting_id,
                ),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Capacity setting not found")
            return _capacity_dict(row)


@router.get("/inventory-guardrails")
def list_inventory_guardrails(limit: int = Query(100, ge=1, le=500), admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    _require_feature(tenant_id, "missions.quiet_hour")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT mi.id,mi.name,mi.is_available,ig.available_quantity,ig.low_stock_threshold,
                          COALESCE(ig.constrained,false),ig.notes,ig.updated_at
                   FROM menu_items mi
                   LEFT JOIN inventory_guardrails ig ON ig.tenant_id=mi.restaurant_id AND ig.item_id=mi.id
                   WHERE mi.restaurant_id=%s
                   ORDER BY mi.name LIMIT %s""",
                (tenant_id, limit),
            )
            return {
                "items": [
                    {
                        "itemId": row[0],
                        "name": row[1],
                        "isAvailable": row[2],
                        "availableQuantity": row[3],
                        "lowStockThreshold": row[4] or 0,
                        "constrained": row[5],
                        "notes": row[6],
                        "updatedAt": row[7].isoformat() if row[7] else None,
                    }
                    for row in cur.fetchall()
                ]
            }


@router.put("/inventory-guardrails/{item_id}")
def upsert_inventory_guardrail(item_id: int, body: InventoryGuardrailInput, admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    _require_feature(tenant_id, "missions.quiet_hour")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM menu_items WHERE restaurant_id=%s AND id=%s", (tenant_id, item_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Menu item not found")
            cur.execute(
                """INSERT INTO inventory_guardrails
                   (tenant_id,item_id,available_quantity,low_stock_threshold,constrained,notes)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (tenant_id,item_id) DO UPDATE SET
                     available_quantity=EXCLUDED.available_quantity,
                     low_stock_threshold=EXCLUDED.low_stock_threshold,
                     constrained=EXCLUDED.constrained,
                     notes=EXCLUDED.notes,
                     updated_at=NOW()
                   RETURNING item_id,available_quantity,low_stock_threshold,constrained,notes,updated_at""",
                (tenant_id, item_id, body.availableQuantity, body.lowStockThreshold, body.constrained, body.notes),
            )
            row = cur.fetchone()
            return {
                "itemId": row[0],
                "availableQuantity": row[1],
                "lowStockThreshold": row[2],
                "constrained": row[3],
                "notes": row[4],
                "updatedAt": row[5].isoformat(),
            }


@router.get("/product-concepts")
def list_product_concepts(admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    _require_feature(tenant_id, "missions.product_demand_test")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,mission_id,name,description,category,estimated_cost_cents,
                          estimated_preparation_time_minutes,target_location_id,target_segment,status,
                          created_by,presentation_mode,created_at,updated_at
                   FROM product_concepts WHERE tenant_id=%s ORDER BY updated_at DESC LIMIT 100""",
                (tenant_id,),
            )
            return {"items": [_concept_dict(row) for row in cur.fetchall()]}


@router.post("/product-concepts", status_code=201)
def create_product_concept(body: ProductConceptInput, admin: dict = Depends(get_current_admin)):
    tenant_id, actor_id = int(admin["restaurant_id"]), str(admin["id"])
    _require_feature(tenant_id, "missions.product_demand_test")
    with get_db() as conn:
        with conn.cursor() as cur:
            if body.missionId:
                cur.execute("SELECT 1 FROM missions WHERE tenant_id=%s AND id=%s AND type='NEW_PRODUCT_DEMAND_TEST'", (tenant_id, body.missionId))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Product demand mission not found")
            cur.execute(
                """INSERT INTO product_concepts
                   (tenant_id,mission_id,name,description,category,estimated_cost_cents,
                    estimated_preparation_time_minutes,target_location_id,target_segment,presentation_mode,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                (
                    tenant_id,
                    body.missionId,
                    body.name.strip(),
                    body.description.strip(),
                    body.category.strip(),
                    body.estimatedCostCents,
                    body.estimatedPreparationTimeMinutes,
                    body.targetLocationId,
                    body.targetSegment,
                    body.presentationMode,
                    actor_id,
                ),
            )
            concept_id = int(cur.fetchone()[0])
            for index, variant in enumerate(body.variants or []):
                cur.execute(
                    """INSERT INTO product_concept_variants
                       (tenant_id,concept_id,variant_key,name,image_url,description,price_cents,
                        deal_json,serving_claim,weight,is_control)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
                    (
                        tenant_id,
                        concept_id,
                        variant.variantKey,
                        variant.name.strip(),
                        variant.imageUrl,
                        variant.description.strip(),
                        variant.priceCents,
                        json.dumps(variant.deal),
                        variant.servingClaim,
                        variant.weight,
                        variant.isControl or index == 0,
                    ),
                )
    return get_product_concept(concept_id, admin)


@router.get("/product-concepts/public")
def list_public_product_concepts(tenant: TenantContext = Depends(resolve_public_tenant)):
    if not has_feature(tenant.id, "missions.product_demand_test"):
        return {"items": []}
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,mission_id,name,description,category,estimated_cost_cents,
                          estimated_preparation_time_minutes,target_location_id,target_segment,status,
                          created_by,presentation_mode,created_at,updated_at
                   FROM product_concepts
                   WHERE tenant_id=%s AND status IN ('APPROVED','RUNNING')
                   ORDER BY updated_at DESC LIMIT 30""",
                (tenant.id,),
            )
            concepts = []
            for row in cur.fetchall():
                concepts.append(_load_concept(cur, tenant.id, int(row[0]), public_only=True))
            return {"items": [item for item in concepts if item]}


@router.get("/product-concepts/{concept_id}")
def get_product_concept(concept_id: int, admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    _require_feature(tenant_id, "missions.product_demand_test")
    with get_db() as conn:
        with conn.cursor() as cur:
            concept = _load_concept(cur, tenant_id, concept_id, public_only=False)
            if not concept:
                raise HTTPException(status_code=404, detail="Product concept not found")
            return concept


@router.post("/product-concepts/{concept_id}/{action}")
def transition_product_concept(concept_id: int, action: Literal["approve", "start", "pause", "complete", "cancel"], admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    _require_feature(tenant_id, "missions.product_demand_test")
    transitions = {
        "approve": ({"DRAFT", "NEEDS_APPROVAL"}, "APPROVED"),
        "start": ({"APPROVED", "PAUSED"}, "RUNNING"),
        "pause": ({"RUNNING"}, "PAUSED"),
        "complete": ({"RUNNING", "PAUSED"}, "COMPLETED"),
        "cancel": ({"DRAFT", "NEEDS_APPROVAL", "APPROVED", "RUNNING", "PAUSED"}, "CANCELLED"),
    }
    allowed, target = transitions[action]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM product_concepts WHERE tenant_id=%s AND id=%s FOR UPDATE", (tenant_id, concept_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Product concept not found")
            if row[0] not in allowed:
                raise HTTPException(status_code=409, detail=f"Concept cannot {action} from {row[0]}")
            cur.execute("UPDATE product_concepts SET status=%s,updated_at=NOW() WHERE tenant_id=%s AND id=%s", (target, tenant_id, concept_id))
    return get_product_concept(concept_id, admin)


def _load_concept(cursor, tenant_id: int, concept_id: int, *, public_only: bool) -> Optional[dict[str, Any]]:
    status_clause = "AND status IN ('APPROVED','RUNNING')" if public_only else ""
    cursor.execute(
        f"""SELECT id,mission_id,name,description,category,estimated_cost_cents,
                   estimated_preparation_time_minutes,target_location_id,target_segment,status,
                   created_by,presentation_mode,created_at,updated_at
            FROM product_concepts WHERE tenant_id=%s AND id=%s {status_clause}""",
        (tenant_id, concept_id),
    )
    row = cursor.fetchone()
    if not row:
        return None
    cursor.execute(
        """SELECT id,variant_key,name,image_url,description,price_cents,deal_json,serving_claim,weight,is_control
           FROM product_concept_variants WHERE tenant_id=%s AND concept_id=%s ORDER BY is_control DESC, weight DESC, id""",
        (tenant_id, concept_id),
    )
    return _concept_dict(row, [_variant_dict(variant) for variant in cursor.fetchall()])


def _record_interest(cursor, tenant_id: int, concept: dict[str, Any], body: ConceptInteractionInput, event_type: str) -> tuple[Optional[int], Optional[str]]:
    mission_id = concept.get("missionId")
    group = None
    if mission_id:
        cursor.execute("SELECT holdout_percentage FROM missions WHERE tenant_id=%s AND id=%s AND status='RUNNING'", (tenant_id, mission_id))
        row = cursor.fetchone()
        if row:
            group = assign_group(
                cursor,
                tenant_id=tenant_id,
                mission_id=int(mission_id),
                subject_type="visitor",
                subject_id=body.visitorId,
                holdout_percentage=int(row[0]),
            )
    event_key = f"concept:{concept['id']}:{event_type}:{body.sessionId}:{body.visitorId}"
    cursor.execute(
        """INSERT INTO product_interest_events
           (tenant_id,concept_id,variant_id,mission_id,event_key,visitor_id,session_id,event_type,
            preferred_price_cents,segment,geography,source,medium,campaign,properties)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
           ON CONFLICT (tenant_id,event_key) DO NOTHING
           RETURNING id""",
        (
            tenant_id,
            concept["id"],
            body.variantId,
            mission_id,
            event_key,
            body.visitorId,
            body.sessionId,
            event_type,
            body.preferredPriceCents,
            body.segment,
            body.geography,
            body.source,
            body.medium,
            body.campaign,
            json.dumps({**body.properties, "assignmentGroup": group}),
        ),
    )
    inserted = cursor.fetchone()
    return (int(inserted[0]) if inserted else None, group)


@router.post("/product-concepts/{concept_id}/interest")
def record_product_interest(concept_id: int, body: ConceptInteractionInput, tenant: TenantContext = Depends(resolve_public_tenant)):
    if not has_feature(tenant.id, "missions.product_demand_test"):
        return {"accepted": False}
    consume_intervention_rate(tenant.id, "product_concept_interest", "PRODUCT_CONCEPT_INTEREST_RATE_PER_MINUTE", 1000)
    with get_db() as conn:
        with conn.cursor() as cur:
            concept = _load_concept(cur, tenant.id, concept_id, public_only=True)
            if not concept:
                raise HTTPException(status_code=404, detail="Product concept not found")
            event_id, group = _record_interest(cur, tenant.id, concept, body, "INTEREST")
            return {"accepted": True, "eventId": event_id, "group": group, "notice": concept["availabilityNotice"]}


@router.post("/product-concepts/{concept_id}/waitlist")
def join_product_waitlist(concept_id: int, body: WaitlistInput, tenant: TenantContext = Depends(resolve_public_tenant)):
    if not has_feature(tenant.id, "missions.product_demand_test"):
        return {"accepted": False}
    consume_intervention_rate(tenant.id, "product_concept_waitlist", "PRODUCT_CONCEPT_WAITLIST_RATE_PER_MINUTE", 300)
    with get_db() as conn:
        with conn.cursor() as cur:
            concept = _load_concept(cur, tenant.id, concept_id, public_only=True)
            if not concept:
                raise HTTPException(status_code=404, detail="Product concept not found")
            event_id, group = _record_interest(cur, tenant.id, concept, body, "WAITLIST")
            cur.execute(
                """INSERT INTO product_waitlist_entries
                   (tenant_id,concept_id,variant_id,visitor_id,email,phone,segment,geography)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT DO NOTHING
                   RETURNING id""",
                (tenant.id, concept_id, body.variantId, body.visitorId, str(body.email) if body.email else None, body.phone, body.segment, body.geography),
            )
            row = cur.fetchone()
            return {"accepted": True, "eventId": event_id, "waitlistId": int(row[0]) if row else None, "group": group, "notice": concept["availabilityNotice"]}


@router.post("/product-concepts/{concept_id}/preorder")
def reserve_product_preorder(concept_id: int, body: PreorderInput, tenant: TenantContext = Depends(resolve_public_tenant)):
    if not has_feature(tenant.id, "missions.product_demand_test"):
        return {"accepted": False}
    consume_intervention_rate(tenant.id, "product_concept_preorder", "PRODUCT_CONCEPT_PREORDER_RATE_PER_MINUTE", 120)
    with get_db() as conn:
        with conn.cursor() as cur:
            concept = _load_concept(cur, tenant.id, concept_id, public_only=True)
            if not concept:
                raise HTTPException(status_code=404, detail="Product concept not found")
            if concept["presentationMode"] != "PREORDER":
                raise HTTPException(status_code=409, detail="This concept is not accepting preorders")
            variant = next((item for item in concept["variants"] if item["id"] == body.variantId), None) if body.variantId else None
            price_cents = body.priceCents or (variant or {}).get("priceCents")
            if price_cents is None:
                raise HTTPException(status_code=400, detail="Preorder requires priceCents")
            event_id, group = _record_interest(cur, tenant.id, concept, body, "PREORDER")
            cur.execute(
                """INSERT INTO product_preorders
                   (tenant_id,concept_id,variant_id,visitor_id,email,phone,quantity,price_cents,deposit_cents)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                (
                    tenant.id,
                    concept_id,
                    body.variantId,
                    body.visitorId,
                    str(body.email) if body.email else None,
                    body.phone,
                    body.quantity,
                    price_cents,
                    body.depositCents,
                ),
            )
            preorder_id = int(cur.fetchone()[0])
            return {"accepted": True, "eventId": event_id, "preorderId": preorder_id, "group": group, "notice": concept["availabilityNotice"]}
