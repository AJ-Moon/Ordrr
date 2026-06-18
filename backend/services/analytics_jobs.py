import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from services.events import emit_server_event
from services.menu_matrix import refresh_menu_classifications
from services.opportunities import detect_opportunities, generate_weekly_cards
from services.experiments import evaluate_experiments
from services.missions import (
    evaluate_abandoned_carts as evaluate_mission_abandoned_carts,
    evaluate_bundles,
    evaluate_lapsed_customers,
    evaluate_product_demand_tests,
    evaluate_quiet_hours,
    monitor_running_missions,
    refresh_customer_profiles,
)
from services.advanced_conversion import (
    refresh_neighborhood_benchmarks,
    refresh_performance_review,
    refresh_tenant_demand_twin,
)


def _target_date(metadata: dict[str, Any]) -> date:
    raw = metadata.get("date")
    if raw:
        return date.fromisoformat(str(raw))
    return datetime.now(timezone.utc).date()


def aggregate_daily(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    metric_date = _target_date(metadata)

    cursor.execute(
        "DELETE FROM daily_item_metrics WHERE tenant_id = %s AND metric_date = %s AND location_id = 0",
        (tenant_id, metric_date),
    )
    cursor.execute(
        """WITH event_metrics AS (
               SELECT item_id,
                      count(*) FILTER (WHERE event_name = 'item_impression') AS impressions,
                      count(DISTINCT session_id) FILTER (WHERE event_name = 'item_impression') AS unique_impression_sessions,
                      count(*) FILTER (WHERE event_name = 'item_viewed') AS detail_views,
                      count(DISTINCT session_id) FILTER (WHERE event_name = 'item_viewed') AS unique_detail_view_sessions,
                      count(*) FILTER (WHERE event_name = 'modifier_group_viewed') AS modifier_starts,
                      count(*) FILTER (WHERE event_name = 'item_added_to_cart') AS add_to_carts,
                      count(DISTINCT session_id) FILTER (WHERE event_name = 'item_added_to_cart') AS unique_add_to_cart_sessions,
                      count(DISTINCT session_id) FILTER (WHERE event_name IN ('checkout_started','checkout_step_viewed')) AS checkout_count,
                      count(DISTINCT cart_id) FILTER (WHERE event_name = 'item_added_to_cart' AND cart_id IS NOT NULL) AS unique_carts
               FROM analytics_events
               WHERE tenant_id = %s AND occurred_at::date = %s AND item_id IS NOT NULL
               GROUP BY item_id
           ), order_metrics AS (
               SELECT oi.menu_item_id AS item_id, count(DISTINCT oi.order_id) AS orders,
                      sum(oi.quantity) AS quantity_sold,
                      sum(oi.line_revenue_cents) AS revenue_cents,
                      CASE WHEN count(*) FILTER (WHERE oi.line_contribution_margin_cents IS NULL) > 0
                           THEN NULL ELSE sum(oi.line_contribution_margin_cents) END AS margin_cents
               FROM order_line_items oi
               JOIN orders o ON o.id = oi.order_id AND o.restaurant_id = oi.tenant_id
               WHERE oi.tenant_id = %s AND o.completed_at::date = %s AND o.status = 'delivered'
               GROUP BY oi.menu_item_id
           )
           INSERT INTO daily_item_metrics
             (tenant_id, metric_date, location_id, item_id, impressions, unique_impression_sessions,
              detail_views, unique_detail_view_sessions, modifier_starts, add_to_carts,
              unique_add_to_cart_sessions, checkout_count, purchase_count, unique_carts,
              orders, quantity_sold, revenue_cents, contribution_margin_cents)
           SELECT %s, %s, 0, COALESCE(e.item_id, o.item_id),
                  COALESCE(e.impressions, 0), COALESCE(e.unique_impression_sessions, 0),
                  COALESCE(e.detail_views, 0), COALESCE(e.unique_detail_view_sessions, 0),
                  COALESCE(e.modifier_starts, 0), COALESCE(e.add_to_carts, 0),
                  COALESCE(e.unique_add_to_cart_sessions, 0), COALESCE(e.checkout_count, 0),
                  COALESCE(o.orders, 0), COALESCE(e.unique_carts, 0), COALESCE(o.orders, 0),
                  COALESCE(o.quantity_sold, 0), COALESCE(o.revenue_cents, 0), o.margin_cents
           FROM event_metrics e FULL OUTER JOIN order_metrics o ON o.item_id = e.item_id""",
        (tenant_id, metric_date, tenant_id, metric_date, tenant_id, metric_date),
    )

    cursor.execute(
        "DELETE FROM daily_funnel_metrics WHERE tenant_id = %s AND metric_date = %s AND location_id = 0",
        (tenant_id, metric_date),
    )
    cursor.execute(
        """INSERT INTO daily_funnel_metrics
           (tenant_id, metric_date, location_id, sessions, menu_sessions, cart_sessions,
            checkout_sessions, ordering_sessions, completed_orders, revenue_cents)
           SELECT %s, %s, 0,
                  count(DISTINCT session_id),
                  count(DISTINCT session_id) FILTER (WHERE event_name IN ('menu_viewed','item_impression','item_viewed')),
                  count(DISTINCT session_id) FILTER (WHERE event_name IN ('cart_created','cart_viewed','item_added_to_cart')),
                  count(DISTINCT session_id) FILTER (WHERE event_name IN ('checkout_started','checkout_step_viewed')),
                  count(DISTINCT session_id) FILTER (WHERE event_name = 'order_created'),
                  count(DISTINCT order_id) FILTER (WHERE event_name = 'order_completed'),
                  COALESCE((SELECT sum(total_cents) FROM orders
                            WHERE restaurant_id = %s AND completed_at::date = %s AND status = 'delivered'), 0)
           FROM analytics_events
           WHERE tenant_id = %s AND occurred_at::date = %s""",
        (tenant_id, metric_date, tenant_id, metric_date, tenant_id, metric_date),
    )

    cursor.execute("DELETE FROM daily_search_metrics WHERE tenant_id = %s AND metric_date = %s", (tenant_id, metric_date))
    cursor.execute(
        """WITH searches AS (
               SELECT lower(trim(properties->>'query')) AS query, session_id, occurred_at,
                      COALESCE((properties->>'resultCount')::int, 0) AS result_count
               FROM analytics_events
               WHERE tenant_id = %s AND occurred_at::date = %s AND event_name = 'search_performed'
                 AND NULLIF(trim(properties->>'query'), '') IS NOT NULL
           )
           INSERT INTO daily_search_metrics
             (tenant_id, metric_date, normalized_query, searches, zero_result_searches, clicks, add_to_carts, orders)
           SELECT %s, %s, s.query, count(*), count(*) FILTER (WHERE s.result_count = 0),
                  count(*) FILTER (WHERE EXISTS (
                    SELECT 1 FROM analytics_events e WHERE e.tenant_id = %s AND e.session_id = s.session_id
                      AND e.event_name = 'search_result_clicked' AND e.occurred_at >= s.occurred_at
                      AND lower(trim(COALESCE(e.properties->>'query', s.query))) = s.query)),
                  count(*) FILTER (WHERE EXISTS (
                    SELECT 1 FROM analytics_events e WHERE e.tenant_id = %s AND e.session_id = s.session_id
                      AND e.event_name = 'item_added_to_cart' AND e.occurred_at >= s.occurred_at)),
                  count(*) FILTER (WHERE EXISTS (
                    SELECT 1 FROM analytics_events e WHERE e.tenant_id = %s AND e.session_id = s.session_id
                      AND e.event_name = 'order_completed' AND e.occurred_at >= s.occurred_at))
           FROM searches s GROUP BY s.query""",
        (tenant_id, metric_date, tenant_id, metric_date, tenant_id, tenant_id, tenant_id),
    )

    cursor.execute("DELETE FROM daily_checkout_metrics WHERE tenant_id = %s AND metric_date = %s", (tenant_id, metric_date))
    cursor.execute(
        """INSERT INTO daily_checkout_metrics
           (tenant_id, metric_date, step, entered, completed, failures,
            delivery_area_rejections, minimum_order_blocks, coupon_failures, mobile_entered, mobile_completed)
           SELECT %s, %s, COALESCE(properties->>'step', 'CHECKOUT'),
                  count(*) FILTER (WHERE event_name IN ('checkout_started','checkout_step_viewed','payment_started')),
                  count(*) FILTER (WHERE event_name IN ('checkout_step_completed','order_created')),
                  count(*) FILTER (WHERE event_name = 'payment_failed'),
                  count(*) FILTER (WHERE event_name = 'delivery_area_checked' AND COALESCE((properties->>'available')::boolean, false) = false),
                  count(*) FILTER (WHERE event_name = 'minimum_order_blocked'),
                  count(*) FILTER (WHERE properties->>'failureType' = 'coupon'),
                  count(*) FILTER (WHERE properties->>'deviceClass' = 'mobile' AND event_name IN ('checkout_started','checkout_step_viewed','payment_started')),
                  count(*) FILTER (WHERE properties->>'deviceClass' = 'mobile' AND event_name IN ('checkout_step_completed','order_created'))
           FROM analytics_events
           WHERE tenant_id = %s AND occurred_at::date = %s
             AND event_name IN ('checkout_started','checkout_step_viewed','checkout_step_completed','delivery_area_checked','minimum_order_blocked','payment_started','payment_failed','order_created')
           GROUP BY COALESCE(properties->>'step', 'CHECKOUT')""",
        (tenant_id, metric_date, tenant_id, metric_date),
    )

    cursor.execute("DELETE FROM daily_source_metrics WHERE tenant_id = %s AND metric_date = %s", (tenant_id, metric_date))
    cursor.execute(
        """WITH sessions AS (
               SELECT session_id, min(visitor_id) AS visitor_id, min(occurred_at) AS first_seen,
                      COALESCE((array_agg(NULLIF(source, '') ORDER BY occurred_at) FILTER (WHERE source IS NOT NULL))[1], '(direct)') AS source,
                      COALESCE((array_agg(NULLIF(medium, '') ORDER BY occurred_at) FILTER (WHERE medium IS NOT NULL))[1], '(none)') AS medium,
                      COALESCE((array_agg(NULLIF(campaign, '') ORDER BY occurred_at) FILTER (WHERE campaign IS NOT NULL))[1], '') AS campaign,
                      bool_or(event_name = 'item_viewed') AS viewed_item,
                      bool_or(event_name IN ('cart_created','cart_viewed','item_added_to_cart')) AS reached_cart,
                      bool_or(event_name IN ('checkout_started','checkout_step_viewed')) AS reached_checkout
               FROM analytics_events WHERE tenant_id = %s AND occurred_at::date = %s GROUP BY session_id
           )
           INSERT INTO daily_source_metrics
             (tenant_id, metric_date, source, medium, campaign, sessions, new_visitors,
              returning_visitors, item_views, cart_sessions, checkout_sessions, orders,
              revenue_cents, contribution_margin_cents, repeat_customers)
           SELECT %s, %s, s.source, s.medium, s.campaign, count(DISTINCT s.session_id),
                  count(DISTINCT s.session_id) FILTER (WHERE NOT EXISTS (
                    SELECT 1 FROM analytics_events p WHERE p.tenant_id = %s AND p.visitor_id = s.visitor_id
                      AND p.occurred_at < s.first_seen)),
                  count(DISTINCT s.session_id) FILTER (WHERE EXISTS (
                    SELECT 1 FROM analytics_events p WHERE p.tenant_id = %s AND p.visitor_id = s.visitor_id
                      AND p.occurred_at < s.first_seen)),
                  count(*) FILTER (WHERE s.viewed_item), count(*) FILTER (WHERE s.reached_cart),
                  count(*) FILTER (WHERE s.reached_checkout),
                  count(DISTINCT o.id), COALESCE(sum(o.total_cents), 0),
                  CASE WHEN count(o.id) FILTER (WHERE o.contribution_margin_cents IS NULL) > 0
                       THEN NULL ELSE COALESCE(sum(o.contribution_margin_cents), 0) END,
                  count(DISTINCT o.user_id) FILTER (WHERE o.user_id IS NOT NULL AND EXISTS (
                    SELECT 1 FROM orders po WHERE po.restaurant_id = o.restaurant_id
                      AND po.user_id = o.user_id AND po.created_at < o.created_at AND po.status != 'cancelled'))
           FROM sessions s
           LEFT JOIN orders o ON o.restaurant_id = %s AND o.session_id = s.session_id
                             AND o.completed_at::date = %s AND o.status = 'delivered'
           GROUP BY s.source, s.medium, s.campaign""",
        (tenant_id, metric_date, tenant_id, metric_date, tenant_id, tenant_id, tenant_id, metric_date),
    )


def refresh_customer_metrics(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    metric_date = _target_date(metadata)

    cursor.execute(
        "DELETE FROM daily_customer_metrics WHERE tenant_id = %s AND metric_date = %s",
        (tenant_id, metric_date),
    )
    cursor.execute(
        """WITH today_orders AS (
               SELECT id, total_cents, completed_at,
                      CASE WHEN user_id IS NOT NULL THEN 'user:' || user_id
                           WHEN visitor_id IS NOT NULL THEN 'visitor:' || visitor_id END AS identity
               FROM orders
               WHERE restaurant_id = %s AND status = 'delivered' AND completed_at::date = %s
           ), classified AS (
               SELECT t.id, t.total_cents,
                      COALESCE(t.identity, 'order:' || t.id) AS identity_key,
                      CASE
                          WHEN t.identity IS NOT NULL AND EXISTS (
                              SELECT 1 FROM orders p
                              WHERE p.restaurant_id = %s AND p.status != 'cancelled'
                                AND p.status = 'delivered' AND p.completed_at < t.completed_at
                                AND (CASE WHEN p.user_id IS NOT NULL THEN 'user:' || p.user_id
                                          WHEN p.visitor_id IS NOT NULL THEN 'visitor:' || p.visitor_id END) = t.identity
                          ) THEN 'returning'
                          ELSE 'new'
                      END AS segment
               FROM today_orders t
           )
           INSERT INTO daily_customer_metrics (tenant_id, metric_date, segment, customers, orders, revenue_cents)
           SELECT %s, %s, segment, count(DISTINCT identity_key), count(*), COALESCE(sum(total_cents), 0)
           FROM classified GROUP BY segment""",
        (tenant_id, metric_date, tenant_id, tenant_id, metric_date),
    )


def refresh_basket_associations(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    window_days = max(7, int(os.getenv("BASKET_ASSOCIATION_WINDOW_DAYS", "90")))
    window_end = _target_date(metadata)
    window_start = window_end - timedelta(days=window_days)

    cursor.execute(
        "DELETE FROM basket_associations WHERE tenant_id = %s AND window_start = %s AND window_end = %s",
        (tenant_id, window_start, window_end),
    )
    cursor.execute(
        """WITH order_items AS (
               SELECT DISTINCT oi.order_id, oi.menu_item_id
               FROM order_line_items oi
               JOIN orders o ON o.id = oi.order_id AND o.restaurant_id = oi.tenant_id
               WHERE oi.tenant_id = %s AND oi.menu_item_id IS NOT NULL
                 AND o.completed_at::date BETWEEN %s AND %s AND o.status = 'delivered'
           ), pairs AS (
               SELECT a.order_id, a.menu_item_id AS item_a, b.menu_item_id AS item_b
               FROM order_items a
               JOIN order_items b ON a.order_id = b.order_id AND a.menu_item_id < b.menu_item_id
           ), pair_counts AS (
               SELECT item_a, item_b, count(*) AS pair_orders FROM pairs GROUP BY item_a, item_b
           ), item_counts AS (
               SELECT menu_item_id, count(DISTINCT order_id) AS item_orders FROM order_items GROUP BY menu_item_id
           ), total AS (
               SELECT count(DISTINCT order_id) AS total_orders FROM order_items
           )
           INSERT INTO basket_associations
             (tenant_id, window_start, window_end, item_a_id, item_b_id, pair_orders, support, confidence, reverse_confidence, lift)
           SELECT %s, %s, %s, pc.item_a, pc.item_b, pc.pair_orders,
                  pc.pair_orders::numeric / NULLIF(t.total_orders, 0),
                  pc.pair_orders::numeric / NULLIF(ia.item_orders, 0),
                  pc.pair_orders::numeric / NULLIF(ib.item_orders, 0),
                  (pc.pair_orders::numeric / NULLIF(ia.item_orders, 0))
                    / NULLIF(ib.item_orders::numeric / NULLIF(t.total_orders, 0), 0)
           FROM pair_counts pc
           JOIN item_counts ia ON ia.menu_item_id = pc.item_a
           JOIN item_counts ib ON ib.menu_item_id = pc.item_b
           CROSS JOIN total t
           ON CONFLICT (tenant_id, window_start, window_end, item_a_id, item_b_id) DO UPDATE SET
             pair_orders = EXCLUDED.pair_orders, support = EXCLUDED.support,
             confidence = EXCLUDED.confidence, reverse_confidence = EXCLUDED.reverse_confidence,
             lift = EXCLUDED.lift, updated_at = NOW()""",
        (tenant_id, window_start, window_end, tenant_id, window_start, window_end),
    )


def refresh_chat_metrics(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    metric_date = _target_date(metadata)

    cursor.execute(
        "DELETE FROM daily_chat_metrics WHERE tenant_id = %s AND metric_date = %s",
        (tenant_id, metric_date),
    )
    cursor.execute(
        """INSERT INTO daily_chat_metrics (tenant_id, metric_date, intent, messages, recommendations, clicks, orders)
           SELECT %s, %s, COALESCE(properties->>'intent', 'general'),
                  count(*) FILTER (WHERE event_name = 'chat_message_sent'),
                  count(*) FILTER (WHERE event_name = 'chat_recommendation_shown'),
                  count(*) FILTER (WHERE event_name = 'chat_recommendation_clicked'),
                  0  -- order attribution requires chat-to-order session linkage, added in a later phase
           FROM analytics_events
           WHERE tenant_id = %s AND occurred_at::date = %s
             AND event_name IN ('chat_message_sent', 'chat_recommendation_shown', 'chat_recommendation_clicked')
           GROUP BY COALESCE(properties->>'intent', 'general')""",
        (tenant_id, metric_date, tenant_id, metric_date),
    )


def aggregate_daily_full(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    aggregate_daily(cursor, tenant_id, metadata)
    refresh_customer_metrics(cursor, tenant_id, metadata)
    refresh_basket_associations(cursor, tenant_id, metadata)
    refresh_chat_metrics(cursor, tenant_id, metadata)
    refresh_menu_classifications(cursor, tenant_id, metadata)


def refresh_data_quality(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    checks: list[tuple[str, str, int, dict[str, Any]]] = []

    cursor.execute(
        """SELECT count(*) FROM orders o
           WHERE o.restaurant_id = %s AND o.status = 'delivered'
             AND o.completed_at >= NOW() - INTERVAL '30 days'
             AND NOT EXISTS (SELECT 1 FROM analytics_events e
                             WHERE e.tenant_id = o.restaurant_id AND e.order_id = o.id
                               AND e.event_name = 'order_completed')""",
        (tenant_id,),
    )
    missing_completed = int(cursor.fetchone()[0])
    checks.append(("missing_order_completed_events", "error" if missing_completed else "ok", missing_completed, {}))

    cursor.execute(
        "SELECT count(*) FROM menu_items WHERE restaurant_id = %s AND is_available = TRUE AND ingredient_cost_cents IS NULL",
        (tenant_id,),
    )
    missing_cost = int(cursor.fetchone()[0])
    checks.append(("missing_item_cost", "warning" if missing_cost else "ok", missing_cost, {}))

    cursor.execute(
        """SELECT count(*) FILTER (WHERE source IS NULL OR source = ''), count(*)
           FROM analytics_events WHERE tenant_id = %s AND occurred_at >= NOW() - INTERVAL '7 days'
             AND event_name = 'page_viewed'""",
        (tenant_id,),
    )
    unknown, total = cursor.fetchone()
    ratio = (int(unknown) / int(total)) if total else 0
    checks.append(("unknown_traffic_source", "warning" if total and ratio > 0.6 else "ok", int(unknown), {"total": int(total), "ratio": ratio}))

    cursor.execute(
        """SELECT count(*) FROM job_runs WHERE tenant_id = %s AND status = 'failed'
           AND updated_at >= NOW() - INTERVAL '24 hours'""",
        (tenant_id,),
    )
    failed_jobs = int(cursor.fetchone()[0])
    checks.append(("background_job_failures", "error" if failed_jobs else "ok", failed_jobs, {}))

    cursor.execute(
        """SELECT count(*) FROM orders WHERE restaurant_id = %s AND created_at >= NOW() - INTERVAL '7 days'
           AND (visitor_id IS NULL OR session_id IS NULL)""",
        (tenant_id,),
    )
    unlinked_orders = int(cursor.fetchone()[0])
    checks.append(("tracking_failures", "warning" if unlinked_orders else "ok", unlinked_orders, {}))

    cursor.execute(
        """SELECT count(*) FROM analytics_events e
           WHERE e.tenant_id = %s AND e.order_id IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.restaurant_id = e.tenant_id AND o.id = e.order_id)""",
        (tenant_id,),
    )
    event_order_mismatch = int(cursor.fetchone()[0])
    checks.append(("event_order_mismatch", "error" if event_order_mismatch else "ok", event_order_mismatch, {}))

    cursor.execute(
        """SELECT count(*) FROM (
               SELECT event_id FROM analytics_events WHERE tenant_id = %s
               GROUP BY event_id HAVING count(*) > 1
           ) duplicates""",
        (tenant_id,),
    )
    duplicate_events = int(cursor.fetchone()[0])
    checks.append(("duplicate_events", "error" if duplicate_events else "ok", duplicate_events, {}))

    cursor.execute(
        """SELECT count(*) FROM customers c WHERE c.tenant_id = %s
           AND NOT EXISTS (SELECT 1 FROM customer_consents cc
                           WHERE cc.tenant_id = c.tenant_id AND cc.customer_id = c.id)""",
        (tenant_id,),
    )
    missing_consent = int(cursor.fetchone()[0])
    checks.append(("missing_consent", "warning" if missing_consent else "ok", missing_consent, {}))

    cursor.execute(
        """SELECT count(*) FROM analytics_events
           WHERE tenant_id = %s AND event_name IN ('item_impression','item_viewed','item_added_to_cart')
             AND item_id IS NULL AND occurred_at >= NOW() - INTERVAL '7 days'""",
        (tenant_id,),
    )
    unlinked_items = int(cursor.fetchone()[0])
    checks.append(("unlinked_menu_items", "warning" if unlinked_items else "ok", unlinked_items, {}))

    cursor.execute(
        """SELECT count(*) FROM menu_items m JOIN restaurants r ON r.id = m.restaurant_id
           WHERE m.restaurant_id = %s AND upper(m.currency) != upper(r.currency)""",
        (tenant_id,),
    )
    currency_mismatch = int(cursor.fetchone()[0])
    checks.append(("currency_mismatch", "error" if currency_mismatch else "ok", currency_mismatch, {}))

    cursor.execute(
        """SELECT count(*) FROM restaurants r WHERE r.id = %s
           AND NOT EXISTS (SELECT 1 FROM pg_timezone_names p WHERE p.name = r.timezone)""",
        (tenant_id,),
    )
    timezone_mismatch = int(cursor.fetchone()[0])
    checks.append(("timezone_mismatch", "error" if timezone_mismatch else "ok", timezone_mismatch, {}))

    cursor.execute(
        """SELECT (SELECT count(*) FROM menu_items WHERE restaurant_id = %s AND is_available = TRUE)
                + (SELECT count(*) FROM faqs WHERE restaurant_id = %s)""",
        (tenant_id, tenant_id),
    )
    knowledge_rows = int(cursor.fetchone()[0])
    checks.append(("missing_chatbot_knowledge", "warning" if knowledge_rows == 0 else "ok", 1 if knowledge_rows == 0 else 0, {"knowledgeRows": knowledge_rows}))

    cursor.execute(
        """SELECT count(*),
                  count(*) FILTER (WHERE verified_at IS NULL OR verified_at < NOW() - INTERVAL '90 days')
           FROM competitors WHERE tenant_id = %s AND status = 'active'""",
        (tenant_id,),
    )
    total_competitors, stale_competitors = (int(v) for v in cursor.fetchone())
    checks.append((
        "stale_competitor_data",
        "warning" if total_competitors == 0 or stale_competitors > 0 else "ok",
        stale_competitors,
        {"configured": total_competitors > 0, "totalCompetitors": total_competitors},
    ))

    cursor.execute(
        """SELECT count(*) FROM experiments e WHERE e.tenant_id=%s AND e.status='RUNNING'
           AND NOT EXISTS (
               SELECT 1 FROM experiment_results er WHERE er.tenant_id=e.tenant_id
                 AND er.experiment_id=e.id AND er.evaluated_at>=NOW()-INTERVAL '24 hours'
           )""",
        (tenant_id,),
    )
    stale_experiments = int(cursor.fetchone()[0])
    checks.append(("experiment_evaluation", "warning" if stale_experiments else "ok", stale_experiments, {}))

    cursor.execute(
        """SELECT count(*) FROM mission_guardrails mg JOIN missions m ON m.id=mg.mission_id AND m.tenant_id=mg.tenant_id
           WHERE mg.tenant_id=%s AND m.status='RUNNING' AND mg.status='breached'""",
        (tenant_id,),
    )
    breached_guardrails = int(cursor.fetchone()[0])
    checks.append(("mission_guardrails", "error" if breached_guardrails else "ok", breached_guardrails, {}))

    cursor.execute(
        """SELECT count(*) FROM campaign_messages cm WHERE cm.tenant_id=%s AND cm.status IN ('SENT','DELIVERED','CLICKED')
           AND NOT EXISTS (
               SELECT 1 FROM customer_consents cc WHERE cc.tenant_id=cm.tenant_id
                 AND cc.customer_id=cm.customer_id AND cc.channel=cm.channel AND cc.status='granted'
           )""",
        (tenant_id,),
    )
    consent_violations = int(cursor.fetchone()[0])
    checks.append(("mission_consent_enforcement", "error" if consent_violations else "ok", consent_violations, {}))

    for key, status, affected_count, details in checks:
        import json
        cursor.execute(
            """INSERT INTO data_quality_checks (tenant_id, check_key, status, affected_count, details, checked_at)
               VALUES (%s,%s,%s,%s,%s::jsonb,NOW())
               ON CONFLICT (tenant_id, check_key) DO UPDATE SET
                 status = EXCLUDED.status, affected_count = EXCLUDED.affected_count,
                 details = EXCLUDED.details, checked_at = NOW()""",
            (tenant_id, key, status, affected_count, json.dumps(details)),
        )


def expire_raw_events(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    retention_days = max(30, int(os.getenv("RAW_EVENT_RETENTION_DAYS", "400")))
    cursor.execute(
        "DELETE FROM analytics_events WHERE tenant_id = %s AND occurred_at < NOW() - (%s * INTERVAL '1 day')",
        (tenant_id, retention_days),
    )
    chat_retention_days = max(1, int(os.getenv("CHAT_CONTENT_RETENTION_DAYS", "90")))
    cursor.execute(
        "DELETE FROM chat_sessions WHERE restaurant_id = %s AND updated_at < NOW() - (%s * INTERVAL '1 day')",
        (tenant_id, chat_retention_days),
    )
    # Rate-limit windows accrue ~1 row per tenant per minute. Only the current
    # minute is ever read, so prune anything older than an hour to keep these
    # tables and their indexes from growing without bound.
    cursor.execute(
        "DELETE FROM event_ingestion_windows WHERE tenant_id = %s AND window_start < NOW() - INTERVAL '1 hour'",
        (tenant_id,),
    )
    cursor.execute(
        "DELETE FROM intervention_request_windows WHERE tenant_id = %s AND window_start < NOW() - INTERVAL '1 hour'",
        (tenant_id,),
    )


def evaluate_abandoned_carts(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    threshold_minutes = max(10, int(os.getenv("ABANDONED_CART_MINUTES", "30")))
    cursor.execute(
        """UPDATE carts SET status = 'abandoned', updated_at = NOW()
           WHERE tenant_id = %s AND status = 'active'
             AND updated_at < NOW() - (%s * INTERVAL '1 minute')
           RETURNING id, visitor_id, session_id, customer_id, subtotal_cents, currency""",
        (tenant_id, threshold_minutes),
    )
    for cart_id, visitor_id, session_id, customer_id, subtotal_cents, currency in cursor.fetchall():
        emit_server_event(
            cursor,
            tenant_id=tenant_id,
            event_id=f"cart-abandoned:{cart_id}",
            event_name="cart_abandoned_candidate",
            visitor_id=visitor_id,
            session_id=session_id,
            customer_id=customer_id,
            cart_id=cart_id,
            properties={"subtotalCents": int(subtotal_cents or 0), "currency": currency},
            consent_state="essential",
        )


JOB_HANDLERS: dict[str, Callable] = {
    "analytics.aggregate_hourly": aggregate_daily,
    "analytics.aggregate_daily": aggregate_daily_full,
    "analytics.refresh_item_metrics": aggregate_daily,
    "analytics.refresh_checkout_metrics": aggregate_daily,
    "analytics.refresh_source_metrics": aggregate_daily,
    "analytics.refresh_search_metrics": aggregate_daily,
    "analytics.refresh_chat_metrics": refresh_chat_metrics,
    "analytics.refresh_customer_metrics": refresh_customer_metrics,
    "analytics.refresh_basket_associations": refresh_basket_associations,
    "analytics.refresh_menu_matrix": refresh_menu_classifications,
    "opportunities.detect_daily": detect_opportunities,
    "opportunities.generate_weekly_cards": generate_weekly_cards,
    "data_quality.refresh": refresh_data_quality,
    "privacy.expire_old_raw_events": expire_raw_events,
    "experiments.evaluate": evaluate_experiments,
    "customers.refresh_segments": refresh_customer_profiles,
    "missions.evaluate_abandoned_carts": evaluate_mission_abandoned_carts,
    "missions.evaluate_bundles": evaluate_bundles,
    "missions.evaluate_lapsed_customers": evaluate_lapsed_customers,
    "missions.evaluate_quiet_hours": evaluate_quiet_hours,
    "missions.evaluate_product_demand_tests": evaluate_product_demand_tests,
    "missions.monitor_running": monitor_running_missions,
    "conversion.refresh_demand_twin": refresh_tenant_demand_twin,
    "network.refresh_benchmarks": refresh_neighborhood_benchmarks,
    "platform.performance_review": refresh_performance_review,
}
