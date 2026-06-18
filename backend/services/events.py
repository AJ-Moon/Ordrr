import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

CLIENT_EVENT_NAMES = {
    "page_viewed", "menu_viewed", "category_impression", "category_viewed",
    "item_impression", "item_viewed", "modifier_group_viewed", "modifier_selected",
    "item_added_to_cart", "item_removed_from_cart", "cart_viewed", "cart_value_changed",
    "checkout_started", "checkout_step_viewed", "checkout_step_completed",
    "delivery_area_checked", "delivery_fee_shown", "minimum_order_blocked",
    "payment_method_selected", "payment_started", "payment_failed", "search_performed",
    "search_result_clicked", "promotion_impression", "promotion_clicked", "chat_opened",
    "chat_message_sent", "chat_recommendation_shown", "chat_recommendation_clicked",
    "order_architect_started", "order_architect_cart_created", "contact_identified",
    "consent_updated",
}

SERVER_EVENT_NAMES = {
    "cart_created", "cart_abandoned_candidate", "order_created", "order_completed",
    "order_cancelled", "order_refunded", "item_marked_unavailable", "item_marked_available",
    "message_queued", "message_sent", "message_delivered", "message_failed", "message_clicked",
    "mission_started", "mission_paused", "mission_completed", "experiment_exposure",
    "experiment_conversion",
}

ALL_EVENT_NAMES = CLIENT_EVENT_NAMES | SERVER_EVENT_NAMES


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def insert_event(
    cursor,
    *,
    event_id: str,
    tenant_id: int,
    visitor_id: str,
    session_id: str,
    event_name: str,
    occurred_at: datetime,
    customer_id: Optional[str] = None,
    location_id: Optional[int] = None,
    page_path: Optional[str] = None,
    referrer: Optional[str] = None,
    source: Optional[str] = None,
    medium: Optional[str] = None,
    campaign: Optional[str] = None,
    content: Optional[str] = None,
    term: Optional[str] = None,
    click_id: Optional[str] = None,
    item_id: Optional[int] = None,
    category_id: Optional[str] = None,
    cart_id: Optional[str] = None,
    order_id: Optional[str] = None,
    experiment_id: Optional[str] = None,
    variant_id: Optional[str] = None,
    mission_id: Optional[str] = None,
    properties: Optional[dict[str, Any]] = None,
    schema_version: int = 1,
    is_server_event: bool = False,
    consent_state: str = "unknown",
) -> bool:
    cursor.execute(
        """INSERT INTO analytics_events
           (event_id, tenant_id, location_id, visitor_id, session_id, customer_id,
            event_name, occurred_at, page_path, referrer, source, medium, campaign,
            content, term, click_id, item_id, category_id, cart_id, order_id,
            experiment_id, variant_id, mission_id, properties, schema_version,
            is_server_event, consent_state)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
           ON CONFLICT (tenant_id, event_id) DO NOTHING
           RETURNING id""",
        (
            event_id, tenant_id, location_id, visitor_id, session_id, customer_id,
            event_name, occurred_at, page_path, referrer, source, medium, campaign,
            content, term, click_id, item_id, category_id, cart_id, order_id,
            experiment_id, variant_id, mission_id, json.dumps(properties or {}),
            schema_version, is_server_event, consent_state,
        ),
    )
    return cursor.fetchone() is not None


def emit_server_event(
    cursor,
    *,
    tenant_id: int,
    event_name: str,
    visitor_id: Optional[str] = None,
    session_id: Optional[str] = None,
    event_id: Optional[str] = None,
    **kwargs: Any,
) -> bool:
    if event_name not in SERVER_EVENT_NAMES:
        raise ValueError(f"Unsupported server event: {event_name}")
    return insert_event(
        cursor,
        event_id=event_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        visitor_id=visitor_id or "server",
        session_id=session_id or "server",
        event_name=event_name,
        occurred_at=kwargs.pop("occurred_at", utc_now()),
        is_server_event=True,
        **kwargs,
    )
