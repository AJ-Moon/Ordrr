import os
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError, field_validator

from db import get_db
from dependencies.auth import TenantContext, resolve_public_tenant
from services.events import CLIENT_EVENT_NAMES, insert_event
from services.jobs import enqueue_job

router = APIRouter()


class EventInput(BaseModel):
    eventId: str = Field(min_length=8, max_length=100)
    eventName: str = Field(min_length=3, max_length=100)
    visitorId: str = Field(min_length=8, max_length=100)
    sessionId: str = Field(min_length=8, max_length=100)
    occurredAt: datetime
    locationId: Optional[int] = None
    pagePath: Optional[str] = Field(default=None, max_length=2000)
    referrer: Optional[str] = Field(default=None, max_length=2000)
    source: Optional[str] = Field(default=None, max_length=160)
    medium: Optional[str] = Field(default=None, max_length=160)
    campaign: Optional[str] = Field(default=None, max_length=240)
    content: Optional[str] = Field(default=None, max_length=240)
    term: Optional[str] = Field(default=None, max_length=240)
    clickId: Optional[str] = Field(default=None, max_length=240)
    itemId: Optional[int] = None
    categoryId: Optional[str] = Field(default=None, max_length=100)
    cartId: Optional[str] = Field(default=None, max_length=100)
    orderId: Optional[str] = Field(default=None, max_length=20)
    experimentId: Optional[str] = Field(default=None, max_length=100)
    variantId: Optional[str] = Field(default=None, max_length=100)
    missionId: Optional[str] = Field(default=None, max_length=100)
    properties: dict[str, Any] = Field(default_factory=dict)
    schemaVersion: int = Field(default=1, ge=1, le=10)
    consentState: Literal["unknown", "essential", "analytics_granted", "analytics_denied"] = "unknown"

    @field_validator("eventName")
    @classmethod
    def allowed_client_event(cls, value: str) -> str:
        if value not in CLIENT_EVENT_NAMES:
            raise ValueError("eventName is not an allowed client event")
        return value

    @field_validator("occurredAt")
    @classmethod
    def plausible_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if value > now + timedelta(minutes=10):
            raise ValueError("occurredAt is too far in the future")
        if value < now - timedelta(days=30):
            raise ValueError("occurredAt is older than the raw-event acceptance window")
        return value.astimezone(timezone.utc)


class EventBatchRequest(BaseModel):
    events: list[dict[str, Any]] = Field(min_length=1, max_length=100)


def _check_content_length(request: Request) -> None:
    max_bytes = int(os.getenv("EVENT_BATCH_MAX_BYTES", "262144"))
    raw_length = request.headers.get("content-length")
    if raw_length:
        try:
            if int(raw_length) > max_bytes:
                raise HTTPException(status_code=413, detail="Event batch payload is too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header")


def _consume_rate_window(cursor, tenant_id: int, event_count: int) -> int:
    cursor.execute(
        """INSERT INTO event_ingestion_windows (tenant_id, window_start, event_count)
           VALUES (%s, date_trunc('minute', NOW()), %s)
           ON CONFLICT (tenant_id, window_start)
           DO UPDATE SET event_count = event_ingestion_windows.event_count + EXCLUDED.event_count,
                         updated_at = NOW()
           RETURNING event_count""",
        (tenant_id, event_count),
    )
    return int(cursor.fetchone()[0])


