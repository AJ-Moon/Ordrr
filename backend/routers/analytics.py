from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db import get_db
from dependencies.auth import get_current_admin
from services.entitlements import require_feature

router = APIRouter()

MAX_RANGE_DAYS = 366


def _date_range(date_from: Optional[date], date_to: Optional[date]) -> tuple[date, date]:
    end = date_to or date.today()
    start = date_from or (end - timedelta(days=29))
    if start > end:
        raise HTTPException(status_code=422, detail="from must not be after to")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail=f"Date range cannot exceed {MAX_RANGE_DAYS} days")
    return start, end


@router.get("/analytics/overview")
def get_overview(
    dateFrom: Optional[date] = Query(default=None, alias="from"),
    dateTo: Optional[date] = Query(default=None, alias="to"),
    admin: dict = Depends(get_current_admin),
    _feature=Depends(require_feature("analytics.item_funnel")),
):
    tenant_id = int(admin["restaurant_id"])
    start, end = _date_range(dateFrom, dateTo)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COALESCE(sum(sessions), 0), COALESCE(sum(menu_sessions), 0),
                          COALESCE(sum(cart_sessions), 0), COALESCE(sum(checkout_sessions), 0),
                          COALESCE(sum(ordering_sessions), 0), COALESCE(sum(completed_orders), 0),
                          COALESCE(sum(revenue_cents), 0)
                   FROM daily_funnel_metrics
                   WHERE tenant_id = %s AND location_id = 0 AND metric_date BETWEEN %s AND %s""",
                (tenant_id, start, end),
            )
            sessions, menu_sessions, cart_sessions, checkout_sessions, ordering_sessions, completed_orders, revenue_cents = cur.fetchone()
            cur.execute(
                """SELECT bool_or(contribution_margin_cents IS NULL AND orders > 0), COALESCE(sum(contribution_margin_cents), 0)
                   FROM daily_item_metrics
                   WHERE tenant_id = %s AND location_id = 0 AND metric_date BETWEEN %s AND %s""",
                (tenant_id, start, end),
            )
            margin_incomplete, margin_cents = cur.fetchone()
    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "sessions": int(sessions),
        "menuSessions": int(menu_sessions),
        "cartSessions": int(cart_sessions),
        "checkoutSessions": int(checkout_sessions),
        "orderingSessions": int(ordering_sessions),
        "completedOrders": int(completed_orders),
        "revenueCents": int(revenue_cents),
        "contributionMarginCents": None if margin_incomplete else int(margin_cents),
        "conversionRate": (int(completed_orders) / int(sessions)) if sessions else None,
    }


@router.get("/analytics/items")
def get_item_funnel(
    dateFrom: Optional[date] = Query(default=None, alias="from"),
    dateTo: Optional[date] = Query(default=None, alias="to"),
    category: Optional[str] = Query(default=None, max_length=100),
    itemId: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=250, ge=1, le=500),
    admin: dict = Depends(get_current_admin),
    _feature=Depends(require_feature("analytics.item_funnel")),
):
    tenant_id = int(admin["restaurant_id"])
    start, end = _date_range(dateFrom, dateTo)
    with get_db() as conn:
        with conn.cursor() as cur:
            filters = ["m.restaurant_id = %s"]
            params: list = [start, end, tenant_id]
            if category:
                filters.append("m.category = %s")
                params.append(category)
            if itemId:
                filters.append("m.id = %s")
                params.append(itemId)
            params.append(limit)
            cur.execute(
                f"""SELECT m.id, m.name, m.category, m.is_available,
                          COALESCE(SUM(d.impressions), 0), COALESCE(SUM(d.detail_views), 0),
                          COALESCE(SUM(d.add_to_carts), 0), COALESCE(SUM(d.orders), 0),
                          COALESCE(SUM(d.quantity_sold), 0), COALESCE(SUM(d.revenue_cents), 0),
                          CASE WHEN bool_or(d.contribution_margin_cents IS NULL AND d.orders > 0)
                               THEN NULL ELSE SUM(d.contribution_margin_cents) END,
                          COALESCE(SUM(d.unique_impression_sessions), 0),
                          COALESCE(SUM(d.unique_detail_view_sessions), 0),
                          COALESCE(SUM(d.modifier_starts), 0),
                          COALESCE(SUM(d.unique_add_to_cart_sessions), 0),
                          COALESCE(SUM(d.checkout_count), 0), COALESCE(SUM(d.purchase_count), 0),
                          COALESCE(SUM(d.unique_carts), 0), COALESCE(SUM(d.discount_cents), 0),
                          COALESCE(SUM(d.refund_count), 0), c.classification, c.confidence_score,
                          c.category_attention_baseline, c.category_conversion_baseline
                   FROM menu_items m
                   LEFT JOIN daily_item_metrics d
                     ON d.tenant_id = m.restaurant_id AND d.item_id = m.id AND d.location_id = 0
                    AND d.metric_date BETWEEN %s AND %s
                   LEFT JOIN LATERAL (
                     SELECT classification, confidence_score, category_attention_baseline, category_conversion_baseline
                     FROM menu_item_classifications mc WHERE mc.tenant_id = m.restaurant_id AND mc.item_id = m.id
                       AND mc.period_end <= %s ORDER BY mc.period_end DESC LIMIT 1
                   ) c ON TRUE
                   WHERE {' AND '.join(filters)}
                   GROUP BY m.id, m.name, m.category, m.is_available, c.classification,
                            c.confidence_score, c.category_attention_baseline, c.category_conversion_baseline
                   ORDER BY COALESCE(SUM(d.revenue_cents), 0) DESC, m.name LIMIT %s""",
                [start, end, end, *params[2:]],
            )
            rows = cur.fetchall()
    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "items": [
            {
                "itemId": row[0], "name": row[1], "category": row[2], "isAvailable": row[3],
                "impressions": int(row[4]), "detailViews": int(row[5]), "addToCarts": int(row[6]),
                "orders": int(row[7]), "quantitySold": int(row[8]), "revenueCents": int(row[9]),
                "contributionMarginCents": int(row[10]) if row[10] is not None else None,
                "uniqueImpressionSessions": int(row[11]), "uniqueDetailViewSessions": int(row[12]),
                "modifierStarts": int(row[13]), "uniqueAddToCartSessions": int(row[14]),
                "checkoutCount": int(row[15]), "purchaseCount": int(row[16]), "uniqueCarts": int(row[17]),
                "discountCents": int(row[18]), "refundCount": int(row[19]),
                "detailViewRate": (int(row[12]) / int(row[11])) if row[11] else None,
                "addToCartRate": (int(row[14]) / int(row[12])) if row[12] else None,
                "purchaseRate": (int(row[16]) / int(row[12])) if row[12] else None,
                "cartSurvivalRate": (int(row[16]) / int(row[17])) if row[17] else None,
                "revenuePerViewCents": (int(row[9]) // int(row[12])) if row[12] else None,
                "averageSellingPriceCents": (int(row[9]) // int(row[8])) if row[8] else None,
                "classification": row[20] or "INSUFFICIENT_DATA",
                "classificationConfidence": float(row[21]) if row[21] is not None else 0,
                "categoryAttentionBaseline": float(row[22]) if row[22] is not None else None,
                "categoryConversionBaseline": float(row[23]) if row[23] is not None else None,
                "minimumSampleWarning": int(row[12]) < 20,
            }
            for row in rows
        ],
    }


@router.get("/analytics/funnel")
def get_funnel_series(
    dateFrom: Optional[date] = Query(default=None, alias="from"),
    dateTo: Optional[date] = Query(default=None, alias="to"),
    admin: dict = Depends(get_current_admin),
    _feature=Depends(require_feature("analytics.checkout_friction")),
):
    tenant_id = int(admin["restaurant_id"])
    start, end = _date_range(dateFrom, dateTo)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT metric_date, sessions, menu_sessions, cart_sessions, checkout_sessions,
                          ordering_sessions, completed_orders, revenue_cents
                   FROM daily_funnel_metrics
                   WHERE tenant_id = %s AND location_id = 0 AND metric_date BETWEEN %s AND %s
                   ORDER BY metric_date""",
                (tenant_id, start, end),
            )
            rows = cur.fetchall()
    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "days": [
            {
                "date": row[0].isoformat(), "sessions": int(row[1]), "menuSessions": int(row[2]),
                "cartSessions": int(row[3]), "checkoutSessions": int(row[4]),
                "orderingSessions": int(row[5]), "completedOrders": int(row[6]), "revenueCents": int(row[7]),
            }
            for row in rows
        ],
    }


