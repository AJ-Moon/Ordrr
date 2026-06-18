import hashlib
import json
import math
import os
from datetime import datetime, timezone
from statistics import NormalDist
from typing import Any, Optional

from fastapi import HTTPException

from services.events import emit_server_event


ACTIVE_EXPERIMENT_STATUSES = ("SCHEDULED", "RUNNING")


def stable_bucket(*parts: object, modulo: int = 10000) -> int:
    raw = "|".join(str(part) for part in parts)
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16], 16) % modulo


def choose_variant(experiment_id: int, visitor_id: str, variants: list[tuple[int, int]]) -> int:
    if not variants:
        raise ValueError("Experiment has no variants")
    total = sum(max(0, int(weight)) for _, weight in variants)
    if total <= 0:
        raise ValueError("Experiment variant weights must be positive")
    bucket = stable_bucket(experiment_id, visitor_id, modulo=total)
    running = 0
    for variant_id, weight in variants:
        running += max(0, int(weight))
        if bucket < running:
            return int(variant_id)
    return int(variants[-1][0])


def assign_variant(
    cursor,
    *,
    tenant_id: int,
    experiment_id: int,
    visitor_id: str,
    customer_id: Optional[str] = None,
    audience: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    cursor.execute(
        """SELECT id, status, allocation_percentage, conflict_key, audience_definition
           FROM experiments WHERE tenant_id = %s AND id = %s""",
        (tenant_id, experiment_id),
    )
    experiment = cursor.fetchone()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if experiment[1] != "RUNNING":
        return None
    allocation = int(experiment[2])
    if stable_bucket("allocation", experiment_id, visitor_id, modulo=100) >= allocation:
        return None

    cursor.execute(
        """SELECT a.id, v.id, v.variant_key, v.name, v.config, v.is_control
           FROM experiment_assignments a
           JOIN experiment_variants v ON v.id = a.variant_id AND v.tenant_id = a.tenant_id
           WHERE a.tenant_id = %s AND a.experiment_id = %s AND a.visitor_id = %s""",
        (tenant_id, experiment_id, visitor_id),
    )
    assigned = cursor.fetchone()
    if assigned:
        return _assignment_dict(assigned)

    cursor.execute(
        """SELECT 1 FROM experiment_assignments a
           JOIN experiments e ON e.id = a.experiment_id AND e.tenant_id = a.tenant_id
           WHERE a.tenant_id = %s AND a.visitor_id = %s AND e.conflict_key = %s
             AND e.id <> %s AND e.status IN ('SCHEDULED','RUNNING') LIMIT 1""",
        (tenant_id, visitor_id, experiment[3], experiment_id),
    )
    if cursor.fetchone():
        return None

    required = experiment[4] or {}
    observed = audience or {}
    for key, expected in required.items():
        if key in {"segments", "excludedSegments"}:
            continue
        if observed.get(key) != expected:
            return None

    cursor.execute(
        "SELECT id, weight FROM experiment_variants WHERE tenant_id = %s AND experiment_id = %s ORDER BY id",
        (tenant_id, experiment_id),
    )
    variants = [(int(row[0]), int(row[1])) for row in cursor.fetchall()]
    variant_id = choose_variant(experiment_id, visitor_id, variants)
    cursor.execute(
        """INSERT INTO experiment_assignments
           (tenant_id, experiment_id, variant_id, visitor_id, customer_id, audience_snapshot)
           VALUES (%s,%s,%s,%s,%s,%s::jsonb)
           ON CONFLICT (experiment_id, visitor_id) DO NOTHING
           RETURNING id""",
        (tenant_id, experiment_id, variant_id, visitor_id, customer_id, json.dumps(observed)),
    )
    row = cursor.fetchone()
    if not row:
        return assign_variant(
            cursor, tenant_id=tenant_id, experiment_id=experiment_id,
            visitor_id=visitor_id, customer_id=customer_id, audience=audience,
        )
    assignment_id = int(row[0])
    cursor.execute(
        "SELECT %s, id, variant_key, name, config, is_control FROM experiment_variants WHERE tenant_id = %s AND id = %s",
        (assignment_id, tenant_id, variant_id),
    )
    return _assignment_dict(cursor.fetchone())


def _assignment_dict(row: tuple) -> dict[str, Any]:
    return {
        "assignmentId": int(row[0]), "variantId": int(row[1]), "variantKey": row[2],
        "variantName": row[3], "config": row[4] or {}, "isControl": bool(row[5]),
    }


def record_exposure(
    cursor,
    *,
    tenant_id: int,
    experiment_id: int,
    assignment_id: int,
    variant_id: int,
    visitor_id: str,
    session_id: str,
    exposure_key: str,
    context: dict[str, Any],
) -> bool:
    cursor.execute(
        """SELECT 1 FROM experiment_assignments a
           JOIN experiments e ON e.id = a.experiment_id AND e.tenant_id = a.tenant_id
           WHERE a.tenant_id = %s AND a.id = %s AND a.experiment_id = %s
             AND a.variant_id = %s AND a.visitor_id = %s AND e.status = 'RUNNING'""",
        (tenant_id, assignment_id, experiment_id, variant_id, visitor_id),
    )
    if not cursor.fetchone():
        raise HTTPException(status_code=409, detail="Assignment is not active or does not match")
    now = datetime.now(timezone.utc)
    cursor.execute(
        """INSERT INTO experiment_exposures
           (tenant_id, experiment_id, variant_id, assignment_id, exposure_key,
            visitor_id, session_id, occurred_at, context)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
           ON CONFLICT (tenant_id, exposure_key) DO NOTHING RETURNING id""",
        (tenant_id, experiment_id, variant_id, assignment_id, exposure_key,
         visitor_id, session_id, now, json.dumps(context)),
    )
    inserted = cursor.fetchone() is not None
    if inserted:
        emit_server_event(
            cursor, tenant_id=tenant_id, event_name="experiment_exposure",
            event_id=f"experiment-exposure:{exposure_key}", visitor_id=visitor_id,
            session_id=session_id, experiment_id=str(experiment_id), variant_id=str(variant_id),
            properties={"assignmentId": assignment_id, **context}, consent_state="analytics_granted",
        )
    return inserted


def two_proportion_interval(success_a: int, total_a: int, success_b: int, total_b: int, confidence: float) -> tuple[float, float, float]:
    if total_a <= 0 or total_b <= 0:
        return 0.0, -1.0, 1.0
    rate_a = success_a / total_a
    rate_b = success_b / total_b
    difference = rate_b - rate_a
    z = NormalDist().inv_cdf(0.5 + confidence / 2)
    standard_error = math.sqrt(rate_a * (1 - rate_a) / total_a + rate_b * (1 - rate_b) / total_b)
    return difference, difference - z * standard_error, difference + z * standard_error


def evaluate_experiments(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    cursor.execute(
        """SELECT id, minimum_sample, confidence_level, primary_metric
           FROM experiments WHERE tenant_id = %s AND status IN ('RUNNING','PAUSED')""",
        (tenant_id,),
    )
    for experiment_id, minimum_sample, confidence_level, primary_metric in cursor.fetchall():
        cursor.execute(
            """INSERT INTO experiment_outcomes
               (tenant_id, experiment_id, variant_id, visitor_id, order_id, metric, value,
                revenue_cents, contribution_margin_cents, occurred_at, attribution_method)
               SELECT DISTINCT ON (o.id) %s, %s, x.variant_id, o.visitor_id, o.id, %s, 1,
                      COALESCE(o.total_cents,0), o.contribution_margin_cents,
                      COALESCE(o.completed_at,o.created_at), 'visitor_post_exposure'
               FROM orders o
               JOIN LATERAL (
                   SELECT ee.variant_id, min(ee.occurred_at) AS first_exposure
                   FROM experiment_exposures ee
                   WHERE ee.tenant_id = %s AND ee.experiment_id = %s
                     AND ee.visitor_id = o.visitor_id
                   GROUP BY ee.variant_id ORDER BY first_exposure LIMIT 1
               ) x ON x.first_exposure <= COALESCE(o.completed_at,o.created_at)
               WHERE o.restaurant_id = %s AND o.status = 'delivered'
               ON CONFLICT (experiment_id, metric, order_id) DO NOTHING
               RETURNING order_id, visitor_id, variant_id, revenue_cents""",
            (tenant_id, experiment_id, primary_metric, tenant_id, experiment_id, tenant_id),
        )
        for order_id, visitor_id, variant_id, revenue_cents in cursor.fetchall():
            emit_server_event(
                cursor, tenant_id=tenant_id, event_name="experiment_conversion",
                event_id=f"experiment-conversion:{experiment_id}:{order_id}", visitor_id=visitor_id,
                session_id="server", order_id=order_id, experiment_id=str(experiment_id),
                variant_id=str(variant_id), properties={"metric": primary_metric, "revenueCents": int(revenue_cents)},
                consent_state="essential",
            )
        cursor.execute(
            """SELECT v.id, v.variant_key, v.is_control,
                      count(DISTINCT ee.visitor_id) AS exposed,
                      count(DISTINCT eo.visitor_id) AS converted,
                      COALESCE(sum(eo.revenue_cents),0), COALESCE(sum(eo.contribution_margin_cents),0)
               FROM experiment_variants v
               LEFT JOIN experiment_exposures ee ON ee.variant_id = v.id AND ee.experiment_id = v.experiment_id
               LEFT JOIN experiment_outcomes eo ON eo.variant_id = v.id AND eo.experiment_id = v.experiment_id
               WHERE v.tenant_id = %s AND v.experiment_id = %s
               GROUP BY v.id, v.variant_key, v.is_control ORDER BY v.is_control DESC, v.id""",
            (tenant_id, experiment_id),
        )
        rows = cursor.fetchall()
        metrics = [{
            "variantId": int(r[0]), "variantKey": r[1], "isControl": bool(r[2]),
            "exposed": int(r[3]), "converted": int(r[4]),
            "conversionRate": int(r[4]) / int(r[3]) if int(r[3]) else 0,
            "revenueCents": int(r[5]), "contributionMarginCents": int(r[6]),
        } for r in rows]
        for item in metrics:
            cursor.execute(
                """WITH first_exposure AS (
                       SELECT visitor_id,min(occurred_at) AS exposed_at
                       FROM experiment_exposures
                       WHERE tenant_id=%s AND experiment_id=%s AND variant_id=%s
                       GROUP BY visitor_id
                   )
                   SELECT count(*) FILTER (WHERE o.status='cancelled'),
                          count(*) FILTER (WHERE o.status='delivered'),
                          COALESCE(sum(o.refund_cents) FILTER (WHERE o.status='delivered'),0),
                          COALESCE(sum(o.total_cents) FILTER (WHERE o.status='delivered'),0)
                   FROM first_exposure fe JOIN orders o ON o.restaurant_id=%s
                     AND o.visitor_id=fe.visitor_id AND o.created_at>=fe.exposed_at""",
                (tenant_id, experiment_id, item["variantId"], tenant_id),
            )
            cancelled, delivered, refunds, order_revenue = cursor.fetchone()
            total_orders = int(cancelled or 0) + int(delivered or 0)
            item["cancelledOrders"] = int(cancelled or 0)
            item["refundCents"] = int(refunds or 0)
            item["cancellationRate"] = int(cancelled or 0) / total_orders if total_orders else 0
            item["refundRate"] = int(refunds or 0) / int(order_revenue) if int(order_revenue or 0) else 0
        total_sample = sum(item["exposed"] for item in metrics)
        result = "INSUFFICIENT_DATA"
        winner_id = None
        method = "two_proportion_normal_approximation_bonferroni_ci"
        refund_limit = float(os.getenv("EXPERIMENT_MAX_REFUND_RATE", "0.10"))
        cancellation_limit = float(os.getenv("EXPERIMENT_MAX_CANCELLATION_RATE", "0.10"))
        guardrails = {
            "margin": "ok" if all(item["contributionMarginCents"] >= 0 for item in metrics) else "breached",
            "refundRate": "ok" if all(item["refundRate"] <= refund_limit for item in metrics) else "breached",
            "cancellationRate": "ok" if all(item["cancellationRate"] <= cancellation_limit for item in metrics) else "breached",
        }
        control = next((item for item in metrics if item["isControl"]), None)
        treatments = [item for item in metrics if not item["isControl"]]
        comparisons = []
        if control and treatments and all(item["exposed"] >= int(minimum_sample) for item in metrics):
            result = "INCONCLUSIVE"
            comparison_confidence = 1 - ((1 - float(confidence_level)) / len(treatments))
            for treatment in treatments:
                diff, low, high = two_proportion_interval(
                    control["converted"], control["exposed"], treatment["converted"],
                    treatment["exposed"], comparison_confidence,
                )
                comparisons.append({"variantId": treatment["variantId"], "difference": diff, "ciLow": low, "ciHigh": high, "adjustedConfidence": comparison_confidence})
                if low > 0 and all(value == "ok" for value in guardrails.values()):
                    result, winner_id = "WINNER", treatment["variantId"]
                    break
                if high < 0:
                    result = "LOSER"
        cursor.execute(
            """INSERT INTO experiment_results
               (tenant_id, experiment_id, result, winning_variant_id, method,
                confidence_level, sample_size, metrics, guardrail_status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)""",
            (tenant_id, experiment_id, result, winner_id, method, confidence_level,
             total_sample, json.dumps({"variants": metrics, "comparisons": comparisons}), json.dumps(guardrails)),
        )
