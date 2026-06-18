import json
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from db import get_db
from dependencies.auth import TenantContext, get_current_admin, resolve_public_tenant
from services.audit import record_audit
from services.entitlements import has_feature, require_feature
from services.events import emit_server_event
from services.jobs import enqueue_job
from services.missions import MISSION_FEATURES, _eligible_margin_items, assign_group
from services.rate_limits import consume_intervention_rate

router = APIRouter()

MissionType = Literal[
    "ABANDONED_CART_RECOVERY",
    "INTELLIGENT_BUNDLE",
    "LAPSED_CUSTOMER_WINBACK",
    "QUIET_HOUR_DEMAND",
    "NEW_PRODUCT_DEMAND_TEST",
]
ActionType = Literal[
    "SEND_EMAIL",
    "SEND_SMS",
    "SEND_WHATSAPP",
    "SHOW_CART_UPSELL",
    "SHOW_PERSONALIZED_BANNER",
    "CREATE_LANDING_PAGE",
]


class MissionActionInput(BaseModel):
    type: ActionType
    sequence: int = Field(default=1, ge=1, le=20)
    config: dict[str, Any] = Field(default_factory=dict)


class MissionCreate(BaseModel):
    type: MissionType
    name: str = Field(min_length=3, max_length=200)
    objective: str = Field(min_length=10, max_length=3000)
    hypothesis: str = Field(min_length=10, max_length=3000)
    startAt: Optional[datetime] = None
    endAt: Optional[datetime] = None
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    budgetLimitCents: Optional[int] = Field(default=None, ge=0)
    discountLimitCents: Optional[int] = Field(default=None, ge=0)
    minimumMarginCents: Optional[int] = None
    maximumRedemptions: Optional[int] = Field(default=None, ge=1)
    capacityLimit: Optional[int] = Field(default=None, ge=1)
    audience: dict[str, Any] = Field(default_factory=dict)
    holdoutPercentage: int = Field(default=10, ge=0, le=50)
    primaryMetric: str = Field(default="incremental_orders", min_length=2, max_length=80)
    guardrailMetrics: list[str] = Field(default_factory=lambda: ["contribution_margin", "unsubscribes"], max_length=20)
    actions: list[MissionActionInput] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_actions(self):
        if len({item.sequence for item in self.actions}) != len(self.actions):
            raise ValueError("Action sequence numbers must be unique")
        if self.endAt and self.startAt and self.endAt <= self.startAt:
            raise ValueError("endAt must be after startAt")
        if self.type == "INTELLIGENT_BUNDLE" and not any(item.type == "SHOW_CART_UPSELL" for item in self.actions):
            raise ValueError("Intelligent bundle missions require SHOW_CART_UPSELL")
        if self.type == "INTELLIGENT_BUNDLE" and not (
            isinstance(self.audience.get("itemAId"), int) and isinstance(self.audience.get("itemBId"), int)
        ):
            raise ValueError("Intelligent bundle missions require audience.itemAId and audience.itemBId")
        if self.type == "QUIET_HOUR_DEMAND" and not any(
            item.type in {"SEND_EMAIL", "SEND_SMS", "SEND_WHATSAPP", "SHOW_PERSONALIZED_BANNER"} for item in self.actions
        ):
            raise ValueError("Quiet-hour demand missions require a message or personalized banner action")
        if self.type == "NEW_PRODUCT_DEMAND_TEST" and not any(item.type == "CREATE_LANDING_PAGE" for item in self.actions):
            raise ValueError("New product demand tests require CREATE_LANDING_PAGE")
        if self.type == "NEW_PRODUCT_DEMAND_TEST" and self.capacityLimit is not None:
            raise ValueError("New product demand tests use preorder and waitlist limits, not kitchen capacityLimit")
        if len(json.dumps(self.audience)) > 16384 or any(len(json.dumps(action.config)) > 32768 for action in self.actions):
            raise ValueError("Mission audience or action config is too large")
        return self


class BundleAssignmentRequest(BaseModel):
    visitorId: str = Field(min_length=8, max_length=100)
    sessionId: str = Field(min_length=8, max_length=100)
    cartId: str = Field(min_length=8, max_length=100)


class QuietHourAssignmentRequest(BaseModel):
    visitorId: str = Field(min_length=8, max_length=100)
    sessionId: str = Field(min_length=8, max_length=100)
    locationId: Optional[int] = Field(default=None, ge=1)
    segment: Optional[str] = Field(default=None, max_length=80)


