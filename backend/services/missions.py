import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from services.communications import check_communication_eligibility
from services.events import emit_server_event
from services.messaging import persist_mock_message


MISSION_FEATURES = {
    "ABANDONED_CART_RECOVERY": "missions.abandoned_cart",
    "INTELLIGENT_BUNDLE": "missions.bundle",
    "LAPSED_CUSTOMER_WINBACK": "missions.lapsed_customer",
    "QUIET_HOUR_DEMAND": "missions.quiet_hour",
    "NEW_PRODUCT_DEMAND_TEST": "missions.product_demand_test",
}


def treatment_group(mission_id: int, subject_type: str, subject_id: str, holdout_percentage: int) -> str:
    raw = f"{mission_id}|{subject_type}|{subject_id}"
    bucket = int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16], 16) % 100
    return "holdout" if bucket < max(0, min(50, holdout_percentage)) else "treatment"


def assign_group(cursor, *, tenant_id: int, mission_id: int, subject_type: str, subject_id: str, holdout_percentage: int) -> str:
    cursor.execute(
        "SELECT group_name FROM mission_holdouts WHERE tenant_id = %s AND mission_id = %s AND subject_type = %s AND subject_id = %s",
        (tenant_id, mission_id, subject_type, subject_id),
    )
    row = cursor.fetchone()
    if row:
        return row[0]
    group = treatment_group(mission_id, subject_type, subject_id, holdout_percentage)
    cursor.execute(
        """INSERT INTO mission_holdouts (tenant_id,mission_id,subject_type,subject_id,group_name)
           VALUES (%s,%s,%s,%s,%s) ON CONFLICT (mission_id,subject_type,subject_id) DO NOTHING""",
        (tenant_id, mission_id, subject_type, subject_id, group),
    )
    return group


