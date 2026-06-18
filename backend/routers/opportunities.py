import json
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from db import get_db
from dependencies.auth import get_current_admin
from services.audit import record_audit
from services.entitlements import has_feature, require_feature

router = APIRouter()

OpportunityStatus = Literal[
    "DETECTED", "NEEDS_REVIEW", "RECOMMENDED", "APPROVED", "DISMISSED",
    "CONVERTED_TO_EXPERIMENT", "CONVERTED_TO_MISSION", "RESOLVED", "EXPIRED",
]

OPPORTUNITY_TYPES = {
    "HIGH_ATTENTION_LOW_CONVERSION", "HIDDEN_WINNER", "WEAK_ITEM", "CHECKOUT_DROP",
    "DELIVERY_FEE_SHOCK", "PAYMENT_FAILURE", "MINIMUM_ORDER_FRICTION", "SEARCH_NO_RESULT",
    "SEARCH_LOW_RELEVANCE", "CHAT_OBJECTION", "CAMPAIGN_MISMATCH", "BUNDLE_OPPORTUNITY",
    "UNAVAILABLE_ITEM_LOSS", "LAPSED_CUSTOMER_POOL", "QUIET_HOUR", "COMPETITOR_PRICE_GAP",
    "COMPETITOR_DEAL_GAP", "MENU_OVERLOAD", "NEW_PRODUCT_DEMAND_SIGNAL",
}


class DismissRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class CommentRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CreateExperimentRequest(BaseModel):
    experimentType: str = Field(default="BUTTON_COPY", max_length=40)
    name: Optional[str] = Field(default=None, max_length=200)
    placement: str = Field(default="OPPORTUNITY", min_length=1, max_length=100)
    minimumSample: int = Field(default=100, ge=20, le=1000000)


class CreateMissionRequest(BaseModel):
    missionType: Literal["ABANDONED_CART_RECOVERY", "INTELLIGENT_BUNDLE", "LAPSED_CUSTOMER_WINBACK"]
    name: Optional[str] = Field(default=None, max_length=200)
    holdoutPercentage: int = Field(default=10, ge=0, le=50)


_SELECT = """id, type, entity_type, entity_id, location_id, period_start, period_end,
headline, summary, estimated_revenue_impact_cents, estimated_margin_impact_cents,
impact_score, confidence_score, effort_score, urgency_score, priority_score,
evidence_json, recommended_action_json, ai_explanation_json, detector_version,
trend, status, first_detected_at, last_detected_at, viewed_at, view_count,
approved_at, approved_by, dismissed_at, dismissed_by, dismissal_reason, created_at, updated_at"""


def _serialize(row: tuple) -> dict:
    date_indexes = {5, 6, 22, 23, 24, 26, 28, 31, 32}
    values = [value.isoformat() if index in date_indexes and value else value for index, value in enumerate(row)]
    for index in (11, 12, 13, 14, 15):
        values[index] = float(values[index])
    return dict(zip([
        "id", "type", "entityType", "entityId", "locationId", "periodStart", "periodEnd",
        "headline", "summary", "estimatedRevenueImpactCents", "estimatedMarginImpactCents",
        "impactScore", "confidenceScore", "effortScore", "urgencyScore", "priorityScore",
        "evidence", "recommendedAction", "aiExplanation", "detectorVersion", "trend", "status",
        "firstDetectedAt", "lastDetectedAt", "viewedAt", "viewCount", "approvedAt", "approvedBy",
        "dismissedAt", "dismissedBy", "dismissalReason", "createdAt", "updatedAt",
    ], values))


@router.get("/opportunities")
def list_opportunities(
    status: Optional[OpportunityStatus] = Query(default=None),
    opportunityType: Optional[str] = Query(default=None, max_length=60),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    admin: dict = Depends(get_current_admin),
    _feature=Depends(require_feature("opportunities.weekly_cards")),
):
    if opportunityType and opportunityType not in OPPORTUNITY_TYPES:
        raise HTTPException(status_code=422, detail="Unknown opportunity type")
    tenant_id = int(admin["restaurant_id"])
    filters = ["tenant_id = %s"]
    params: list = [tenant_id]
    if status:
        filters.append("status = %s")
        params.append(status)
    if opportunityType:
        filters.append("type = %s")
        params.append(opportunityType)
    params.extend([limit, offset])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM opportunities WHERE {' AND '.join(filters)}", params[:-2])
            total = int(cur.fetchone()[0])
            cur.execute(
                f"SELECT {_SELECT} FROM opportunities WHERE {' AND '.join(filters)} ORDER BY priority_score DESC, last_detected_at DESC LIMIT %s OFFSET %s",
                params,
            )
            rows = cur.fetchall()
    return {"total": total, "limit": limit, "offset": offset, "items": [_serialize(row) for row in rows]}