def _feature_for_body(body: MissionCreate):
    return require_feature(MISSION_FEATURES[body.type])


_SELECT = """id,opportunity_id,type,name,objective,hypothesis,start_at,end_at,timezone,
budget_limit_cents,discount_limit_cents,minimum_margin_cents,maximum_redemptions,capacity_limit,
audience_definition,holdout_percentage,primary_metric,guardrail_metrics,status,approved_at,
started_at,completed_at,created_at,updated_at"""


def _dict(row: tuple) -> dict[str, Any]:
    keys = ["id","opportunityId","type","name","objective","hypothesis","startAt","endAt","timezone","budgetLimitCents","discountLimitCents","minimumMarginCents","maximumRedemptions","capacityLimit","audience","holdoutPercentage","primaryMetric","guardrailMetrics","status","approvedAt","startedAt","completedAt","createdAt","updatedAt"]
    values = list(row)
    for index in (6,7,19,20,21,22,23):
        values[index] = values[index].isoformat() if values[index] else None
    return dict(zip(keys, values))


def _ensure_feature(tenant_id: int, mission_type: str):
    from services.entitlements import has_feature
    if not has_feature(tenant_id, MISSION_FEATURES[mission_type]):
        raise HTTPException(status_code=403, detail=f"Feature '{MISSION_FEATURES[mission_type]}' is not enabled")


