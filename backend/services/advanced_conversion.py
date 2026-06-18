import json
import os
from datetime import date, timedelta
from typing import Any, Optional

from fastapi import HTTPException

from services.commerce import RequestedLine, price_menu_lines


MEAT_TERMS = {"chicken", "beef", "meat", "pepperoni", "bacon", "mutton", "fish", "shrimp", "prawn"}
SPICY_TERMS = {"spicy", "hot", "jalapeno", "chilli", "chili"}


def _row_item(row: tuple) -> dict[str, Any]:
    return {
        "id": int(row[0]),
        "name": row[1],
        "category": row[2] or "",
        "description": row[3] or "",
        "priceCents": int(row[4]),
        "costCents": int(row[5] or 0) + int(row[6] or 0),
        "image": row[7],
        "isSpicy": bool(row[8]),
        "isPopular": bool(row[9]),
    }


def _matches_constraints(item: dict[str, Any], dietary: set[str], excluded: set[str]) -> bool:
    haystack = f"{item['name']} {item['category']} {item['description']}".lower()
    if excluded and any(term in haystack for term in excluded):
        return False
    if "vegetarian" in dietary and any(term in haystack for term in MEAT_TERMS):
        return False
    if "not_spicy" in dietary and (item["isSpicy"] or any(term in haystack for term in SPICY_TERMS)):
        return False
    return True


def build_order_architect_suggestion(
    cursor,
    *,
    tenant_id: int,
    visitor_id: Optional[str],
    session_id: Optional[str],
    customer_id: Optional[str],
    budget_cents: Optional[int],
    party_size: int,
    dietary_constraints: list[str],
    excluded_ingredients: list[str],
    preferences: dict[str, Any],
) -> dict[str, Any]:
    budget = int(budget_cents or 0)
    dietary = {str(item).strip().lower() for item in dietary_constraints if str(item).strip()}
    excluded = {str(item).strip().lower() for item in excluded_ingredients if str(item).strip()}
    cursor.execute(
        """SELECT id,name,category,description,COALESCE(sale_price_cents, price_cents),
                  ingredient_cost_cents,packaging_cost_cents,image,is_spicy,is_popular
           FROM menu_items
           WHERE restaurant_id=%s AND is_available=true
           ORDER BY is_popular DESC, rating DESC NULLS LAST, COALESCE(sale_price_cents, price_cents) ASC
           LIMIT 200""",
        (tenant_id,),
    )
    candidates = [_row_item(row) for row in cursor.fetchall()]
    filtered = [item for item in candidates if _matches_constraints(item, dietary, excluded)]
    max_items = max(1, min(20, party_size * 3))
    selected: list[dict[str, Any]] = []
    subtotal = 0
    categories_seen: set[str] = set()

    preferred_categories = {str(value).lower() for value in preferences.get("categories", []) if str(value).strip()}
    filtered.sort(
        key=lambda item: (
            0 if item["category"].lower() in preferred_categories else 1,
            0 if item["isPopular"] else 1,
            -max(0, item["priceCents"] - item["costCents"]),
        )
    )
    for item in filtered:
        if len(selected) >= max_items:
            break
        if budget and subtotal + item["priceCents"] > budget:
            continue
        if item["category"] in categories_seen and len(selected) < party_size:
            continue
        selected.append(item)
        categories_seen.add(item["category"])
        subtotal += item["priceCents"]

    if not selected and filtered:
        cheapest = min(filtered, key=lambda item: item["priceCents"])
        if not budget or cheapest["priceCents"] <= budget:
            selected = [cheapest]
            subtotal = cheapest["priceCents"]

    if not selected:
        status = "NO_MATCH"
        explanation = "No available menu combination satisfies the current budget and dietary constraints."
    else:
        status = "COMPLETED"
        explanation = "Built from currently available menu items using server prices, budget, party size, and dietary constraints."

    priced_items = []
    estimated_margin = None
    if selected:
        priced = price_menu_lines(cursor, tenant_id, [RequestedLine(menu_item_id=item["id"], quantity=1) for item in selected])
        priced_items = [
            {
                "menuItemId": line.menu_item_id,
                "name": line.name,
                "category": line.category,
                "quantity": line.quantity,
                "priceCents": line.net_unit_price_cents,
                "lineTotalCents": line.line_revenue_cents,
            }
            for line in priced
        ]
        margins = [line.line_margin_cents for line in priced]
        if all(value is not None for value in margins):
            estimated_margin = sum(int(value or 0) for value in margins)
        subtotal = sum(line.line_revenue_cents for line in priced)

    cursor.execute(
        """INSERT INTO order_architect_requests
           (tenant_id,visitor_id,session_id,customer_id,budget_cents,party_size,
            dietary_constraints,excluded_ingredients,preferences,status)
           VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s)
           RETURNING id""",
        (
            tenant_id,
            visitor_id,
            session_id,
            customer_id,
            budget_cents,
            party_size,
            json.dumps(dietary_constraints),
            json.dumps(excluded_ingredients),
            json.dumps(preferences),
            status,
        ),
    )
    request_id = int(cursor.fetchone()[0])
    cursor.execute(
        """INSERT INTO order_architect_suggestions
           (tenant_id,request_id,items,subtotal_cents,estimated_margin_cents,explanation,constraints_satisfied)
           VALUES (%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb)
           RETURNING id""",
        (
            tenant_id,
            request_id,
            json.dumps(priced_items),
            subtotal,
            estimated_margin,
            explanation,
            json.dumps({"budgetCents": budget_cents, "partySize": party_size, "dietaryConstraints": dietary_constraints}),
        ),
    )
    suggestion_id = int(cursor.fetchone()[0])
    return {
        "requestId": request_id,
        "suggestionId": suggestion_id,
        "status": status,
        "items": priced_items,
        "subtotalCents": subtotal,
        "estimatedMarginCents": estimated_margin,
        "explanation": explanation,
        "constraintsSatisfied": {"budgetCents": budget_cents, "partySize": party_size, "dietaryConstraints": dietary_constraints},
    }