@router.get("/opportunities/{opportunity_id}")
def get_opportunity(
    opportunity_id: int,
    admin: dict = Depends(get_current_admin),
    _feature=Depends(require_feature("opportunities.weekly_cards")),
):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {_SELECT} FROM opportunities WHERE tenant_id = %s AND id = %s FOR UPDATE", (tenant_id, opportunity_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Opportunity not found")
            cur.execute("UPDATE opportunities SET viewed_at = NOW(), view_count = view_count + 1 WHERE tenant_id = %s AND id = %s", (tenant_id, opportunity_id))
            cur.execute(
                "INSERT INTO opportunity_actions (tenant_id, opportunity_id, actor_type, actor_id, action, metadata) VALUES (%s,%s,'admin',%s,'viewed','{}'::jsonb)",
                (tenant_id, opportunity_id, str(admin["id"])),
            )
            cur.execute(
                "SELECT action, from_status, to_status, metadata, created_at, actor_id FROM opportunity_actions WHERE tenant_id = %s AND opportunity_id = %s ORDER BY created_at DESC LIMIT 100",
                (tenant_id, opportunity_id),
            )
            actions = cur.fetchall()
            cur.execute(
                "SELECT id, actor_id, body, created_at FROM opportunity_comments WHERE tenant_id = %s AND opportunity_id = %s ORDER BY created_at LIMIT 100",
                (tenant_id, opportunity_id),
            )
            comments = cur.fetchall()
    result = _serialize(row)
    result["viewCount"] = int(result["viewCount"]) + 1
    result["actions"] = [{"action": a[0], "fromStatus": a[1], "toStatus": a[2], "metadata": a[3], "createdAt": a[4].isoformat(), "actorId": a[5]} for a in actions]
    result["comments"] = [{"id": c[0], "actorId": c[1], "body": c[2], "createdAt": c[3].isoformat()} for c in comments]
    return result


def _transition(opportunity_id: int, target: str, action: str, admin: dict, reason: Optional[str] = None) -> dict:
    tenant_id = int(admin["restaurant_id"])
    actor_id = str(admin["id"])
    allowed = {"DETECTED", "NEEDS_REVIEW", "RECOMMENDED"}
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {_SELECT} FROM opportunities WHERE tenant_id = %s AND id = %s FOR UPDATE", (tenant_id, opportunity_id))
            before = cur.fetchone()
            if not before:
                raise HTTPException(status_code=404, detail="Opportunity not found")
            previous = before[21]
            if previous not in allowed:
                raise HTTPException(status_code=409, detail=f"Opportunity cannot be {action} from status {previous}")
            if target == "APPROVED":
                cur.execute("UPDATE opportunities SET status = 'APPROVED', approved_at = NOW(), approved_by = %s, updated_at = NOW() WHERE tenant_id = %s AND id = %s", (actor_id, tenant_id, opportunity_id))
            else:
                cur.execute("UPDATE opportunities SET status = 'DISMISSED', dismissed_at = NOW(), dismissed_by = %s, dismissal_reason = %s, updated_at = NOW() WHERE tenant_id = %s AND id = %s", (actor_id, reason, tenant_id, opportunity_id))
            cur.execute(
                "INSERT INTO opportunity_actions (tenant_id, opportunity_id, actor_type, actor_id, action, from_status, to_status, metadata) VALUES (%s,%s,'admin',%s,%s,%s,%s,%s::jsonb)",
                (tenant_id, opportunity_id, actor_id, action, previous, target, json.dumps({"reason": reason} if reason else {})),
            )
            record_audit(cur, tenant_id=tenant_id, actor_type="admin", actor_id=actor_id, action=f"opportunity.{action}", resource_type="opportunity", resource_id=str(opportunity_id), before={"status": previous}, after={"status": target, "reason": reason})
            cur.execute(f"SELECT {_SELECT} FROM opportunities WHERE tenant_id = %s AND id = %s", (tenant_id, opportunity_id))
            updated = cur.fetchone()
    return _serialize(updated)