@router.get("/missions")
def list_missions(status: Optional[str] = None, limit: int = Query(50, ge=1, le=100), admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    enabled_types = {mission_type for mission_type, feature in MISSION_FEATURES.items() if has_feature(tenant_id, feature)}
    params: list[Any] = [tenant_id]
    where = "tenant_id = %s"
    if status:
        where += " AND status = %s"; params.append(status)
    params.append(limit)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {_SELECT} FROM missions WHERE {where} ORDER BY updated_at DESC LIMIT %s", params)
            items = [_dict(row) for row in cur.fetchall()]
            items = [item for item in items if item["type"] in enabled_types]
    return {"items": items}


@router.post("/missions", status_code=201)
def create_mission(body: MissionCreate, admin: dict = Depends(get_current_admin)):
    tenant_id, actor_id = int(admin["restaurant_id"]), str(admin["id"])
    _ensure_feature(tenant_id, body.type)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO missions
                   (tenant_id,type,name,objective,hypothesis,start_at,end_at,timezone,budget_limit_cents,
                    discount_limit_cents,minimum_margin_cents,maximum_redemptions,capacity_limit,
                    audience_definition,holdout_percentage,primary_metric,guardrail_metrics,status,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,'NEEDS_APPROVAL',%s)
                   RETURNING id""",
                (tenant_id,body.type,body.name.strip(),body.objective.strip(),body.hypothesis.strip(),body.startAt,body.endAt,body.timezone,body.budgetLimitCents,body.discountLimitCents,body.minimumMarginCents,body.maximumRedemptions,body.capacityLimit,json.dumps(body.audience),body.holdoutPercentage,body.primaryMetric,json.dumps(body.guardrailMetrics),actor_id),
            )
            mission_id = int(cur.fetchone()[0])
            channel_by_action = {"SEND_EMAIL":"email","SEND_SMS":"sms","SEND_WHATSAPP":"whatsapp"}
            for action in body.actions:
                cur.execute("INSERT INTO mission_actions (tenant_id,mission_id,action_type,sequence_number,channel,config) VALUES (%s,%s,%s,%s,%s,%s::jsonb)", (tenant_id,mission_id,action.type,action.sequence,channel_by_action.get(action.type),json.dumps(action.config)))
            record_audit(cur,tenant_id=tenant_id,actor_type="admin",actor_id=actor_id,action="mission.created",resource_type="mission",resource_id=str(mission_id),after={"type":body.type,"status":"NEEDS_APPROVAL"})
    return get_mission(mission_id, admin)


@router.get("/missions/{mission_id}")
def get_mission(mission_id: int, admin: dict = Depends(get_current_admin)):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {_SELECT} FROM missions WHERE tenant_id = %s AND id = %s", (tenant_id,mission_id))
            row = cur.fetchone()
            if not row: raise HTTPException(status_code=404,detail="Mission not found")
            _ensure_feature(tenant_id,row[2])
            result = _dict(row)
            cur.execute("SELECT id,action_type,sequence_number,channel,config,status FROM mission_actions WHERE tenant_id = %s AND mission_id = %s ORDER BY sequence_number", (tenant_id,mission_id))
            result["actions"] = [{"id":a[0],"type":a[1],"sequence":a[2],"channel":a[3],"config":a[4],"status":a[5]} for a in cur.fetchall()]
            cur.execute("SELECT treatment_size,holdout_size,treatment_conversions,holdout_conversions,incremental_orders,revenue_cents,incremental_revenue_cents,contribution_margin_cents,discount_cost_cents,message_cost_cents,metrics,evaluated_at FROM mission_results WHERE tenant_id = %s AND mission_id = %s ORDER BY evaluated_at DESC LIMIT 1", (tenant_id,mission_id))
            latest = cur.fetchone()
            result["latestResult"] = None if not latest else {"treatmentSize":latest[0],"holdoutSize":latest[1],"treatmentConversions":latest[2],"holdoutConversions":latest[3],"incrementalOrders":float(latest[4]),"revenueCents":latest[5],"incrementalRevenueCents":latest[6],"contributionMarginCents":latest[7],"discountCostCents":latest[8],"messageCostCents":latest[9],"metrics":latest[10],"evaluatedAt":latest[11].isoformat()}
    return result


def _transition(mission_id: int, action: str, admin: dict):
    transitions = {"approve":({"NEEDS_APPROVAL","DRAFT"},"APPROVED"),"start":({"APPROVED","SCHEDULED","PAUSED"},"RUNNING"),"pause":({"RUNNING"},"PAUSED"),"cancel":({"DRAFT","NEEDS_APPROVAL","APPROVED","SCHEDULED","RUNNING","PAUSED"},"CANCELLED")}
    allowed,target = transitions[action]
    tenant_id,actor_id = int(admin["restaurant_id"]),str(admin["id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT type,status FROM missions WHERE tenant_id = %s AND id = %s FOR UPDATE",(tenant_id,mission_id)); row=cur.fetchone()
            if not row: raise HTTPException(status_code=404,detail="Mission not found")
            _ensure_feature(tenant_id,row[0])
            if row[1] not in allowed: raise HTTPException(status_code=409,detail=f"Mission cannot {action} from {row[1]}")
            setters="status=%s,updated_at=NOW()"; params: list[Any]=[target]
            if action=="approve": setters+=",approval_user_id=%s,approved_at=NOW()"; params.append(actor_id)
            if action=="start": setters+=",started_at=COALESCE(started_at,NOW())"
            params.extend([tenant_id,mission_id]); cur.execute(f"UPDATE missions SET {setters} WHERE tenant_id=%s AND id=%s",params)
            event = "mission_started" if action=="start" else "mission_paused" if action=="pause" else None
            if event: emit_server_event(cur,tenant_id=tenant_id,event_name=event,event_id=f"mission-{action}:{mission_id}:{datetime.utcnow().isoformat()}",mission_id=str(mission_id),properties={"fromStatus":row[1],"toStatus":target})
            record_audit(cur,tenant_id=tenant_id,actor_type="admin",actor_id=actor_id,action=f"mission.{action}",resource_type="mission",resource_id=str(mission_id),before={"status":row[1]},after={"status":target})
    return get_mission(mission_id,admin)


@router.post("/missions/{mission_id}/approve")
def approve(mission_id:int,admin:dict=Depends(get_current_admin)): return _transition(mission_id,"approve",admin)
@router.post("/missions/{mission_id}/start")
def start(mission_id:int,admin:dict=Depends(get_current_admin)): return _transition(mission_id,"start",admin)
@router.post("/missions/{mission_id}/pause")
def pause(mission_id:int,admin:dict=Depends(get_current_admin)): return _transition(mission_id,"pause",admin)
@router.post("/missions/{mission_id}/cancel")
def cancel(mission_id:int,admin:dict=Depends(get_current_admin)): return _transition(mission_id,"cancel",admin)


@router.post("/missions/{mission_id}/evaluate",status_code=202)
def evaluate(mission_id:int,admin:dict=Depends(get_current_admin)):
    tenant_id=int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT type FROM missions WHERE tenant_id=%s AND id=%s",(tenant_id,mission_id)); row=cur.fetchone()
            if not row: raise HTTPException(status_code=404,detail="Mission not found")
            _ensure_feature(tenant_id,row[0])
            job_by_type={
                "ABANDONED_CART_RECOVERY":"missions.evaluate_abandoned_carts",
                "INTELLIGENT_BUNDLE":"missions.evaluate_bundles",
                "LAPSED_CUSTOMER_WINBACK":"missions.evaluate_lapsed_customers",
                "QUIET_HOUR_DEMAND":"missions.evaluate_quiet_hours",
                "NEW_PRODUCT_DEMAND_TEST":"missions.evaluate_product_demand_tests",
            }
            job=job_by_type[row[0]]; job_id=enqueue_job(cur,tenant_id=tenant_id,job_name=job,idempotency_key=f"mission-evaluate:{mission_id}:{datetime.utcnow().strftime('%Y%m%d%H')}",metadata={"missionId":mission_id})
    return {"jobId":job_id,"status":"queued" if job_id else "already_queued"}


@router.post("/mission-assignments/bundle")
def bundle_assignment(body: BundleAssignmentRequest, tenant: TenantContext = Depends(resolve_public_tenant)):
    if not has_feature(tenant.id, "missions.bundle"):
        return {"assigned": False, "bundle": None}
    consume_intervention_rate(tenant.id, "mission_bundle_assignment", "MISSION_ASSIGNMENT_RATE_PER_MINUTE", 1000)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,holdout_percentage,audience_definition,minimum_margin_cents
                   FROM missions WHERE tenant_id=%s AND type='INTELLIGENT_BUNDLE' AND status='RUNNING'
                     AND (start_at IS NULL OR start_at<=NOW()) AND (end_at IS NULL OR end_at>NOW())
                   ORDER BY started_at,id LIMIT 20""",
                (tenant.id,),
            )
            for mission_id, holdout, audience, minimum_margin in cur.fetchall():
                audience = audience or {}
                item_ids = [audience.get("itemAId"), audience.get("itemBId")]
                if not all(isinstance(value, int) for value in item_ids):
                    continue
                cur.execute("SELECT id,name,price_cents,sale_price_cents,ingredient_cost_cents,packaging_cost_cents,image FROM menu_items WHERE restaurant_id=%s AND id=ANY(%s) AND is_available=true", (tenant.id,item_ids))
                rows = cur.fetchall()
                if len(rows) != 2:
                    continue
                rows.sort(key=lambda row: item_ids.index(row[0]))
                regular = sum(int(row[3] if row[3] is not None else row[2]) for row in rows)
                proposed = int(audience.get("proposedBundlePriceCents", regular))
                cost = sum(int(row[4] or 0)+int(row[5] or 0) for row in rows)
                if proposed < cost + int(minimum_margin or 0):
                    continue
                group = assign_group(cur,tenant_id=tenant.id,mission_id=int(mission_id),subject_type="visitor",subject_id=body.visitorId,holdout_percentage=int(holdout))
                cur.execute("INSERT INTO mission_audiences (tenant_id,mission_id,subject_type,subject_id,eligibility_snapshot,eligible,reason) VALUES (%s,%s,'visitor',%s,%s::jsonb,true,'eligible') ON CONFLICT (mission_id,subject_type,subject_id) DO UPDATE SET eligibility_snapshot=EXCLUDED.eligibility_snapshot,eligible=true,reason='eligible',evaluated_at=NOW()", (tenant.id,mission_id,body.visitorId,json.dumps({"cartId":body.cartId,"regularPriceCents":regular,"proposedBundlePriceCents":proposed})))
                if group == "holdout":
                    return {"assigned": False, "bundle": None, "group": "holdout"}
                event_key=f"bundle-shown:{mission_id}:{body.sessionId}"
                cur.execute("INSERT INTO mission_events (tenant_id,mission_id,event_key,event_type,subject_type,subject_id,cart_id,properties) VALUES (%s,%s,%s,'bundle_shown','visitor',%s,%s,%s::jsonb) ON CONFLICT DO NOTHING", (tenant.id,mission_id,event_key,body.visitorId,body.cartId,json.dumps({"regularPriceCents":regular,"proposedBundlePriceCents":proposed})))
                return {"assigned":True,"missionId":int(mission_id),"group":"treatment","bundle":{"items":[{"id":r[0],"name":r[1],"priceCents":int(r[3] if r[3] is not None else r[2]),"image":r[6]} for r in rows],"regularPriceCents":regular,"proposedBundlePriceCents":proposed,"discountCents":regular-proposed,"contributionMarginCents":proposed-cost}}
    return {"assigned": False, "bundle": None}