@router.get("/analytics/search")
def get_search_gaps(
    dateFrom: Optional[date] = Query(default=None, alias="from"),
    dateTo: Optional[date] = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    admin: dict = Depends(get_current_admin),
    _feature=Depends(require_feature("analytics.search_gap")),
):
    tenant_id = int(admin["restaurant_id"])
    start, end = _date_range(dateFrom, dateTo)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT normalized_query, COALESCE(SUM(searches), 0), COALESCE(SUM(zero_result_searches), 0),
                          COALESCE(SUM(clicks), 0), COALESCE(SUM(add_to_carts), 0), COALESCE(SUM(orders), 0)
                   FROM daily_search_metrics
                   WHERE tenant_id = %s AND metric_date BETWEEN %s AND %s
                   GROUP BY normalized_query
                   ORDER BY SUM(zero_result_searches) DESC, SUM(searches) DESC
                   LIMIT %s""",
                (tenant_id, start, end, limit),
            )
            rows = cur.fetchall()
    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "queries": [
            {
                "query": row[0], "searches": int(row[1]), "zeroResultSearches": int(row[2]),
                "clicks": int(row[3]), "addToCarts": int(row[4]), "orders": int(row[5]),
            }
            for row in rows
        ],
    }


@router.get("/analytics/checkout")
def get_checkout_friction(
    dateFrom: Optional[date] = Query(default=None, alias="from"),
    dateTo: Optional[date] = Query(default=None, alias="to"),
    admin: dict = Depends(get_current_admin),
    _feature=Depends(require_feature("analytics.checkout_friction")),
):
    tenant_id = int(admin["restaurant_id"])
    start, end = _date_range(dateFrom, dateTo)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT step, COALESCE(SUM(entered), 0), COALESCE(SUM(completed), 0), COALESCE(SUM(failures), 0),
                          COALESCE(SUM(delivery_area_rejections), 0), COALESCE(SUM(minimum_order_blocks), 0),
                          COALESCE(SUM(coupon_failures), 0), COALESCE(SUM(mobile_entered), 0), COALESCE(SUM(mobile_completed), 0)
                   FROM daily_checkout_metrics
                   WHERE tenant_id = %s AND metric_date BETWEEN %s AND %s
                   GROUP BY step
                   ORDER BY SUM(entered) DESC""",
                (tenant_id, start, end),
            )
            rows = cur.fetchall()
    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "steps": [
            {
                "step": row[0], "entered": int(row[1]), "completed": int(row[2]), "failures": int(row[3]),
                "dropOffRate": max(0, 1 - int(row[2]) / int(row[1])) if row[1] else None,
                "paymentFailureRate": (int(row[3]) / int(row[1])) if row[1] else None,
                "deliveryAreaRejections": int(row[4]), "minimumOrderBlocks": int(row[5]),
                "couponFailures": int(row[6]), "mobileEntered": int(row[7]), "mobileCompleted": int(row[8]),
                "mobileDropOffRate": max(0, 1 - int(row[8]) / int(row[7])) if row[7] else None,
            }
            for row in rows
        ],
    }