@router.post("/opportunities/{opportunity_id}/approve")
def approve_opportunity(opportunity_id: int, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("opportunities.weekly_cards"))):
    return _transition(opportunity_id, "APPROVED", "approved", admin)


@router.post("/opportunities/{opportunity_id}/dismiss")
def dismiss_opportunity(body: DismissRequest, opportunity_id: int, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("opportunities.weekly_cards"))):
    return _transition(opportunity_id, "DISMISSED", "dismissed", admin, body.reason.strip())


@router.post("/opportunities/{opportunity_id}/comments", status_code=201)
def add_comment(body: CommentRequest, opportunity_id: int, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("opportunities.weekly_cards"))):
    tenant_id = int(admin["restaurant_id"])
    actor_id = str(admin["id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM opportunity_actions WHERE tenant_id = %s AND actor_id = %s AND action = 'commented' AND created_at >= NOW() - INTERVAL '1 hour'", (tenant_id, actor_id))
            if int(cur.fetchone()[0]) >= 30:
                raise HTTPException(status_code=429, detail="Opportunity comment rate limit exceeded")
            cur.execute("SELECT 1 FROM opportunities WHERE tenant_id = %s AND id = %s", (tenant_id, opportunity_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Opportunity not found")
            cur.execute("INSERT INTO opportunity_comments (tenant_id, opportunity_id, actor_id, body) VALUES (%s,%s,%s,%s) RETURNING id, created_at", (tenant_id, opportunity_id, actor_id, body.body.strip()))
            row = cur.fetchone()
            cur.execute("INSERT INTO opportunity_actions (tenant_id, opportunity_id, actor_type, actor_id, action, metadata) VALUES (%s,%s,'admin',%s,'commented','{}'::jsonb)", (tenant_id, opportunity_id, actor_id))
    return {"id": row[0], "body": body.body.strip(), "actorId": actor_id, "createdAt": row[1].isoformat()}


@router.post("/opportunities/{opportunity_id}/create-experiment", status_code=201)
def create_experiment_from_opportunity(body: CreateExperimentRequest, opportunity_id: int, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("opportunities.weekly_cards"))):
    allowed_types = {"PRODUCT_IMAGE","PRODUCT_NAME","PRODUCT_DESCRIPTION","PRODUCT_POSITION","SERVING_INFORMATION","PRICE","DEAL","BUTTON_COPY","LANDING_PAGE","MODIFIER_DEFAULT","UPSELL","CHAT_RECOMMENDATION","MENU_LAYOUT"}
    if body.experimentType not in allowed_types:
        raise HTTPException(status_code=422, detail="Unknown experiment type")
    tenant_id, actor_id = int(admin["restaurant_id"]), str(admin["id"])
    if not has_feature(tenant_id, "experiments.enabled"):
        raise HTTPException(status_code=403, detail="Experiments are not enabled")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status,headline,summary,entity_type,entity_id,recommended_action_json FROM opportunities WHERE tenant_id=%s AND id=%s FOR UPDATE", (tenant_id, opportunity_id))
            row = cur.fetchone()
            if not row: raise HTTPException(status_code=404, detail="Opportunity not found")
            if row[0] != "APPROVED": raise HTTPException(status_code=409, detail=f"Opportunity cannot be converted from status {row[0]}")
            name = (body.name or f"Test: {row[1]}").strip()
            conflict_key = f"{row[3] or 'opportunity'}:{row[4] or opportunity_id}:{body.placement}"
            cur.execute(
                """INSERT INTO experiments
                   (tenant_id,opportunity_id,type,name,hypothesis,entity_type,entity_id,placement,
                    primary_metric,guardrail_metrics,minimum_sample,conflict_key,status,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'order_conversion','["contribution_margin"]'::jsonb,%s,%s,'NEEDS_APPROVAL',%s)
                   RETURNING id""",
                (tenant_id,opportunity_id,body.experimentType,name,row[2],row[3],row[4],body.placement,body.minimumSample,conflict_key,actor_id),
            )
            experiment_id = int(cur.fetchone()[0])
            cur.execute("INSERT INTO experiment_variants (tenant_id,experiment_id,variant_key,name,config,weight,is_control) VALUES (%s,%s,'control','Control','{}'::jsonb,50,true),(%s,%s,'treatment','Treatment',%s::jsonb,50,false)", (tenant_id,experiment_id,tenant_id,experiment_id,json.dumps(row[5] or {})))
            cur.execute("UPDATE opportunities SET status='CONVERTED_TO_EXPERIMENT',updated_at=NOW() WHERE tenant_id=%s AND id=%s", (tenant_id,opportunity_id))
            cur.execute("INSERT INTO opportunity_actions (tenant_id,opportunity_id,actor_type,actor_id,action,from_status,to_status,metadata) VALUES (%s,%s,'admin',%s,'created_experiment','APPROVED','CONVERTED_TO_EXPERIMENT',%s::jsonb)", (tenant_id,opportunity_id,actor_id,json.dumps({"experimentId":experiment_id})))
            record_audit(cur,tenant_id=tenant_id,actor_type="admin",actor_id=actor_id,action="opportunity.created_experiment",resource_type="opportunity",resource_id=str(opportunity_id),before={"status":"APPROVED"},after={"status":"CONVERTED_TO_EXPERIMENT","experimentId":experiment_id})
    return {"experimentId": experiment_id, "status": "NEEDS_APPROVAL"}


@router.post("/opportunities/{opportunity_id}/create-mission", status_code=201)
def create_mission_from_opportunity(body: CreateMissionRequest, opportunity_id: int, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("opportunities.weekly_cards"))):
    feature_by_type = {"ABANDONED_CART_RECOVERY":"missions.abandoned_cart","INTELLIGENT_BUNDLE":"missions.bundle","LAPSED_CUSTOMER_WINBACK":"missions.lapsed_customer"}
    tenant_id, actor_id = int(admin["restaurant_id"]), str(admin["id"])
    if not has_feature(tenant_id, feature_by_type[body.missionType]):
        raise HTTPException(status_code=403, detail="Mission feature is not enabled")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status,headline,summary,evidence_json,recommended_action_json FROM opportunities WHERE tenant_id=%s AND id=%s FOR UPDATE", (tenant_id, opportunity_id))
            row = cur.fetchone()
            if not row: raise HTTPException(status_code=404, detail="Opportunity not found")
            if row[0] != "APPROVED": raise HTTPException(status_code=409, detail=f"Opportunity cannot be converted from status {row[0]}")
            name = (body.name or row[1]).strip()
            cur.execute(
                """INSERT INTO missions
                   (tenant_id,opportunity_id,type,name,objective,hypothesis,audience_definition,
                    holdout_percentage,primary_metric,guardrail_metrics,status,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,'incremental_orders','["contribution_margin","unsubscribes"]'::jsonb,'NEEDS_APPROVAL',%s)
                   RETURNING id""",
                (tenant_id,opportunity_id,body.missionType,name,row[2],row[2],json.dumps(row[3] or {}),body.holdoutPercentage,actor_id),
            )
            mission_id = int(cur.fetchone()[0])
            action_type, channel = {"ABANDONED_CART_RECOVERY":("SEND_EMAIL","email"),"LAPSED_CUSTOMER_WINBACK":("SEND_EMAIL","email"),"INTELLIGENT_BUNDLE":("SHOW_CART_UPSELL",None)}[body.missionType]
            cur.execute("INSERT INTO mission_actions (tenant_id,mission_id,action_type,sequence_number,channel,config) VALUES (%s,%s,%s,1,%s,%s::jsonb)", (tenant_id,mission_id,action_type,channel,json.dumps(row[4] or {})))
            cur.execute("UPDATE opportunities SET status='CONVERTED_TO_MISSION',updated_at=NOW() WHERE tenant_id=%s AND id=%s", (tenant_id,opportunity_id))
            cur.execute("INSERT INTO opportunity_actions (tenant_id,opportunity_id,actor_type,actor_id,action,from_status,to_status,metadata) VALUES (%s,%s,'admin',%s,'created_mission','APPROVED','CONVERTED_TO_MISSION',%s::jsonb)", (tenant_id,opportunity_id,actor_id,json.dumps({"missionId":mission_id})))
            record_audit(cur,tenant_id=tenant_id,actor_type="admin",actor_id=actor_id,action="opportunity.created_mission",resource_type="opportunity",resource_id=str(opportunity_id),before={"status":"APPROVED"},after={"status":"CONVERTED_TO_MISSION","missionId":mission_id})
    return {"missionId": mission_id, "status": "NEEDS_APPROVAL"}