@router.post("/mission-assignments/quiet-hour")
def quiet_hour_assignment(body: QuietHourAssignmentRequest, tenant: TenantContext = Depends(resolve_public_tenant)):
    if not has_feature(tenant.id, "missions.quiet_hour"):
        return {"assigned": False, "offer": None}
    consume_intervention_rate(tenant.id, "mission_quiet_hour_assignment", "MISSION_ASSIGNMENT_RATE_PER_MINUTE", 1000)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT m.id,m.holdout_percentage,m.audience_definition,m.minimum_margin_cents,
                          m.maximum_redemptions,q.capacity_setting_id,q.location_id,q.time_start,q.time_end,
                          q.maximum_capacity_orders
                   FROM missions m
                   JOIN quiet_hour_candidates q ON q.tenant_id = m.tenant_id
                    AND q.status = 'CANDIDATE'
                    AND (m.audience_definition->>'capacitySettingId' IS NULL OR (m.audience_definition->>'capacitySettingId')::bigint = q.capacity_setting_id)
                   WHERE m.tenant_id=%s AND m.type='QUIET_HOUR_DEMAND' AND m.status='RUNNING'
                     AND (m.start_at IS NULL OR m.start_at<=NOW()) AND (m.end_at IS NULL OR m.end_at>NOW())
                     AND q.weekday = EXTRACT(DOW FROM NOW())::int
                     AND NOW()::time >= q.time_start AND NOW()::time < q.time_end
                     AND (%s::int IS NULL OR q.location_id = %s)
                   ORDER BY m.started_at, m.id LIMIT 20""",
                (tenant.id, body.locationId, body.locationId),
            )
            for mission_id, holdout, audience, minimum_margin, maximum_redemptions, setting_id, location_id, time_start, time_end, maximum_capacity in cur.fetchall():
                audience = audience or {}
                if audience.get("targetSegment") and audience.get("targetSegment") != body.segment:
                    continue
                if maximum_redemptions:
                    cur.execute(
                        "SELECT count(*) FROM mission_events WHERE tenant_id=%s AND mission_id=%s AND event_type='quiet_hour_banner_shown'",
                        (tenant.id, mission_id),
                    )
                    if int(cur.fetchone()[0]) >= int(maximum_redemptions):
                        continue
                cur.execute(
                    """SELECT count(*) FROM orders
                       WHERE restaurant_id=%s AND branch_id=%s AND created_at::date=CURRENT_DATE
                         AND created_at::time >= %s::time AND created_at::time < %s::time
                         AND lower(status) NOT IN ('cancelled','canceled','failed')""",
                    (tenant.id, location_id, time_start, time_end),
                )
                current_orders = int(cur.fetchone()[0])
                if current_orders >= int(audience.get("capacityLimit", maximum_capacity)):
                    continue
                items = _eligible_margin_items(cur, tenant.id, minimum_margin)
                if not items:
                    continue
                group = assign_group(cur, tenant_id=tenant.id, mission_id=int(mission_id), subject_type="visitor", subject_id=body.visitorId, holdout_percentage=int(holdout))
                snapshot = {
                    "capacitySettingId": int(setting_id),
                    "locationId": int(location_id),
                    "segment": body.segment,
                    "currentOrders": current_orders,
                    "maximumCapacityOrders": int(maximum_capacity),
                    "items": items[:5],
                }
                cur.execute(
                    """INSERT INTO mission_audiences
                       (tenant_id,mission_id,subject_type,subject_id,eligibility_snapshot,eligible,reason)
                       VALUES (%s,%s,'visitor',%s,%s::jsonb,true,'eligible')
                       ON CONFLICT (mission_id,subject_type,subject_id) DO UPDATE SET
                         eligibility_snapshot=EXCLUDED.eligibility_snapshot,eligible=true,reason='eligible',evaluated_at=NOW()""",
                    (tenant.id, mission_id, body.visitorId, json.dumps(snapshot)),
                )
                if group == "holdout":
                    return {"assigned": False, "offer": None, "group": "holdout"}
                cur.execute(
                    """INSERT INTO mission_events
                       (tenant_id,mission_id,event_key,event_type,subject_type,subject_id,properties)
                       VALUES (%s,%s,%s,'quiet_hour_banner_shown','visitor',%s,%s::jsonb)
                       ON CONFLICT DO NOTHING""",
                    (tenant.id, mission_id, f"quiet-hour-banner:{mission_id}:{body.sessionId}", body.visitorId, json.dumps(snapshot)),
                )
                return {
                    "assigned": True,
                    "missionId": int(mission_id),
                    "group": "treatment",
                    "offer": {
                        "headline": audience.get("headline", "Quiet hour special"),
                        "body": audience.get("body", "Fresh favorites are moving fast right now."),
                        "locationId": int(location_id),
                        "items": items[:5],
                    },
                }
    return {"assigned": False, "offer": None}