@router.get("/analytics/sources")
@router.get("/analytics/acquisition")
def get_source_conversion(
    dateFrom: Optional[date] = Query(default=None, alias="from"),
    dateTo: Optional[date] = Query(default=None, alias="to"),
    source: Optional[str] = Query(default=None),
    medium: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    admin: dict = Depends(get_current_admin),
    _feature=Depends(require_feature("analytics.traffic_sources")),
):
    tenant_id = int(admin["restaurant_id"])
    start, end = _date_range(dateFrom, dateTo)
    filters = ["tenant_id = %s", "metric_date BETWEEN %s AND %s"]
    params: list = [tenant_id, start, end]
    if source:
        filters.append("source = %s")
        params.append(source)
    if medium:
        filters.append("medium = %s")
        params.append(medium)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT source, medium, campaign, COALESCE(SUM(sessions), 0), COALESCE(SUM(orders), 0),
                           COALESCE(SUM(revenue_cents), 0),
                           CASE WHEN bool_or(contribution_margin_cents IS NULL AND orders > 0)
                                THEN NULL ELSE SUM(contribution_margin_cents) END,
                           COALESCE(SUM(new_visitors), 0), COALESCE(SUM(returning_visitors), 0),
                           COALESCE(SUM(item_views), 0), COALESCE(SUM(cart_sessions), 0),
                           COALESCE(SUM(checkout_sessions), 0), COALESCE(SUM(repeat_customers), 0)
                    FROM daily_source_metrics
                    WHERE {' AND '.join(filters)}
                    GROUP BY source, medium, campaign
                    ORDER BY SUM(sessions) DESC LIMIT %s""",
                [*params, limit],
            )
            rows = cur.fetchall()
    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "sources": [
            {
                "source": row[0], "medium": row[1], "campaign": row[2] or None,
                "sessions": int(row[3]), "orders": int(row[4]), "revenueCents": int(row[5]),
                "contributionMarginCents": int(row[6]) if row[6] is not None else None,
                "conversionRate": (int(row[4]) / int(row[3])) if row[3] else None,
                "newVisitors": int(row[7]), "returningVisitors": int(row[8]), "itemViews": int(row[9]),
                "cartSessions": int(row[10]), "checkoutSessions": int(row[11]), "repeatCustomers": int(row[12]),
                "cartRate": (int(row[10]) / int(row[3])) if row[3] else None,
                "checkoutRate": (int(row[11]) / int(row[3])) if row[3] else None,
                "revenuePerSessionCents": (int(row[5]) // int(row[3])) if row[3] else None,
                "averageOrderValueCents": (int(row[5]) // int(row[4])) if row[4] else None,
            }
            for row in rows
        ],
    }


@router.get("/analytics/chat")
@router.get("/analytics/chatbot")
def get_chat_intents(
    dateFrom: Optional[date] = Query(default=None, alias="from"),
    dateTo: Optional[date] = Query(default=None, alias="to"),
    admin: dict = Depends(get_current_admin),
    _feature=Depends(require_feature("analytics.chat_objections")),
):
    tenant_id = int(admin["restaurant_id"])
    start, end = _date_range(dateFrom, dateTo)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT intent, COALESCE(SUM(messages), 0), COALESCE(SUM(recommendations), 0),
                          COALESCE(SUM(clicks), 0), COALESCE(SUM(orders), 0)
                   FROM daily_chat_metrics
                   WHERE tenant_id = %s AND metric_date BETWEEN %s AND %s
                   GROUP BY intent
                   ORDER BY SUM(messages) DESC""",
                (tenant_id, start, end),
            )
            rows = cur.fetchall()
    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "intents": [
            {"intent": row[0], "messages": int(row[1]), "recommendations": int(row[2]), "clicks": int(row[3]),
             "orders": int(row[4]), "recommendationClickRate": (int(row[3]) / int(row[2])) if row[2] else None}
            for row in rows
        ],
    }