def _validate_entity_ownership(cursor, tenant_id: int, event: EventInput) -> None:
    checks = [
        ("menu_items", "id", event.itemId, "itemId"),
        ("branches", "id", event.locationId, "locationId"),
        ("orders", "id", event.orderId, "orderId"),
    ]
    for table, column, entity_id, label in checks:
        if entity_id is None:
            continue
        cursor.execute(
            f"SELECT 1 FROM {table} WHERE {column} = %s AND restaurant_id = %s",
            (entity_id, tenant_id),
        )
        if not cursor.fetchone():
            raise ValueError(f"{label} does not belong to this restaurant")
    if event.experimentId is not None:
        try:
            experiment_id = int(event.experimentId)
        except ValueError:
            raise ValueError("experimentId must be an integer identifier")
        cursor.execute("SELECT 1 FROM experiments WHERE id = %s AND tenant_id = %s", (experiment_id, tenant_id))
        if not cursor.fetchone():
            raise ValueError("experimentId does not belong to this restaurant")
        if event.variantId is not None:
            try:
                variant_id = int(event.variantId)
            except ValueError:
                raise ValueError("variantId must be an integer identifier")
            cursor.execute(
                "SELECT 1 FROM experiment_variants WHERE id = %s AND experiment_id = %s AND tenant_id = %s",
                (variant_id, experiment_id, tenant_id),
            )
            if not cursor.fetchone():
                raise ValueError("variantId does not belong to this experiment")
    elif event.variantId is not None:
        raise ValueError("variantId requires experimentId")
    if event.missionId is not None:
        try:
            mission_id = int(event.missionId)
        except ValueError:
            raise ValueError("missionId must be an integer identifier")
        cursor.execute("SELECT 1 FROM missions WHERE id = %s AND tenant_id = %s", (mission_id, tenant_id))
        if not cursor.fetchone():
            raise ValueError("missionId does not belong to this restaurant")


@router.post("/events/batch")
def ingest_event_batch(
    body: EventBatchRequest,
    request: Request,
    tenant: TenantContext = Depends(resolve_public_tenant),
):
    _check_content_length(request)
    results: list[dict[str, Any]] = []
    accepted = duplicates = rejected = 0

    with get_db() as rate_conn:
        with rate_conn.cursor() as rate_cur:
            rate_count = _consume_rate_window(rate_cur, tenant.id, len(body.events))
    if rate_count > int(os.getenv("EVENT_RATE_LIMIT_PER_MINUTE", "3000")):
        raise HTTPException(status_code=429, detail="Event ingestion rate limit exceeded")

    with get_db() as conn:
        with conn.cursor() as cur:
            for index, raw_event in enumerate(body.events):
                cur.execute("SAVEPOINT event_item")
                try:
                    event = EventInput.model_validate(raw_event)
                    _validate_entity_ownership(cur, tenant.id, event)
                    inserted = insert_event(
                        cur,
                        event_id=event.eventId,
                        tenant_id=tenant.id,
                        visitor_id=event.visitorId,
                        session_id=event.sessionId,
                        event_name=event.eventName,
                        occurred_at=event.occurredAt,
                        location_id=event.locationId,
                        page_path=event.pagePath,
                        referrer=event.referrer,
                        source=event.source,
                        medium=event.medium,
                        campaign=event.campaign,
                        content=event.content,
                        term=event.term,
                        click_id=event.clickId,
                        item_id=event.itemId,
                        category_id=event.categoryId,
                        cart_id=event.cartId,
                        order_id=event.orderId,
                        experiment_id=event.experimentId,
                        variant_id=event.variantId,
                        mission_id=event.missionId,
                        properties=event.properties,
                        schema_version=event.schemaVersion,
                        consent_state=event.consentState,
                    )
                    if inserted:
                        accepted += 1
                        results.append({"index": index, "eventId": event.eventId, "status": "accepted"})
                    else:
                        duplicates += 1
                        results.append({"index": index, "eventId": event.eventId, "status": "duplicate"})
                    cur.execute("RELEASE SAVEPOINT event_item")
                except (ValidationError, ValueError) as exc:
                    cur.execute("ROLLBACK TO SAVEPOINT event_item")
                    rejected += 1
                    message = str(exc)
                    results.append({"index": index, "eventId": raw_event.get("eventId"), "status": "rejected", "error": message})
                except Exception as exc:
                    cur.execute("ROLLBACK TO SAVEPOINT event_item")
                    rejected += 1
                    results.append({
                        "index": index, "eventId": raw_event.get("eventId"),
                        "status": "rejected", "error": f"Database validation failed: {str(exc)[:300]}",
                    })

            if accepted:
                bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H")
                enqueue_job(
                    cur,
                    tenant_id=tenant.id,
                    job_name="analytics.aggregate_hourly",
                    idempotency_key=f"events:{tenant.id}:{bucket}",
                    metadata={"trigger": "event_ingestion"},
                )

    return {
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": rejected,
        "results": results,
    }