def refresh_customer_profiles(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    cursor.execute(
        """WITH spans AS (
               SELECT user_id,(max(completed_at)-min(completed_at)) / NULLIF(count(*)-1,0) AS average_interval
               FROM orders WHERE restaurant_id=%s AND status='delivered' AND user_id IS NOT NULL
               GROUP BY user_id HAVING count(*)>=2
           ) SELECT COALESCE(extract(epoch FROM avg(average_interval))/86400,30) FROM spans""",
        (tenant_id,),
    )
    segment_interval_days = max(1.0, float(cursor.fetchone()[0] or 30))
    cursor.execute(
        """SELECT c.id, c.user_id FROM customers c
           WHERE c.tenant_id = %s AND c.anonymized_at IS NULL""",
        (tenant_id,),
    )
    for customer_id, user_id in cursor.fetchall():
        if not user_id:
            continue
        cursor.execute(
            """SELECT count(*), COALESCE(sum(total_cents),0), COALESCE(sum(contribution_margin_cents),0),
                      COALESCE(avg(total_cents),0), min(completed_at), max(completed_at),
                      COALESCE(sum(discount_cents),0), COALESCE(sum(subtotal_cents),0)
               FROM orders WHERE restaurant_id = %s AND user_id = %s AND status = 'delivered'""",
            (tenant_id, user_id),
        )
        count, revenue, margin, average, first_at, last_at, discounts, subtotal = cursor.fetchone()
        count = int(count)
        interval_days = None
        if count >= 2 and first_at and last_at:
            interval_days = max(1.0, (last_at - first_at).total_seconds() / 86400 / (count - 1))
        expected = last_at + timedelta(days=interval_days or segment_interval_days) if last_at else None
        dependency = float(discounts or 0) / int(subtotal) if int(subtotal or 0) else 0.0
        cursor.execute(
            """SELECT oli.category_name,count(*) FROM order_line_items oli
               JOIN orders o ON o.id=oli.order_id AND o.restaurant_id=oli.tenant_id
               WHERE oli.tenant_id=%s AND o.user_id=%s AND o.status='delivered'
               GROUP BY oli.category_name ORDER BY count(*) DESC LIMIT 5""",
            (tenant_id, user_id),
        )
        preferred_categories = [row[0] for row in cursor.fetchall() if row[0]]
        cursor.execute(
            """SELECT branch_id,count(*) FROM orders WHERE restaurant_id=%s AND user_id=%s
               AND status='delivered' AND branch_id IS NOT NULL GROUP BY branch_id ORDER BY count(*) DESC LIMIT 1""",
            (tenant_id, user_id),
        )
        location_row = cursor.fetchone()
        preferred_location_id = location_row[0] if location_row else None
        cursor.execute(
            """SELECT extract(hour FROM completed_at)::int,count(*) FROM orders
               WHERE restaurant_id=%s AND user_id=%s AND status='delivered' AND completed_at IS NOT NULL
               GROUP BY 1 ORDER BY count(*) DESC LIMIT 1""",
            (tenant_id, user_id),
        )
        hour_row = cursor.fetchone()
        usual_hour = int(hour_row[0]) if hour_row else None
        usual_daypart = None if usual_hour is None else "LUNCH" if 11 <= usual_hour < 15 else "LATE_NIGHT" if usual_hour >= 21 or usual_hour < 5 else "OTHER"
        cursor.execute(
            """SELECT COALESCE(avg(line_count),0),COALESCE(avg(quantity),0) FROM (
                   SELECT oli.order_id,count(*) AS line_count,sum(oli.quantity) AS quantity
                   FROM order_line_items oli JOIN orders o ON o.id=oli.order_id AND o.restaurant_id=oli.tenant_id
                   WHERE oli.tenant_id=%s AND o.user_id=%s AND o.status='delivered' GROUP BY oli.order_id
               ) baskets""",
            (tenant_id, user_id),
        )
        average_lines, average_quantity = cursor.fetchone()
        cursor.execute("SELECT count(*) FROM carts WHERE tenant_id=%s AND customer_id=%s AND status='abandoned'", (tenant_id, customer_id))
        abandoned_count = int(cursor.fetchone()[0])
        cursor.execute(
            """INSERT INTO customer_metric_profiles
               (tenant_id,customer_id,order_count,lifetime_revenue_cents,lifetime_contribution_cents,
                average_order_value_cents,average_reorder_interval_days,expected_reorder_at,last_order_at,
                preferred_categories,preferred_location_id,discount_dependency,usual_daypart)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
               ON CONFLICT (tenant_id,customer_id) DO UPDATE SET
                 order_count=EXCLUDED.order_count,lifetime_revenue_cents=EXCLUDED.lifetime_revenue_cents,
                 lifetime_contribution_cents=EXCLUDED.lifetime_contribution_cents,
                 average_order_value_cents=EXCLUDED.average_order_value_cents,
                 average_reorder_interval_days=EXCLUDED.average_reorder_interval_days,
                 expected_reorder_at=EXCLUDED.expected_reorder_at,last_order_at=EXCLUDED.last_order_at,
                 preferred_categories=EXCLUDED.preferred_categories,preferred_location_id=EXCLUDED.preferred_location_id,
                 discount_dependency=EXCLUDED.discount_dependency,usual_daypart=EXCLUDED.usual_daypart,updated_at=NOW()""",
            (tenant_id, customer_id, count, int(revenue), int(margin), int(average), interval_days, expected, last_at,
             json.dumps(preferred_categories), preferred_location_id, dependency, usual_daypart),
        )
        cursor.execute("DELETE FROM customer_segment_memberships WHERE tenant_id = %s AND customer_id = %s", (tenant_id, customer_id))
        segments: list[tuple[str, dict[str, Any]]] = []
        if count == 1: segments.append(("FIRST_TIME_CUSTOMER", {"orderCount": count}))
        if count >= 2: segments.append(("RETURNING_CUSTOMER", {"orderCount": count}))
        if count >= 5: segments.append(("HIGH_FREQUENCY", {"orderCount": count}))
        if int(revenue) >= int(os.getenv("HIGH_VALUE_REVENUE_CENTS", "50000")): segments.append(("HIGH_VALUE", {"lifetimeRevenueCents": int(revenue)}))
        if dependency >= 0.15: segments.append(("DEAL_DEPENDENT", {"discountDependency": dependency}))
        if float(average_quantity or 0) >= 4 or float(average_lines or 0) >= 4: segments.append(("FAMILY_ORDER", {"averageQuantity": float(average_quantity or 0)}))
        if count and float(average_quantity or 0) <= 2: segments.append(("INDIVIDUAL_MEAL", {"averageQuantity": float(average_quantity or 0)}))
        if usual_daypart == "LUNCH": segments.append(("LUNCH", {"usualHour": usual_hour}))
        if usual_daypart == "LATE_NIGHT": segments.append(("LATE_NIGHT", {"usualHour": usual_hour}))
        if any("dessert" in category.lower() for category in preferred_categories): segments.append(("DESSERT_BUYER", {"preferredCategories": preferred_categories}))
        if abandoned_count >= 3: segments.append(("FREQUENT_ABANDONER", {"abandonedCarts": abandoned_count}))
        if expected and expected + timedelta(days=int(os.getenv("LAPSED_GRACE_DAYS", "14"))) < datetime.now(timezone.utc): segments.append(("LAPSED", {"expectedReorderAt": expected.isoformat()}))
        if count >= 8 and dependency < 0.15: segments.append(("LOYAL", {"orderCount": count}))
        for key, evidence in segments:
            cursor.execute(
                "INSERT INTO customer_segment_memberships (tenant_id,customer_id,segment_key,evidence) VALUES (%s,%s,%s,%s::jsonb)",
                (tenant_id, customer_id, key, json.dumps(evidence)),
            )


def _mission_rows(cursor, tenant_id: int, mission_type: str) -> list[tuple]:
    cursor.execute(
        """SELECT id, holdout_percentage, audience_definition, budget_limit_cents,
                  minimum_margin_cents, maximum_redemptions
           FROM missions WHERE tenant_id = %s AND type = %s AND status = 'RUNNING'
             AND (start_at IS NULL OR start_at <= NOW()) AND (end_at IS NULL OR end_at > NOW())""",
        (tenant_id, mission_type),
    )
    return cursor.fetchall()


def _next_action(cursor, tenant_id: int, mission_id: int, subject_type: str, subject_id: str) -> Optional[tuple]:
    cursor.execute(
        """SELECT ma.id, ma.channel, ma.config, ma.sequence_number
           FROM mission_actions ma
           WHERE ma.tenant_id = %s AND ma.mission_id = %s AND ma.status IN ('configured','active')
             AND NOT EXISTS (
                 SELECT 1 FROM campaign_messages cm WHERE cm.tenant_id = ma.tenant_id
                   AND cm.mission_id = ma.mission_id AND cm.action_id = ma.id
                   AND cm.subject_type = %s AND cm.subject_id = %s
             )
             AND NOT EXISTS (
                 SELECT 1 FROM mission_actions prior
                 WHERE prior.tenant_id = ma.tenant_id AND prior.mission_id = ma.mission_id
                   AND prior.sequence_number < ma.sequence_number
                   AND NOT EXISTS (
                       SELECT 1 FROM campaign_messages pcm WHERE pcm.tenant_id = prior.tenant_id
                         AND pcm.mission_id = prior.mission_id AND pcm.action_id = prior.id
                         AND pcm.subject_type = %s AND pcm.subject_id = %s
                         AND pcm.status IN ('SENT','DELIVERED','CLICKED')
                   )
             )
           ORDER BY ma.sequence_number LIMIT 1""",
        (tenant_id, mission_id, subject_type, subject_id, subject_type, subject_id),
    )
    row = cursor.fetchone()
    if not row:
        return None
    delay_hours = max(0, int((row[2] or {}).get("delayHours", 0)))
    if int(row[3]) > 1 and delay_hours:
        cursor.execute(
            """SELECT max(cm.created_at) FROM campaign_messages cm
               JOIN mission_actions ma ON ma.id = cm.action_id AND ma.tenant_id = cm.tenant_id
               WHERE cm.tenant_id = %s AND cm.mission_id = %s AND cm.subject_type = %s
                 AND cm.subject_id = %s AND ma.sequence_number < %s""",
            (tenant_id, mission_id, subject_type, subject_id, row[3]),
        )
        previous_at = cursor.fetchone()[0]
        if previous_at and previous_at + timedelta(hours=delay_hours) > datetime.now(timezone.utc):
            return None
    return row


def _mission_send_capacity(cursor, tenant_id: int, mission_id: int, maximum_redemptions: Optional[int]) -> bool:
    if not maximum_redemptions:
        return True
    cursor.execute(
        "SELECT count(*) FROM campaign_messages WHERE tenant_id = %s AND mission_id = %s AND status IN ('SENT','DELIVERED','CLICKED')",
        (tenant_id, mission_id),
    )
    return int(cursor.fetchone()[0]) < int(maximum_redemptions)


def quiet_hour_candidate_status(
    *,
    observed_orders: float,
    normal_capacity_orders: int,
    target_utilization: float,
    cancellation_rate: float,
    eligible_item_count: int,
    max_cancellation_rate: float = 0.15,
) -> tuple[str, str]:
    actual_utilization = observed_orders / normal_capacity_orders if normal_capacity_orders else 1
    if eligible_item_count <= 0:
        return "BLOCKED", "no_margin_qualified_inventory"
    if cancellation_rate > max_cancellation_rate:
        return "BLOCKED", "cancellation_rate_too_high"
    if actual_utilization >= target_utilization:
        return "BLOCKED", "capacity_already_utilized"
    return "CANDIDATE", "quiet_capacity_available"


def _eligible_margin_items(cursor, tenant_id: int, minimum_margin_cents: Optional[int]) -> list[dict[str, Any]]:
    cursor.execute(
        """SELECT mi.id, mi.name, COALESCE(mi.sale_price_cents, mi.price_cents) AS price_cents,
                  COALESCE(mi.ingredient_cost_cents, 0) + COALESCE(mi.packaging_cost_cents, 0) AS cost_cents,
                  mi.image
           FROM menu_items mi
           LEFT JOIN inventory_guardrails ig ON ig.tenant_id = mi.restaurant_id AND ig.item_id = mi.id
           WHERE mi.restaurant_id = %s
             AND mi.is_available = true
             AND COALESCE(mi.sale_price_cents, mi.price_cents) >= (
                 COALESCE(mi.ingredient_cost_cents, 0) + COALESCE(mi.packaging_cost_cents, 0) + %s
             )
             AND COALESCE(ig.constrained, false) = false
             AND (ig.available_quantity IS NULL OR ig.available_quantity > ig.low_stock_threshold)
           ORDER BY (COALESCE(mi.sale_price_cents, mi.price_cents) - COALESCE(mi.ingredient_cost_cents, 0) - COALESCE(mi.packaging_cost_cents, 0)) DESC
           LIMIT 20""",
        (tenant_id, int(minimum_margin_cents or 0)),
    )
    return [
        {
            "id": int(row[0]),
            "name": row[1],
            "priceCents": int(row[2]),
            "costCents": int(row[3]),
            "image": row[4],
        }
        for row in cursor.fetchall()
    ]


def refresh_quiet_hour_candidates(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    max_cancellation_rate = float(metadata.get("maxCancellationRate") or os.getenv("QUIET_HOUR_MAX_CANCELLATION_RATE", "0.15"))
    cursor.execute(
        """SELECT id, location_id, weekday, time_start, time_end, normal_capacity_orders,
                  maximum_capacity_orders, target_utilization
           FROM capacity_settings
           WHERE tenant_id = %s AND enabled = true""",
        (tenant_id,),
    )
    for setting_id, location_id, weekday, time_start, time_end, normal_capacity, maximum_capacity, target_utilization in cursor.fetchall():
        cursor.execute(
            """WITH days AS (
                   SELECT generate_series(CURRENT_DATE - INTERVAL '56 days', CURRENT_DATE - INTERVAL '1 day', INTERVAL '1 day')::date AS day
               ), scoped_days AS (
                   SELECT day FROM days WHERE EXTRACT(DOW FROM day)::int = %s
               ), scoped_orders AS (
                   SELECT o.id, o.status
                   FROM scoped_days d
                   LEFT JOIN orders o ON o.restaurant_id = %s
                    AND o.branch_id = %s
                    AND o.created_at::date = d.day
                    AND o.created_at::time >= %s::time
                    AND o.created_at::time < %s::time
               )
               SELECT COALESCE(count(id)::numeric / NULLIF((SELECT count(*) FROM scoped_days), 0), 0),
                      COALESCE(count(id) FILTER (WHERE lower(status) IN ('cancelled','canceled'))::numeric / NULLIF(count(id), 0), 0)
               FROM scoped_orders""",
            (int(weekday), tenant_id, location_id, time_start, time_end),
        )
        observed_orders, cancellation_rate = cursor.fetchone()
        eligible_items = _eligible_margin_items(cursor, tenant_id, int(metadata.get("minimumMarginCents") or 0))
        status, reason = quiet_hour_candidate_status(
            observed_orders=float(observed_orders or 0),
            normal_capacity_orders=int(normal_capacity),
            target_utilization=float(target_utilization),
            cancellation_rate=float(cancellation_rate or 0),
            eligible_item_count=len(eligible_items),
            max_cancellation_rate=max_cancellation_rate,
        )
        utilization = float(observed_orders or 0) / int(normal_capacity)
        evidence = {
            "reason": reason,
            "eligibleItemIds": [item["id"] for item in eligible_items[:10]],
            "historyWindowDays": 56,
            "maxCancellationRate": max_cancellation_rate,
        }
        cursor.execute(
            """INSERT INTO quiet_hour_candidates
               (tenant_id,capacity_setting_id,location_id,weekday,time_start,time_end,observed_orders,
                normal_capacity_orders,maximum_capacity_orders,target_utilization,actual_utilization,
                cancellation_rate,available_margin_items,status,evidence)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
               ON CONFLICT (tenant_id, capacity_setting_id) DO UPDATE SET
                 location_id=EXCLUDED.location_id, weekday=EXCLUDED.weekday,
                 time_start=EXCLUDED.time_start, time_end=EXCLUDED.time_end,
                 observed_orders=EXCLUDED.observed_orders,
                 normal_capacity_orders=EXCLUDED.normal_capacity_orders,
                 maximum_capacity_orders=EXCLUDED.maximum_capacity_orders,
                 target_utilization=EXCLUDED.target_utilization,
                 actual_utilization=EXCLUDED.actual_utilization,
                 cancellation_rate=EXCLUDED.cancellation_rate,
                 available_margin_items=EXCLUDED.available_margin_items,
                 status=EXCLUDED.status,evidence=EXCLUDED.evidence,calculated_at=NOW()""",
            (
                tenant_id,
                setting_id,
                location_id,
                weekday,
                time_start,
                time_end,
                float(observed_orders or 0),
                normal_capacity,
                maximum_capacity,
                target_utilization,
                utilization,
                float(cancellation_rate or 0),
                len(eligible_items),
                status,
                json.dumps(evidence),
            ),
        )


def _breach_guardrail(cursor, tenant_id: int, mission_id: int, key: str, value: dict[str, Any]) -> None:
    cursor.execute(
        """INSERT INTO mission_guardrails
           (tenant_id,mission_id,guardrail_key,threshold_json,status,last_value,checked_at)
           VALUES (%s,%s,%s,%s::jsonb,'breached',%s::jsonb,NOW())
           ON CONFLICT (mission_id, guardrail_key) DO UPDATE SET
             status='breached', last_value=EXCLUDED.last_value, checked_at=NOW()""",
        (tenant_id, mission_id, key, json.dumps(value), json.dumps(value)),
    )
    cursor.execute(
        "UPDATE missions SET status='PAUSED', updated_at=NOW() WHERE tenant_id=%s AND id=%s AND status='RUNNING'",
        (tenant_id, mission_id),
    )


def evaluate_quiet_hours(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    refresh_quiet_hour_candidates(cursor, tenant_id, metadata)
    cursor.execute(
        """SELECT m.id,m.holdout_percentage,m.audience_definition,m.minimum_margin_cents,m.maximum_redemptions,m.capacity_limit,
                  q.capacity_setting_id,q.location_id,q.time_start,q.time_end,q.maximum_capacity_orders
           FROM missions m
           JOIN quiet_hour_candidates q ON q.tenant_id = m.tenant_id
            AND q.status = 'CANDIDATE'
            AND (m.audience_definition->>'capacitySettingId' IS NULL OR (m.audience_definition->>'capacitySettingId')::bigint = q.capacity_setting_id)
           WHERE m.tenant_id = %s AND m.type = 'QUIET_HOUR_DEMAND' AND m.status = 'RUNNING'
             AND (m.start_at IS NULL OR m.start_at <= NOW()) AND (m.end_at IS NULL OR m.end_at > NOW())
             AND q.weekday = EXTRACT(DOW FROM NOW())::int
             AND NOW()::time >= q.time_start AND NOW()::time < q.time_end
           ORDER BY m.started_at, m.id""",
        (tenant_id,),
    )
    for mission_id, holdout, audience, minimum_margin, maximum_redemptions, capacity_limit, setting_id, location_id, time_start, time_end, maximum_capacity in cursor.fetchall():
        effective_capacity = min(int(capacity_limit or maximum_capacity), int(maximum_capacity))
        cursor.execute(
            """SELECT count(*) FROM orders
               WHERE restaurant_id=%s AND branch_id=%s AND created_at::date=CURRENT_DATE
                 AND created_at::time >= %s::time AND created_at::time < %s::time
                 AND lower(status) NOT IN ('cancelled','canceled','failed')""",
            (tenant_id, location_id, time_start, time_end),
        )
        current_orders = int(cursor.fetchone()[0])
        if current_orders >= effective_capacity:
            _breach_guardrail(
                cursor,
                tenant_id,
                int(mission_id),
                "capacity_reached",
                {"capacitySettingId": int(setting_id), "currentOrders": current_orders, "capacity": effective_capacity},
            )
            continue
        eligible_items = _eligible_margin_items(cursor, tenant_id, minimum_margin)
        if not eligible_items:
            _breach_guardrail(cursor, tenant_id, int(mission_id), "stock_low", {"capacitySettingId": int(setting_id)})
            continue
        target_segment = (audience or {}).get("targetSegment")
        if target_segment:
            cursor.execute(
                """SELECT c.id,c.email,c.phone
                   FROM customer_segment_memberships sm
                   JOIN customers c ON c.tenant_id = sm.tenant_id AND c.id = sm.customer_id
                   WHERE sm.tenant_id=%s AND sm.segment_key=%s AND c.anonymized_at IS NULL
                   LIMIT 500""",
                (tenant_id, target_segment),
            )
        else:
            cursor.execute(
                """SELECT c.id,c.email,c.phone
                   FROM customers c
                   WHERE c.tenant_id=%s AND c.anonymized_at IS NULL
                   ORDER BY c.updated_at DESC NULLS LAST
                   LIMIT 500""",
                (tenant_id,),
            )
        for customer_id, email, phone in cursor.fetchall():
            if not _mission_send_capacity(cursor, tenant_id, int(mission_id), maximum_redemptions):
                break
            action = _next_action(cursor, tenant_id, int(mission_id), "customer", customer_id)
            if not action:
                continue
            channel = action[1]
            destination = email if channel == "email" else phone
            eligible = True
            reason = "eligible"
            if channel:
                eligibility = check_communication_eligibility(cursor, tenant_id=tenant_id, customer_id=customer_id, channel=channel)
                eligible = bool(destination) and eligibility.allowed
                reason = "eligible" if eligible else ("missing_contact" if not destination else eligibility.reason)
            snapshot = {
                "capacitySettingId": int(setting_id),
                "locationId": int(location_id),
                "currentOrders": current_orders,
                "capacity": effective_capacity,
                "targetSegment": target_segment,
                "eligibleItems": eligible_items[:5],
                "reason": reason,
            }
            cursor.execute(
                """INSERT INTO mission_audiences
                   (tenant_id,mission_id,subject_type,subject_id,customer_id,eligibility_snapshot,eligible,reason)
                   VALUES (%s,%s,'customer',%s,%s,%s::jsonb,%s,%s)
                   ON CONFLICT (mission_id,subject_type,subject_id) DO UPDATE SET
                     eligibility_snapshot=EXCLUDED.eligibility_snapshot,eligible=EXCLUDED.eligible,
                     reason=EXCLUDED.reason,evaluated_at=NOW()""",
                (tenant_id, mission_id, customer_id, customer_id, json.dumps(snapshot), eligible, reason),
            )
            if not eligible:
                continue
            group = assign_group(cursor, tenant_id=tenant_id, mission_id=int(mission_id), subject_type="customer", subject_id=customer_id, holdout_percentage=int(holdout))
            if group == "treatment":
                if channel:
                    persist_mock_message(
                        cursor,
                        tenant_id=tenant_id,
                        mission_id=int(mission_id),
                        action_id=int(action[0]),
                        customer_id=customer_id,
                        subject_type="customer",
                        subject_id=customer_id,
                        channel=channel,
                        destination=destination,
                        content={"template": "quiet_hour_offer", "items": eligible_items[:5], **(action[2] or {})},
                    )
                cursor.execute(
                    """INSERT INTO mission_events
                       (tenant_id,mission_id,event_key,event_type,subject_type,subject_id,customer_id,properties)
                       VALUES (%s,%s,%s,'quiet_hour_offer_ready','customer',%s,%s,%s::jsonb)
                       ON CONFLICT DO NOTHING""",
                    (tenant_id, mission_id, f"quiet-hour:{mission_id}:{customer_id}", customer_id, customer_id, json.dumps(snapshot)),
                )
    refresh_mission_results(cursor, tenant_id, "QUIET_HOUR_DEMAND")


def evaluate_product_demand_tests(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    refresh_mission_results(cursor, tenant_id, "NEW_PRODUCT_DEMAND_TEST")


def evaluate_abandoned_carts(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    inactive_minutes = max(10, int(os.getenv("ABANDONED_CART_MINUTES", "30")))
    for mission_id, holdout, audience, budget, minimum_margin, maximum_redemptions in _mission_rows(cursor, tenant_id, "ABANDONED_CART_RECOVERY"):
        minimum_value = int((audience or {}).get("minimumCartValueCents", 0))
        cursor.execute(
            """SELECT c.id,c.customer_id,c.subtotal_cents,cu.email,cu.phone,c.visitor_id,c.session_id
               FROM carts c JOIN customers cu ON cu.id = c.customer_id AND cu.tenant_id = c.tenant_id
               WHERE c.tenant_id = %s AND c.status = 'active' AND c.customer_id IS NOT NULL
                 AND c.updated_at <= NOW() - (%s * INTERVAL '1 minute') AND c.subtotal_cents >= %s
                 AND EXISTS (SELECT 1 FROM cart_lines cl WHERE cl.tenant_id = c.tenant_id AND cl.cart_id = c.id)
                 AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.restaurant_id = c.tenant_id AND o.cart_id = c.id AND o.status = 'delivered')
               ORDER BY c.updated_at LIMIT 500""",
            (tenant_id, inactive_minutes, minimum_value),
        )
        for cart_id, customer_id, subtotal, email, phone, visitor_id, session_id in cursor.fetchall():
            if not _mission_send_capacity(cursor, tenant_id, mission_id, maximum_redemptions):
                break
            action = _next_action(cursor, tenant_id, mission_id, "cart", cart_id)
            if not action:
                continue
            channel = action[1] or "email"
            destination = email if channel == "email" else phone
            eligibility = check_communication_eligibility(cursor, tenant_id=tenant_id, customer_id=customer_id, channel=channel)
            eligible = bool(destination) and eligibility.allowed
            reason = "eligible" if eligible else ("missing_contact" if not destination else eligibility.reason)
            snapshot = {"cartId": cart_id, "subtotalCents": int(subtotal), "channel": channel, "reason": reason}
            cursor.execute(
                """INSERT INTO mission_audiences
                   (tenant_id,mission_id,subject_type,subject_id,customer_id,eligibility_snapshot,eligible,reason)
                   VALUES (%s,%s,'cart',%s,%s,%s::jsonb,%s,%s)
                   ON CONFLICT (mission_id,subject_type,subject_id) DO UPDATE SET
                     eligibility_snapshot=EXCLUDED.eligibility_snapshot,eligible=EXCLUDED.eligible,
                     reason=EXCLUDED.reason,evaluated_at=NOW()""",
                (tenant_id, mission_id, cart_id, customer_id, json.dumps(snapshot), eligible, reason),
            )
            if not eligible:
                continue
            group = assign_group(cursor, tenant_id=tenant_id, mission_id=mission_id, subject_type="cart", subject_id=cart_id, holdout_percentage=int(holdout))
            if group == "treatment":
                content = {"template": "abandoned_cart_reminder", "cartId": cart_id, "subtotalCents": int(subtotal), **(action[2] or {})}
                sent = persist_mock_message(cursor, tenant_id=tenant_id, mission_id=mission_id, action_id=int(action[0]), customer_id=customer_id, subject_type="cart", subject_id=cart_id, channel=channel, destination=destination, content=content)
                if sent:
                    cursor.execute("UPDATE carts SET status = 'abandoned', updated_at = NOW() WHERE tenant_id = %s AND id = %s AND status = 'active'", (tenant_id, cart_id))
                    cursor.execute("INSERT INTO mission_events (tenant_id,mission_id,event_key,event_type,subject_type,subject_id,customer_id,cart_id,properties) VALUES (%s,%s,%s,'message_sent','cart',%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING", (tenant_id, mission_id, f"abandoned-message:{mission_id}:{cart_id}", cart_id, customer_id, cart_id, json.dumps({"channel": channel})))
    refresh_mission_results(cursor, tenant_id, "ABANDONED_CART_RECOVERY")


def evaluate_lapsed_customers(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    refresh_customer_profiles(cursor, tenant_id, metadata)
    grace_days = max(1, int(os.getenv("LAPSED_GRACE_DAYS", "14")))
    for mission_id, holdout, audience, budget, minimum_margin, maximum_redemptions in _mission_rows(cursor, tenant_id, "LAPSED_CUSTOMER_WINBACK"):
        minimum_orders = max(1, int((audience or {}).get("minimumOrderCount", 2)))
        cursor.execute(
            """SELECT p.customer_id,c.email,c.phone,p.order_count,p.expected_reorder_at,p.average_order_value_cents,
                      p.preferred_categories,p.preferred_location_id,p.discount_dependency,p.usual_daypart,c.user_id
               FROM customer_metric_profiles p JOIN customers c ON c.id = p.customer_id AND c.tenant_id = p.tenant_id
               WHERE p.tenant_id = %s AND p.order_count >= %s
                 AND p.expected_reorder_at < NOW() - (%s * INTERVAL '1 day')
                 AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.restaurant_id = p.tenant_id AND o.user_id = c.user_id AND o.status = 'delivered' AND o.completed_at >= p.expected_reorder_at)
               LIMIT 500""",
            (tenant_id, minimum_orders, grace_days),
        )
        for customer_id, email, phone, order_count, expected_at, average_value, categories, location_id, discount_dependency, daypart, user_id in cursor.fetchall():
            if not _mission_send_capacity(cursor, tenant_id, mission_id, maximum_redemptions):
                break
            action = _next_action(cursor, tenant_id, mission_id, "customer", customer_id)
            if not action:
                continue
            channel = action[1] or "email"
            destination = email if channel == "email" else phone
            eligibility = check_communication_eligibility(cursor, tenant_id=tenant_id, customer_id=customer_id, channel=channel)
            eligible = bool(destination) and eligibility.allowed
            reason = "eligible" if eligible else ("missing_contact" if not destination else eligibility.reason)
            cursor.execute(
                """SELECT oli.item_name,count(*) FROM order_line_items oli JOIN orders o ON o.id=oli.order_id AND o.restaurant_id=oli.tenant_id
                   WHERE oli.tenant_id=%s AND o.user_id=%s AND o.status='delivered' GROUP BY oli.item_name ORDER BY count(*) DESC LIMIT 1""",
                (tenant_id, user_id),
            )
            favorite_row = cursor.fetchone()
            favorite_item = favorite_row[0] if favorite_row else None
            snapshot = {"orderCount": int(order_count), "expectedReorderAt": expected_at.isoformat(), "averageOrderValueCents": int(average_value), "preferredCategories": categories or [], "preferredLocationId": location_id, "discountDependency": float(discount_dependency or 0), "usualDaypart": daypart, "favoriteItem": favorite_item, "reason": reason}
            cursor.execute(
                """INSERT INTO mission_audiences
                   (tenant_id,mission_id,subject_type,subject_id,customer_id,eligibility_snapshot,eligible,reason)
                   VALUES (%s,%s,'customer',%s,%s,%s::jsonb,%s,%s)
                   ON CONFLICT (mission_id,subject_type,subject_id) DO UPDATE SET eligibility_snapshot=EXCLUDED.eligibility_snapshot,eligible=EXCLUDED.eligible,reason=EXCLUDED.reason,evaluated_at=NOW()""",
                (tenant_id, mission_id, customer_id, customer_id, json.dumps(snapshot), eligible, reason),
            )
            if not eligible:
                continue
            group = assign_group(cursor, tenant_id=tenant_id, mission_id=mission_id, subject_type="customer", subject_id=customer_id, holdout_percentage=int(holdout))
            if group == "treatment":
                persist_mock_message(cursor, tenant_id=tenant_id, mission_id=mission_id, action_id=int(action[0]), customer_id=customer_id, subject_type="customer", subject_id=customer_id, channel=channel, destination=destination, content={"template": "lapsed_customer_reorder", "averageOrderValueCents": int(average_value), "favoriteItem": favorite_item, "preferredCategories": categories or [], "preferredLocationId": location_id, "usualDaypart": daypart, "discountDependency": float(discount_dependency or 0), **(action[2] or {})})
    refresh_mission_results(cursor, tenant_id, "LAPSED_CUSTOMER_WINBACK")


def evaluate_bundles(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    refresh_mission_results(cursor, tenant_id, "INTELLIGENT_BUNDLE")


def refresh_mission_results(cursor, tenant_id: int, mission_type: Optional[str] = None) -> None:
    params: list[Any] = [tenant_id]
    condition = "tenant_id = %s AND status IN ('RUNNING','PAUSED','COMPLETED')"
    if mission_type:
        condition += " AND type = %s"
        params.append(mission_type)
    cursor.execute(f"SELECT id,type FROM missions WHERE {condition}", params)
    for mission_id, kind in cursor.fetchall():
        cursor.execute("SELECT group_name,count(*) FROM mission_holdouts WHERE tenant_id = %s AND mission_id = %s GROUP BY group_name", (tenant_id, mission_id))
        sizes = {row[0]: int(row[1]) for row in cursor.fetchall()}
        if kind == "NEW_PRODUCT_DEMAND_TEST":
            cursor.execute(
                """SELECT h.group_name,
                          count(DISTINCT e.visitor_id) FILTER (WHERE e.event_type IN ('INTEREST','WAITLIST','PREORDER')),
                          count(*) FILTER (WHERE e.event_type = 'WAITLIST'),
                          count(*) FILTER (WHERE e.event_type = 'PREORDER'),
                          COALESCE(avg(e.preferred_price_cents) FILTER (WHERE e.preferred_price_cents IS NOT NULL), 0)
                   FROM mission_holdouts h
                   LEFT JOIN product_interest_events e ON e.tenant_id = h.tenant_id
                    AND e.mission_id = h.mission_id AND e.visitor_id = h.subject_id
                    AND e.occurred_at >= h.assigned_at
                   WHERE h.tenant_id = %s AND h.mission_id = %s
                   GROUP BY h.group_name""",
                (tenant_id, mission_id),
            )
            outcomes = {
                row[0]: {
                    "qualified": int(row[1] or 0),
                    "waitlist": int(row[2] or 0),
                    "preorder": int(row[3] or 0),
                    "preferredPrice": int(row[4] or 0),
                }
                for row in cursor.fetchall()
            }
            cursor.execute(
                """SELECT COALESCE(sum((po.price_cents - pc.estimated_cost_cents) * po.quantity), 0),
                          COALESCE(sum(po.price_cents * po.quantity), 0),
                          count(DISTINCT po.id)
                   FROM product_preorders po
                   JOIN product_concepts pc ON pc.tenant_id = po.tenant_id AND pc.id = po.concept_id
                   WHERE po.tenant_id=%s AND pc.mission_id=%s AND po.status='RESERVED'""",
                (tenant_id, mission_id),
            )
            contribution, revenue, reserved = cursor.fetchone()
            treatment_size, holdout_size = sizes.get("treatment", 0), sizes.get("holdout", 0)
            treatment_conversions = outcomes.get("treatment", {}).get("qualified", 0)
            holdout_conversions = outcomes.get("holdout", {}).get("qualified", 0)
            treatment_rate = treatment_conversions / treatment_size if treatment_size else 0
            holdout_rate = holdout_conversions / holdout_size if holdout_size else 0
            incremental_orders = (treatment_rate - holdout_rate) * treatment_size
            metrics = {
                "qualifiedInterest": treatment_conversions,
                "waitlistConversion": outcomes.get("treatment", {}).get("waitlist", 0),
                "preorderConversion": outcomes.get("treatment", {}).get("preorder", 0),
                "preferredPriceCents": outcomes.get("treatment", {}).get("preferredPrice", 0),
                "reservedPreorders": int(reserved or 0),
                "estimatedContributionCents": int(contribution or 0),
                "treatmentRate": treatment_rate,
                "holdoutRate": holdout_rate,
            }
            cursor.execute(
                """INSERT INTO mission_results
                   (tenant_id,mission_id,treatment_size,holdout_size,treatment_conversions,holdout_conversions,
                    incremental_orders,revenue_cents,incremental_revenue_cents,contribution_margin_cents,
                    discount_cost_cents,message_cost_cents,metrics)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,%s,0,0,%s::jsonb)""",
                (
                    tenant_id,
                    mission_id,
                    treatment_size,
                    holdout_size,
                    treatment_conversions,
                    holdout_conversions,
                    incremental_orders,
                    int(revenue or 0),
                    int(contribution or 0),
                    json.dumps(metrics),
                ),
            )
            continue
        if kind == "ABANDONED_CART_RECOVERY":
            cursor.execute(
                """SELECT h.group_name,count(DISTINCT o.id),COALESCE(sum(o.total_cents),0),COALESCE(sum(o.contribution_margin_cents),0),COALESCE(sum(o.discount_cents),0)
                   FROM mission_holdouts h LEFT JOIN orders o ON o.restaurant_id = h.tenant_id AND o.cart_id = h.subject_id AND o.status = 'delivered'
                   WHERE h.tenant_id = %s AND h.mission_id = %s GROUP BY h.group_name""",
                (tenant_id, mission_id),
            )
        elif kind == "INTELLIGENT_BUNDLE":
            cursor.execute(
                """SELECT h.group_name,count(DISTINCT o.id),COALESCE(sum(o.total_cents),0),COALESCE(sum(o.contribution_margin_cents),0),COALESCE(sum(o.discount_cents),0)
                   FROM mission_holdouts h
                   LEFT JOIN orders o ON o.restaurant_id = h.tenant_id AND o.visitor_id = h.subject_id
                     AND o.status = 'delivered' AND o.completed_at >= h.assigned_at
                   WHERE h.tenant_id = %s AND h.mission_id = %s GROUP BY h.group_name""",
                (tenant_id, mission_id),
            )
        elif kind == "QUIET_HOUR_DEMAND":
            cursor.execute(
                """SELECT h.group_name,count(DISTINCT o.id),COALESCE(sum(o.total_cents),0),COALESCE(sum(o.contribution_margin_cents),0),COALESCE(sum(o.discount_cents),0)
                   FROM mission_holdouts h
                   LEFT JOIN customers c ON h.subject_type = 'customer' AND c.id = h.subject_id AND c.tenant_id = h.tenant_id
                   LEFT JOIN orders o ON o.restaurant_id = h.tenant_id
                    AND o.status = 'delivered'
                    AND o.completed_at >= h.assigned_at
                    AND ((h.subject_type = 'visitor' AND o.visitor_id = h.subject_id)
                      OR (h.subject_type = 'customer' AND o.user_id = c.user_id))
                   WHERE h.tenant_id = %s AND h.mission_id = %s GROUP BY h.group_name""",
                (tenant_id, mission_id),
            )
        else:
            cursor.execute(
                """SELECT h.group_name,count(DISTINCT o.id),COALESCE(sum(o.total_cents),0),COALESCE(sum(o.contribution_margin_cents),0),COALESCE(sum(o.discount_cents),0)
                   FROM mission_holdouts h
                   LEFT JOIN customers c ON h.subject_type = 'customer' AND c.id = h.subject_id AND c.tenant_id = h.tenant_id
                   LEFT JOIN orders o ON o.restaurant_id = h.tenant_id AND o.user_id = c.user_id AND o.status = 'delivered' AND o.completed_at >= h.assigned_at
                   WHERE h.tenant_id = %s AND h.mission_id = %s GROUP BY h.group_name""",
                (tenant_id, mission_id),
            )
        outcomes = {row[0]: {"orders": int(row[1]), "revenue": int(row[2]), "margin": int(row[3]), "discount": int(row[4])} for row in cursor.fetchall()}
        treatment_size, holdout_size = sizes.get("treatment", 0), sizes.get("holdout", 0)
        treatment_orders = outcomes.get("treatment", {}).get("orders", 0)
        holdout_orders = outcomes.get("holdout", {}).get("orders", 0)
        treatment_rate = treatment_orders / treatment_size if treatment_size else 0
        holdout_rate = holdout_orders / holdout_size if holdout_size else 0
        incremental_orders = (treatment_rate - holdout_rate) * treatment_size
        revenue = outcomes.get("treatment", {}).get("revenue", 0)
        average_revenue = revenue / treatment_orders if treatment_orders else 0
        cursor.execute("SELECT count(*) FROM campaign_messages WHERE tenant_id = %s AND mission_id = %s AND status IN ('SENT','DELIVERED','CLICKED')", (tenant_id, mission_id))
        sent = int(cursor.fetchone()[0])
        extra_metrics: dict[str, Any] = {}
        if kind == "QUIET_HOUR_DEMAND":
            cursor.execute(
                """SELECT count(*) FILTER (WHERE status = 'breached'),
                          COALESCE(max((last_value->>'currentOrders')::numeric / NULLIF((last_value->>'capacity')::numeric, 0)), 0)
                   FROM mission_guardrails
                   WHERE tenant_id = %s AND mission_id = %s""",
                (tenant_id, mission_id),
            )
            violations, utilization = cursor.fetchone()
            extra_metrics = {
                "operationalViolations": int(violations or 0),
                "capacityUtilization": float(utilization or 0),
            }
        cursor.execute(
            """INSERT INTO mission_results
               (tenant_id,mission_id,treatment_size,holdout_size,treatment_conversions,holdout_conversions,
                incremental_orders,revenue_cents,incremental_revenue_cents,contribution_margin_cents,
                discount_cost_cents,message_cost_cents,metrics)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s::jsonb)""",
            (tenant_id, mission_id, treatment_size, holdout_size, treatment_orders, holdout_orders,
             incremental_orders, revenue, int(max(0, incremental_orders * average_revenue)),
             outcomes.get("treatment", {}).get("margin", 0), outcomes.get("treatment", {}).get("discount", 0),
             json.dumps({"treatmentRate": treatment_rate, "holdoutRate": holdout_rate, "messagesSent": sent, **extra_metrics})),
        )


def monitor_running_missions(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    cursor.execute(
        """UPDATE missions SET status = 'COMPLETED', completed_at = NOW(), updated_at = NOW()
           WHERE tenant_id = %s AND status = 'RUNNING' AND end_at IS NOT NULL AND end_at <= NOW()
           RETURNING id""",
        (tenant_id,),
    )
    for row in cursor.fetchall():
        emit_server_event(cursor, tenant_id=tenant_id, event_name="mission_completed", event_id=f"mission-completed:{row[0]}", mission_id=str(row[0]), properties={})
    refresh_mission_results(cursor, tenant_id)