@router.get("/analytics/baskets")
def get_basket_associations(
    limit: int = Query(default=25, ge=1, le=100),
    admin: dict = Depends(get_current_admin),
    _feature=Depends(require_feature("analytics.basket")),
):
    tenant_id = int(admin["restaurant_id"])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT max(window_end) FROM basket_associations WHERE tenant_id = %s", (tenant_id,))
            window_end = cur.fetchone()[0]
            rows = []
            window_start = None
            if window_end:
                cur.execute(
                    """SELECT ba.item_a_id, ma.name, ba.item_b_id, mb.name,
                              ba.pair_orders, ba.support, ba.confidence, ba.reverse_confidence,
                              ba.lift, ba.window_start, ba.combined_revenue_cents, ba.contribution_margin_cents
                       FROM basket_associations ba
                       JOIN menu_items ma ON ma.id = ba.item_a_id
                       JOIN menu_items mb ON mb.id = ba.item_b_id
                       WHERE ba.tenant_id = %s AND ba.window_end = %s
                       ORDER BY ba.lift DESC NULLS LAST, ba.pair_orders DESC
                       LIMIT %s""",
                    (tenant_id, window_end, limit),
                )
                rows = cur.fetchall()
                window_start = rows[0][9] if rows else None
    return {
        "window": {
            "start": window_start.isoformat() if window_start else None,
            "end": window_end.isoformat() if window_end else None,
        },
        "pairs": [
            {
                "itemAId": row[0], "itemAName": row[1], "itemBId": row[2], "itemBName": row[3],
                "pairOrders": int(row[4]),
                "support": float(row[5]) if row[5] is not None else None,
                "confidence": float(row[6]) if row[6] is not None else None,
                "reverseConfidence": float(row[7]) if row[7] is not None else None,
                "lift": float(row[8]) if row[8] is not None else None,
                "combinedRevenueCents": int(row[10]) if row[10] is not None else None,
                "contributionMarginCents": int(row[11]) if row[11] is not None else None,
            }
            for row in rows
        ],
    }


@router.get("/analytics/customers")
def get_customer_segments(
    dateFrom: Optional[date] = Query(default=None, alias="from"),
    dateTo: Optional[date] = Query(default=None, alias="to"),
    admin: dict = Depends(get_current_admin),
    _feature=Depends(require_feature("analytics.customer_segments")),
):
    tenant_id = int(admin["restaurant_id"])
    start, end = _date_range(dateFrom, dateTo)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT segment, COALESCE(SUM(customers), 0), COALESCE(SUM(orders), 0), COALESCE(SUM(revenue_cents), 0)
                   FROM daily_customer_metrics
                   WHERE tenant_id = %s AND metric_date BETWEEN %s AND %s
                   GROUP BY segment
                   ORDER BY segment""",
                (tenant_id, start, end),
            )
            rows = cur.fetchall()
    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "segments": [
            {"segment": row[0], "customers": int(row[1]), "orders": int(row[2]), "revenueCents": int(row[3])}
            for row in rows
        ],
    }
