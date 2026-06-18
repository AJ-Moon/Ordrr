import json
import math
import os
from datetime import date, timedelta
from typing import Any


DETECTOR_VERSION = "menu-matrix-v1"


def classify_item(
    *,
    impressions: int,
    detail_sessions: int,
    purchase_count: int,
    category_attention: float,
    category_conversion: float,
    minimum_sample: int,
) -> tuple[str, float, float, float]:
    attention = detail_sessions / impressions if impressions else 0.0
    conversion = purchase_count / detail_sessions if detail_sessions else 0.0
    if detail_sessions < minimum_sample or impressions < minimum_sample:
        return "INSUFFICIENT_DATA", attention, conversion, 0.0
    attention_high = attention >= category_attention
    conversion_high = conversion >= category_conversion
    classification = {
        (True, True): "HERO",
        (True, False): "LEAKING",
        (False, True): "HIDDEN_WINNER",
        (False, False): "WEAK",
    }[(attention_high, conversion_high)]
    confidence = min(100.0, 35.0 + 15.0 * math.log10(max(detail_sessions, 1)))
    return classification, attention, conversion, round(confidence, 2)


def refresh_menu_classifications(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    period_end = date.fromisoformat(str(metadata["date"])) if metadata.get("date") else date.today()
    window_days = max(7, min(180, int(os.getenv("MENU_MATRIX_WINDOW_DAYS", "30"))))
    minimum_sample = max(5, int(os.getenv("MENU_MATRIX_MINIMUM_SAMPLE", "20")))
    period_start = period_end - timedelta(days=window_days - 1)
    cursor.execute(
        """SELECT m.id, COALESCE(NULLIF(m.category, ''), 'Uncategorized'),
                  COALESCE(sum(d.impressions), 0), COALESCE(sum(d.unique_detail_view_sessions), 0),
                  COALESCE(sum(d.purchase_count), 0), COALESCE(sum(d.revenue_cents), 0)
           FROM menu_items m
           LEFT JOIN daily_item_metrics d ON d.tenant_id = m.restaurant_id AND d.item_id = m.id
             AND d.location_id = 0 AND d.metric_date BETWEEN %s AND %s
           WHERE m.restaurant_id = %s
           GROUP BY m.id, COALESCE(NULLIF(m.category, ''), 'Uncategorized')""",
        (period_start, period_end, tenant_id),
    )
    rows = cursor.fetchall()
    by_category: dict[str, list[tuple]] = {}
    for row in rows:
        by_category.setdefault(row[1], []).append(row)
    total_impressions = sum(int(row[2]) for row in rows)
    total_details = sum(int(row[3]) for row in rows)
    total_purchases = sum(int(row[4]) for row in rows)
    tenant_attention = total_details / total_impressions if total_impressions else 0.0
    tenant_conversion = total_purchases / total_details if total_details else 0.0

    for item_id, category, impressions, detail_sessions, purchases, revenue_cents in rows:
        category_rows = by_category[category]
        cat_impressions = sum(int(row[2]) for row in category_rows)
        cat_details = sum(int(row[3]) for row in category_rows)
        cat_purchases = sum(int(row[4]) for row in category_rows)
        category_attention = cat_details / cat_impressions if cat_impressions else tenant_attention
        category_conversion = cat_purchases / cat_details if cat_details else tenant_conversion
        classification, attention, conversion, confidence = classify_item(
            impressions=int(impressions),
            detail_sessions=int(detail_sessions),
            purchase_count=int(purchases),
            category_attention=category_attention,
            category_conversion=category_conversion,
            minimum_sample=minimum_sample,
        )
        metrics = {
            "impressions": int(impressions),
            "uniqueDetailViewSessions": int(detail_sessions),
            "purchaseCount": int(purchases),
            "revenueCents": int(revenue_cents),
            "minimumSample": minimum_sample,
        }
        cursor.execute(
            """INSERT INTO menu_item_classifications
               (tenant_id, item_id, period_start, period_end, classification, attention_rate,
                conversion_rate, category_attention_baseline, category_conversion_baseline,
                tenant_attention_baseline, tenant_conversion_baseline, sample_size,
                confidence_score, metrics, detector_version)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
               ON CONFLICT (tenant_id, item_id, period_start, period_end) DO UPDATE SET
                 classification = EXCLUDED.classification, attention_rate = EXCLUDED.attention_rate,
                 conversion_rate = EXCLUDED.conversion_rate,
                 category_attention_baseline = EXCLUDED.category_attention_baseline,
                 category_conversion_baseline = EXCLUDED.category_conversion_baseline,
                 tenant_attention_baseline = EXCLUDED.tenant_attention_baseline,
                 tenant_conversion_baseline = EXCLUDED.tenant_conversion_baseline,
                 sample_size = EXCLUDED.sample_size, confidence_score = EXCLUDED.confidence_score,
                 metrics = EXCLUDED.metrics, detector_version = EXCLUDED.detector_version, updated_at = NOW()""",
            (
                tenant_id, item_id, period_start, period_end, classification, attention, conversion,
                category_attention, category_conversion, tenant_attention, tenant_conversion,
                int(detail_sessions), confidence, json.dumps(metrics), DETECTOR_VERSION,
            ),
        )