def compute_private_offer_discount(
    *,
    subtotal_cents: int,
    discount_type: str,
    discount_value: int,
    max_discount_cents: Optional[int],
) -> int:
    if discount_type == "PERCENT":
        discount = subtotal_cents * min(discount_value, 100) // 100
    elif discount_type == "FIXED":
        discount = discount_value
    else:
        raise ValueError("Unsupported discount type")
    if max_discount_cents is not None:
        discount = min(discount, int(max_discount_cents))
    return max(0, min(discount, subtotal_cents))


def validate_private_offer(
    cursor,
    *,
    tenant_id: int,
    code: str,
    subtotal_cents: int,
    estimated_margin_before_discount_cents: Optional[int],
    visitor_id: Optional[str],
    customer_id: Optional[str],
) -> dict[str, Any]:
    cursor.execute(
        """SELECT id,title,description,target_segment,customer_id,visitor_id,discount_type,discount_value,
                  max_discount_cents,minimum_subtotal_cents,minimum_margin_cents,max_redemptions,rules
           FROM private_offers
           WHERE tenant_id=%s AND lower(code)=lower(%s) AND status='RUNNING'
             AND (starts_at IS NULL OR starts_at <= NOW()) AND (ends_at IS NULL OR ends_at > NOW())
           LIMIT 1""",
        (tenant_id, code),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Private offer not found")
    offer = {
        "id": int(row[0]),
        "title": row[1],
        "description": row[2],
        "targetSegment": row[3],
        "customerId": row[4],
        "visitorId": row[5],
        "discountType": row[6],
        "discountValue": int(row[7]),
        "maxDiscountCents": row[8],
        "minimumSubtotalCents": int(row[9] or 0),
        "minimumMarginCents": int(row[10] or 0),
        "maxRedemptions": row[11],
        "rules": row[12] or {},
    }
    if offer["customerId"] and offer["customerId"] != customer_id:
        raise HTTPException(status_code=403, detail="Private offer is not assigned to this customer")
    if offer["visitorId"] and offer["visitorId"] != visitor_id:
        raise HTTPException(status_code=403, detail="Private offer is not assigned to this visitor")
    if subtotal_cents < offer["minimumSubtotalCents"]:
        raise HTTPException(status_code=409, detail="Cart does not meet the private offer minimum")
    if offer["maxRedemptions"]:
        cursor.execute(
            "SELECT count(*) FROM private_offer_redemptions WHERE tenant_id=%s AND offer_id=%s AND status='REDEEMED'",
            (tenant_id, offer["id"]),
        )
        if int(cursor.fetchone()[0]) >= int(offer["maxRedemptions"]):
            raise HTTPException(status_code=409, detail="Private offer redemption limit reached")
    discount = compute_private_offer_discount(
        subtotal_cents=subtotal_cents,
        discount_type=offer["discountType"],
        discount_value=offer["discountValue"],
        max_discount_cents=offer["maxDiscountCents"],
    )
    margin_after = None if estimated_margin_before_discount_cents is None else estimated_margin_before_discount_cents - discount
    if margin_after is not None and margin_after < offer["minimumMarginCents"]:
        raise HTTPException(status_code=409, detail="Private offer would breach minimum contribution margin")
    offer["discountCents"] = discount
    offer["contributionMarginAfterDiscountCents"] = margin_after
    return offer


def list_personalized_merchandising(
    cursor,
    *,
    tenant_id: int,
    visitor_id: str,
    session_id: str,
    placement: str,
    customer_id: Optional[str],
    segment: Optional[str],
) -> dict[str, Any]:
    cursor.execute(
        """SELECT id,code,title,description,discount_type,discount_value,max_discount_cents,minimum_subtotal_cents
           FROM private_offers
           WHERE tenant_id=%s AND status='RUNNING'
             AND (starts_at IS NULL OR starts_at <= NOW()) AND (ends_at IS NULL OR ends_at > NOW())
             AND (customer_id IS NULL OR customer_id=%s)
             AND (visitor_id IS NULL OR visitor_id=%s)
             AND (target_segment IS NULL OR target_segment=%s)
           ORDER BY updated_at DESC LIMIT 3""",
        (tenant_id, customer_id, visitor_id, segment),
    )
    offers = [
        {
            "id": int(row[0]),
            "code": row[1],
            "title": row[2],
            "description": row[3],
            "discountType": row[4],
            "discountValue": int(row[5]),
            "maxDiscountCents": row[6],
            "minimumSubtotalCents": int(row[7] or 0),
        }
        for row in cursor.fetchall()
    ]
    cursor.execute(
        """WITH ranked_classifications AS (
               SELECT tenant_id,item_id,classification,
                      ROW_NUMBER() OVER (
                          PARTITION BY tenant_id,item_id
                          ORDER BY updated_at DESC, confidence_score DESC
                      ) AS rn
               FROM menu_item_classifications
               WHERE tenant_id=%s
           )
           SELECT mi.id,mi.name,mi.category,COALESCE(mi.sale_price_cents,mi.price_cents),mi.image
           FROM menu_items mi
           LEFT JOIN ranked_classifications mc
             ON mc.tenant_id=mi.restaurant_id AND mc.item_id=mi.id AND mc.rn=1
           WHERE mi.restaurant_id=%s AND mi.is_available=true
           ORDER BY CASE WHEN mc.classification IN ('HERO','HIDDEN_WINNER') THEN 0 ELSE 1 END,
                    mi.is_popular DESC, mi.rating DESC NULLS LAST, mi.id ASC
           LIMIT 8""",
        (tenant_id, tenant_id),
    )
    items = [
        {"id": int(row[0]), "name": row[1], "category": row[2], "priceCents": int(row[3]), "image": row[4]}
        for row in cursor.fetchall()
    ]
    event_key = f"merch:{placement}:{session_id}:{visitor_id}"
    cursor.execute(
        """INSERT INTO merchandising_events
           (tenant_id,event_key,visitor_id,session_id,customer_id,placement,item_ids,offer_id,properties)
           VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb)
           ON CONFLICT DO NOTHING""",
        (
            tenant_id,
            event_key,
            visitor_id,
            session_id,
            customer_id,
            placement,
            json.dumps([item["id"] for item in items]),
            offers[0]["id"] if offers else None,
            json.dumps({"segment": segment}),
        ),
    )
    return {"offers": offers, "items": items}


def refresh_tenant_demand_twin(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    snapshot_date = date.fromisoformat(str(metadata.get("date"))) if metadata.get("date") else date.today()
    window_days = max(7, int(metadata.get("windowDays") or os.getenv("DEMAND_TWIN_WINDOW_DAYS", "30")))
    threshold = max(1, int(metadata.get("privacyThreshold") or os.getenv("DEMAND_TWIN_PRIVACY_THRESHOLD", "5")))
    window_start = snapshot_date - timedelta(days=window_days - 1)
    cursor.execute(
        """SELECT COALESCE(sum(completed_orders),0),COALESCE(sum(revenue_cents),0),COALESCE(sum(sessions),0),
                  COALESCE(sum(cart_sessions),0),COALESCE(sum(checkout_sessions),0)
           FROM daily_funnel_metrics
           WHERE tenant_id=%s AND metric_date BETWEEN %s AND %s""",
        (tenant_id, window_start, snapshot_date),
    )
    orders, revenue, sessions, carts, checkouts = (int(value or 0) for value in cursor.fetchone())
    metrics = {
        "orders": orders,
        "revenueCents": revenue,
        "sessions": sessions,
        "cartSessions": carts,
        "checkoutSessions": checkouts,
        "conversionRate": orders / sessions if sessions >= threshold else None,
        "averageOrderValueCents": revenue // orders if orders >= threshold else None,
    }
    cursor.execute(
        """SELECT segment,COALESCE(sum(customers),0),COALESCE(sum(orders),0),COALESCE(sum(revenue_cents),0)
           FROM daily_customer_metrics WHERE tenant_id=%s AND metric_date BETWEEN %s AND %s GROUP BY segment""",
        (tenant_id, window_start, snapshot_date),
    )
    segments = {
        row[0]: {"customers": int(row[1]), "orders": int(row[2]), "revenueCents": int(row[3])}
        for row in cursor.fetchall()
        if int(row[1] or 0) >= threshold
    }
    cursor.execute(
        """SELECT mi.name,mc.classification,mc.confidence_score,mc.metrics
           FROM menu_item_classifications mc
           JOIN menu_items mi ON mi.restaurant_id=mc.tenant_id AND mi.id=mc.item_id
           WHERE mc.tenant_id=%s ORDER BY mc.updated_at DESC LIMIT 20""",
        (tenant_id,),
    )
    menu_insights = [
        {"name": row[0], "classification": row[1], "confidence": float(row[2] or 0), "evidence": row[3]}
        for row in cursor.fetchall()
    ]
    cursor.execute(
        """SELECT source,medium,COALESCE(sum(sessions),0),COALESCE(sum(orders),0),COALESCE(sum(revenue_cents),0)
           FROM daily_source_metrics WHERE tenant_id=%s AND metric_date BETWEEN %s AND %s
           GROUP BY source,medium ORDER BY sum(sessions) DESC LIMIT 12""",
        (tenant_id, window_start, snapshot_date),
    )
    source_mix = [
        {"source": row[0], "medium": row[1], "sessions": int(row[2]), "orders": int(row[3]), "revenueCents": int(row[4])}
        for row in cursor.fetchall()
        if int(row[2] or 0) >= threshold
    ]
    cursor.execute(
        """INSERT INTO tenant_demand_twins
           (tenant_id,snapshot_date,window_start,window_end,privacy_threshold,metrics,segments,menu_insights,source_mix)
           VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb)
           ON CONFLICT (tenant_id,snapshot_date) DO UPDATE SET
             window_start=EXCLUDED.window_start,window_end=EXCLUDED.window_end,
             privacy_threshold=EXCLUDED.privacy_threshold,metrics=EXCLUDED.metrics,
             segments=EXCLUDED.segments,menu_insights=EXCLUDED.menu_insights,
             source_mix=EXCLUDED.source_mix,generated_at=NOW()""",
        (
            tenant_id,
            snapshot_date,
            window_start,
            snapshot_date,
            threshold,
            json.dumps(metrics),
            json.dumps(segments),
            json.dumps(menu_insights),
            json.dumps(source_mix),
        ),
    )


def refresh_neighborhood_benchmarks(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    benchmark_date = date.fromisoformat(str(metadata.get("date"))) if metadata.get("date") else date.today()
    threshold = max(3, int(metadata.get("privacyThreshold") or os.getenv("BENCHMARK_PRIVACY_THRESHOLD", "5")))
    cursor.execute(
        "SELECT COALESCE(min(city), 'unknown') FROM branches WHERE restaurant_id=%s",
        (tenant_id,),
    )
    neighborhood = (cursor.fetchone()[0] or "unknown").strip().lower() or "unknown"
    cursor.execute(
        """WITH peers AS (
               SELECT DISTINCT b.restaurant_id
               FROM branches b
               WHERE lower(COALESCE(b.city,'unknown'))=%s
           ), metrics AS (
               SELECT df.tenant_id, sum(df.completed_orders) AS orders, sum(df.revenue_cents) AS revenue, sum(df.sessions) AS sessions
               FROM daily_funnel_metrics df JOIN peers p ON p.restaurant_id=df.tenant_id
               WHERE df.metric_date BETWEEN %s - INTERVAL '29 days' AND %s
               GROUP BY df.tenant_id
           )
           SELECT count(*),COALESCE(avg(orders),0),COALESCE(avg(revenue),0),COALESCE(avg(sessions),0)
           FROM metrics""",
        (neighborhood, benchmark_date, benchmark_date),
    )
    peer_count, avg_orders, avg_revenue, avg_sessions = cursor.fetchone()
    peer_count = int(peer_count or 0)
    status = "READY" if peer_count >= threshold else "INSUFFICIENT_PEERS"
    metrics = {} if status != "READY" else {
        "averageOrders30d": float(avg_orders or 0),
        "averageRevenueCents30d": float(avg_revenue or 0),
        "averageSessions30d": float(avg_sessions or 0),
    }
    cursor.execute(
        """INSERT INTO neighborhood_benchmark_snapshots
           (tenant_id,benchmark_date,neighborhood_key,privacy_threshold,peer_count,status,metrics)
           VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
           ON CONFLICT (tenant_id,benchmark_date,neighborhood_key) DO UPDATE SET
             privacy_threshold=EXCLUDED.privacy_threshold,peer_count=EXCLUDED.peer_count,
             status=EXCLUDED.status,metrics=EXCLUDED.metrics,generated_at=NOW()""",
        (tenant_id, benchmark_date, neighborhood, threshold, peer_count, status, json.dumps(metrics)),
    )


def refresh_performance_review(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    cursor.execute(
        """SELECT count(*) FILTER (WHERE status='pending'), count(*) FILTER (WHERE status='running'),
                  count(*) FILTER (WHERE status='failed' AND updated_at >= NOW() - INTERVAL '24 hours'),
                  COALESCE(avg(EXTRACT(EPOCH FROM (started_at-created_at))) FILTER (WHERE started_at IS NOT NULL), 0)
           FROM job_runs WHERE tenant_id=%s""",
        (tenant_id,),
    )
    pending, running, failed, latency = cursor.fetchone()
    queue = {
        "pendingJobs": int(pending or 0),
        "runningJobs": int(running or 0),
        "failedJobs24h": int(failed or 0),
        "averageLatencySeconds": float(latency or 0),
    }
    cursor.execute(
        """INSERT INTO queue_health_snapshots
           (tenant_id,pending_jobs,running_jobs,failed_jobs_24h,average_latency_seconds,details)
           VALUES (%s,%s,%s,%s,%s,%s::jsonb)""",
        (tenant_id, queue["pendingJobs"], queue["runningJobs"], queue["failedJobs24h"], queue["averageLatencySeconds"], json.dumps(queue)),
    )
    large_tables = []
    for table in ("analytics_events", "job_runs", "orders"):
        cursor.execute(f"SELECT count(*) FROM {table} WHERE " + ("tenant_id=%s" if table != "orders" else "restaurant_id=%s"), (tenant_id,))
        count = int(cursor.fetchone()[0])
        if count >= int(os.getenv("PARTITION_REVIEW_ROW_THRESHOLD", "1000000")):
            large_tables.append({"table": table, "tenantRows": count, "recommendation": "review monthly partitioning"})
    pooling = {
        "enabled": os.getenv("DB_POOL_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
        "minConnections": int(os.getenv("DB_POOL_MIN_CONNECTIONS", "1")),
        "maxConnections": int(os.getenv("DB_POOL_MAX_CONNECTIONS", "5")),
    }
    status = "ATTENTION_REQUIRED" if queue["failedJobs24h"] or large_tables else "RECORDED"
    cursor.execute(
        """INSERT INTO performance_reviews
           (tenant_id,database_pooling,queue_throughput,partition_recommendations,status)
           VALUES (%s,%s::jsonb,%s::jsonb,%s::jsonb,%s)""",
        (tenant_id, json.dumps(pooling), json.dumps(queue), json.dumps(large_tables), status),
    )
