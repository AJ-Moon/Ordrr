import json
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from db import get_db
from dependencies.auth import TenantContext, get_current_admin, resolve_public_tenant
from services.audit import record_audit
from services.entitlements import has_feature, require_feature
from services.experiments import assign_variant, record_exposure
from services.jobs import enqueue_job
from services.rate_limits import consume_intervention_rate

router = APIRouter()

ExperimentType = Literal[
    "PRODUCT_IMAGE", "PRODUCT_NAME", "PRODUCT_DESCRIPTION", "PRODUCT_POSITION",
    "SERVING_INFORMATION", "PRICE", "DEAL", "BUTTON_COPY", "LANDING_PAGE",
    "MODIFIER_DEFAULT", "UPSELL", "CHAT_RECOMMENDATION", "MENU_LAYOUT",
]


class VariantInput(BaseModel):
    key: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=160)
    config: dict[str, Any] = Field(default_factory=dict)
    weight: int = Field(default=50, ge=1, le=10000)
    isControl: bool = False

    @model_validator(mode="after")
    def bounded_config(self):
        if len(json.dumps(self.config)) > 32768:
            raise ValueError("Variant config is too large")
        return self


class ExperimentCreate(BaseModel):
    type: ExperimentType
    name: str = Field(min_length=3, max_length=200)
    hypothesis: str = Field(min_length=10, max_length=3000)
    entityType: Optional[str] = Field(default=None, max_length=40)
    entityId: Optional[str] = Field(default=None, max_length=100)
    placement: str = Field(default="GENERIC", min_length=1, max_length=100)
    audience: dict[str, Any] = Field(default_factory=dict)
    primaryMetric: Literal["order_conversion"] = "order_conversion"
    guardrailMetrics: list[str] = Field(default_factory=lambda: ["contribution_margin"], max_length=20)
    minimumSample: int = Field(default=100, ge=20, le=1000000)
    confidenceLevel: float = Field(default=0.95, ge=0.80, le=0.999)
    allocationPercentage: int = Field(default=100, ge=1, le=100)
    conflictKey: str = Field(min_length=2, max_length=160)
    startsAt: Optional[datetime] = None
    endsAt: Optional[datetime] = None
    variants: list[VariantInput] = Field(min_length=2, max_length=10)

    @model_validator(mode="after")
    def validate_variants(self):
        if sum(1 for item in self.variants if item.isControl) != 1:
            raise ValueError("Exactly one control variant is required")
        if len({item.key for item in self.variants}) != len(self.variants):
            raise ValueError("Variant keys must be unique")
        if self.startsAt and self.endsAt and self.endsAt <= self.startsAt:
            raise ValueError("endsAt must be after startsAt")
        if len(json.dumps(self.audience)) > 16384:
            raise ValueError("Audience definition is too large")
        return self


class AssignmentRequest(BaseModel):
    visitorId: str = Field(min_length=8, max_length=100)
    customerId: Optional[str] = Field(default=None, max_length=100)
    audience: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bounded_audience(self):
        if len(json.dumps(self.audience)) > 8192:
            raise ValueError("Audience context is too large")
        return self


class ActiveAssignmentRequest(AssignmentRequest):
    placement: str = Field(min_length=1, max_length=100)


class ExposureRequest(BaseModel):
    assignmentId: int
    variantId: int
    visitorId: str = Field(min_length=8, max_length=100)
    sessionId: str = Field(min_length=8, max_length=100)
    exposureKey: str = Field(min_length=8, max_length=120)
    context: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bounded_context(self):
        if len(json.dumps(self.context)) > 8192:
            raise ValueError("Exposure context is too large")
        return self


def _experiment_dict(row: tuple) -> dict[str, Any]:
    return {
        "id": int(row[0]), "opportunityId": row[1], "type": row[2], "name": row[3],
        "hypothesis": row[4], "entityType": row[5], "entityId": row[6], "placement": row[7],
        "audience": row[8], "primaryMetric": row[9], "guardrailMetrics": row[10],
        "minimumSample": int(row[11]), "confidenceLevel": float(row[12]),
        "allocationPercentage": int(row[13]), "conflictKey": row[14], "status": row[15],
        "startsAt": row[16].isoformat() if row[16] else None, "endsAt": row[17].isoformat() if row[17] else None,
        "approvedAt": row[18].isoformat() if row[18] else None,
        "createdAt": row[19].isoformat(), "updatedAt": row[20].isoformat(),
    }


_SELECT = """id, opportunity_id, type, name, hypothesis, entity_type, entity_id, placement,
audience_definition, primary_metric, guardrail_metrics, minimum_sample, confidence_level,
allocation_percentage, conflict_key, status, starts_at, ends_at, approved_at, created_at, updated_at"""


@router.get("/experiments")
def list_experiments(status: Optional[str] = None, limit: int = Query(50, ge=1, le=100), admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("experiments.enabled"))):
    tenant_id = int(admin["restaurant_id"])
    params: list[Any] = [tenant_id]
    where = "tenant_id = %s"
    if status:
        where += " AND status = %s"
        params.append(status)
    params.append(limit)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {_SELECT} FROM experiments WHERE {where} ORDER BY updated_at DESC LIMIT %s", params)
            items = [_experiment_dict(row) for row in cur.fetchall()]
    return {"items": items}


@router.post("/experiments", status_code=201)
def create_experiment(body: ExperimentCreate, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("experiments.enabled"))):
    tenant_id, actor_id = int(admin["restaurant_id"]), str(admin["id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO experiments
                   (tenant_id,type,name,hypothesis,entity_type,entity_id,placement,audience_definition,
                    primary_metric,guardrail_metrics,minimum_sample,confidence_level,allocation_percentage,
                    conflict_key,status,starts_at,ends_at,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s,%s,%s,'NEEDS_APPROVAL',%s,%s,%s)
                   RETURNING id""",
                (tenant_id, body.type, body.name.strip(), body.hypothesis.strip(), body.entityType,
                 body.entityId, body.placement, json.dumps(body.audience), body.primaryMetric,
                 json.dumps(body.guardrailMetrics), body.minimumSample, body.confidenceLevel,
                 body.allocationPercentage, body.conflictKey, body.startsAt, body.endsAt, actor_id),
            )
            experiment_id = int(cur.fetchone()[0])
            for variant in body.variants:
                cur.execute(
                    """INSERT INTO experiment_variants
                       (tenant_id,experiment_id,variant_key,name,config,weight,is_control)
                       VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                    (tenant_id, experiment_id, variant.key, variant.name, json.dumps(variant.config), variant.weight, variant.isControl),
                )
            record_audit(cur, tenant_id=tenant_id, actor_type="admin", actor_id=actor_id, action="experiment.created", resource_type="experiment", resource_id=str(experiment_id), after={"status": "NEEDS_APPROVAL", "name": body.name})
    return get_experiment(experiment_id, admin, _feature)


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: int, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("experiments.enabled"))):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {_SELECT} FROM experiments WHERE tenant_id = %s AND id = %s", (tenant_id, experiment_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Experiment not found")
            result = _experiment_dict(row)
            cur.execute("SELECT id, variant_key, name, config, weight, is_control FROM experiment_variants WHERE tenant_id = %s AND experiment_id = %s ORDER BY id", (tenant_id, experiment_id))
            result["variants"] = [{"id": v[0], "key": v[1], "name": v[2], "config": v[3], "weight": v[4], "isControl": v[5]} for v in cur.fetchall()]
            cur.execute("SELECT result, winning_variant_id, method, confidence_level, sample_size, metrics, guardrail_status, evaluated_at FROM experiment_results WHERE tenant_id = %s AND experiment_id = %s ORDER BY evaluated_at DESC LIMIT 1", (tenant_id, experiment_id))
            latest = cur.fetchone()
            result["latestResult"] = None if not latest else {"result": latest[0], "winningVariantId": latest[1], "method": latest[2], "confidenceLevel": float(latest[3]), "sampleSize": latest[4], "metrics": latest[5], "guardrails": latest[6], "evaluatedAt": latest[7].isoformat()}
    return result


def _transition(experiment_id: int, action: str, admin: dict) -> dict:
    transitions = {
        "approve": ({"NEEDS_APPROVAL", "DRAFT"}, "SCHEDULED"),
        "start": ({"SCHEDULED", "PAUSED"}, "RUNNING"),
        "pause": ({"RUNNING"}, "PAUSED"),
    }
    allowed, target = transitions[action]
    tenant_id, actor_id = int(admin["restaurant_id"]), str(admin["id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, conflict_key FROM experiments WHERE tenant_id = %s AND id = %s FOR UPDATE", (tenant_id, experiment_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Experiment not found")
            if row[0] not in allowed:
                raise HTTPException(status_code=409, detail=f"Experiment cannot {action} from {row[0]}")
            if action == "start":
                cur.execute("SELECT id FROM experiments WHERE tenant_id = %s AND conflict_key = %s AND id <> %s AND status = 'RUNNING' LIMIT 1", (tenant_id, row[1], experiment_id))
                conflict = cur.fetchone()
                if conflict:
                    raise HTTPException(status_code=409, detail=f"Conflicting experiment {conflict[0]} is already running")
            setters = "status = %s, updated_at = NOW()"
            params: list[Any] = [target]
            if action == "approve":
                setters += ", approved_by = %s, approved_at = NOW()"
                params.append(actor_id)
            if action == "start":
                setters += ", started_at = COALESCE(started_at,NOW())"
            params.extend([tenant_id, experiment_id])
            cur.execute(f"UPDATE experiments SET {setters} WHERE tenant_id = %s AND id = %s", params)
            record_audit(cur, tenant_id=tenant_id, actor_type="admin", actor_id=actor_id, action=f"experiment.{action}", resource_type="experiment", resource_id=str(experiment_id), before={"status": row[0]}, after={"status": target})
    return get_experiment(experiment_id, admin, None)


@router.post("/experiments/{experiment_id}/approve")
def approve_experiment(experiment_id: int, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("experiments.enabled"))): return _transition(experiment_id, "approve", admin)


@router.post("/experiments/{experiment_id}/start")
def start_experiment(experiment_id: int, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("experiments.enabled"))): return _transition(experiment_id, "start", admin)


@router.post("/experiments/{experiment_id}/pause")
def pause_experiment(experiment_id: int, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("experiments.enabled"))): return _transition(experiment_id, "pause", admin)


@router.post("/experiments/{experiment_id}/evaluate", status_code=202)
def queue_evaluation(experiment_id: int, admin: dict = Depends(get_current_admin), _feature=Depends(require_feature("experiments.enabled"))):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM experiments WHERE tenant_id = %s AND id = %s", (tenant_id, experiment_id))
            if not cur.fetchone(): raise HTTPException(status_code=404, detail="Experiment not found")
            job_id = enqueue_job(cur, tenant_id=tenant_id, job_name="experiments.evaluate", idempotency_key=f"experiment-evaluate:{experiment_id}:{datetime.utcnow().strftime('%Y%m%d%H')}", metadata={"experimentId": experiment_id})
    return {"jobId": job_id, "status": "queued" if job_id else "already_queued"}


@router.post("/experiments/{experiment_id}/assignment")
def get_assignment(body: AssignmentRequest, experiment_id: int, tenant: TenantContext = Depends(resolve_public_tenant)):
    if not has_feature(tenant.id, "experiments.enabled"):
        raise HTTPException(status_code=403, detail="Experiments are not enabled")
    consume_intervention_rate(tenant.id, "experiment_assignment", "EXPERIMENT_ASSIGNMENT_RATE_PER_MINUTE", 1000)
    with get_db() as conn:
        with conn.cursor() as cur:
            assignment = assign_variant(cur, tenant_id=tenant.id, experiment_id=experiment_id, visitor_id=body.visitorId, customer_id=body.customerId, audience=body.audience)
    return {"experimentId": experiment_id, "assigned": assignment is not None, "assignment": assignment}


@router.post("/experiment-assignments/active")
def get_active_assignment(body: ActiveAssignmentRequest, tenant: TenantContext = Depends(resolve_public_tenant)):
    if not has_feature(tenant.id, "experiments.enabled"):
        return {"assigned": False, "assignment": None}
    consume_intervention_rate(tenant.id, "experiment_assignment", "EXPERIMENT_ASSIGNMENT_RATE_PER_MINUTE", 1000)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, type, name FROM experiments
                   WHERE tenant_id = %s AND placement = %s AND status = 'RUNNING'
                     AND (starts_at IS NULL OR starts_at <= NOW())
                     AND (ends_at IS NULL OR ends_at > NOW())
                   ORDER BY started_at, id LIMIT 20""",
                (tenant.id, body.placement),
            )
            for experiment_id, experiment_type, name in cur.fetchall():
                assignment = assign_variant(cur, tenant_id=tenant.id, experiment_id=int(experiment_id), visitor_id=body.visitorId, customer_id=body.customerId, audience=body.audience)
                if assignment:
                    return {"assigned": True, "experimentId": int(experiment_id), "experimentType": experiment_type, "name": name, "assignment": assignment}
    return {"assigned": False, "assignment": None}


@router.post("/experiments/{experiment_id}/exposure", status_code=201)
def expose(body: ExposureRequest, experiment_id: int, tenant: TenantContext = Depends(resolve_public_tenant)):
    if not has_feature(tenant.id, "experiments.enabled"):
        raise HTTPException(status_code=403, detail="Experiments are not enabled")
    consume_intervention_rate(tenant.id, "experiment_exposure", "EXPERIMENT_EXPOSURE_RATE_PER_MINUTE", 2000)
    with get_db() as conn:
        with conn.cursor() as cur:
            inserted = record_exposure(cur, tenant_id=tenant.id, experiment_id=experiment_id, assignment_id=body.assignmentId, variant_id=body.variantId, visitor_id=body.visitorId, session_id=body.sessionId, exposure_key=body.exposureKey, context=body.context)
    return {"recorded": inserted}
