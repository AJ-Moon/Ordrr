import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional

from services.ai import get_ai_provider


DETECTOR_VERSION = "opportunity-v1"
ACTIVE_STATUSES = ("DETECTED", "NEEDS_REVIEW", "RECOMMENDED", "APPROVED")


def clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def priority_score(impact: float, confidence: float, effort: float, urgency: float) -> float:
    return clamp_score(impact * 0.35 + confidence * 0.30 + (100 - effort) * 0.15 + urgency * 0.20)


@dataclass(frozen=True)
class OpportunityCandidate:
    type: str
    entity_type: str
    entity_id: Optional[str]
    headline: str
    summary: str
    impact_score: float
    confidence_score: float
    effort_score: float
    urgency_score: float
    evidence: dict[str, Any]
    recommended_action: dict[str, Any]
    estimated_revenue_impact_cents: Optional[int] = None
    estimated_margin_impact_cents: Optional[int] = None
    location_id: Optional[int] = None

    @property
    def priority(self) -> float:
        return priority_score(self.impact_score, self.confidence_score, self.effort_score, self.urgency_score)

    @property
    def fingerprint(self) -> str:
        raw = f"{DETECTOR_VERSION}|{self.type}|{self.entity_type}|{self.entity_id or ''}|{self.location_id or 0}"
        return hashlib.sha256(raw.encode()).hexdigest()


def item_candidates(rows: list[tuple], quality_multiplier: float) -> list[OpportunityCandidate]:
    candidates = []
    for item_id, name, classification, confidence, metrics in rows:
        if classification not in {"LEAKING", "HIDDEN_WINNER", "WEAK"}:
            continue
        opportunity_type = {
            "LEAKING": "HIGH_ATTENTION_LOW_CONVERSION",
            "HIDDEN_WINNER": "HIDDEN_WINNER",
            "WEAK": "WEAK_ITEM",
        }[classification]
        revenue = int((metrics or {}).get("revenueCents", 0))
        impact = 75 if classification == "LEAKING" else 60 if classification == "HIDDEN_WINNER" else 35
        action = {
            "LEAKING": "Review product presentation, modifiers, price communication, and availability before testing one change.",
            "HIDDEN_WINNER": "Increase qualified visibility with a controlled placement or merchandising experiment.",
            "WEAK": "Review whether the item should be repositioned, revised, or retired after operational checks.",
        }[classification]
        candidates.append(OpportunityCandidate(
            type=opportunity_type, entity_type="menu_item", entity_id=str(item_id),
            headline=f"{name}: {classification.replace('_', ' ').title()}",
            summary=f"The persisted menu matrix classified {name} as {classification} for the current evidence window.",
            impact_score=impact, confidence_score=float(confidence) * quality_multiplier,
            effort_score=45, urgency_score=65 if classification == "LEAKING" else 45,
            evidence={"classification": classification, "metrics": metrics or {}},
            recommended_action={"type": "human_review", "description": action},
            estimated_revenue_impact_cents=max(0, int(revenue * 0.10)) if revenue else None,
        ))
    return candidates


def search_candidates(rows: list[tuple], quality_multiplier: float) -> list[OpportunityCandidate]:
    candidates = []
    for query, searches, zero_results, clicks, carts, orders in rows:
        searches = int(searches)
        zero_results = int(zero_results)
        if searches < 10:
            continue
        zero_rate = zero_results / searches
        if zero_rate < 0.40:
            continue
        candidates.append(OpportunityCandidate(
            type="SEARCH_NO_RESULT", entity_type="search_query", entity_id=str(query),
            headline=f"Customers cannot find “{query}”",
            summary=f"{zero_results} of {searches} searches returned no results.",
            impact_score=clamp_score(40 + zero_rate * 45), confidence_score=clamp_score(min(90, 40 + math.log10(searches) * 20) * quality_multiplier),
            effort_score=30, urgency_score=60,
            evidence={"query": query, "searches": searches, "zeroResultSearches": zero_results, "zeroResultRate": zero_rate, "clicks": int(clicks), "addToCarts": int(carts), "orders": int(orders)},
            recommended_action={"type": "human_review", "description": "Review menu aliases, FAQs, and genuine product demand before changing the catalog."},
        ))
    return candidates


def checkout_candidates(rows: list[tuple], quality_multiplier: float) -> list[OpportunityCandidate]:
    candidates = []
    for step, entered, completed, failures, area_rejections, minimum_blocks in rows:
        entered, completed, failures = int(entered), int(completed), int(failures)
        if entered < 20:
            continue
        drop_rate = max(0.0, 1 - completed / entered)
        if failures >= 5 and failures / entered >= 0.10:
            candidates.append(OpportunityCandidate(
                type="PAYMENT_FAILURE", entity_type="checkout_step", entity_id=str(step),
                headline=f"Payment failures at {step}", summary=f"{failures} failures occurred across {entered} entrants.",
                impact_score=75, confidence_score=clamp_score(70 * quality_multiplier), effort_score=55, urgency_score=85,
                evidence={"step": step, "entered": entered, "completed": completed, "failures": failures, "failureRate": failures / entered},
                recommended_action={"type": "technical_review", "description": "Review provider errors and payment-method availability before changing checkout."},
            ))
        if int(minimum_blocks) >= 5:
            candidates.append(OpportunityCandidate(
                type="MINIMUM_ORDER_FRICTION", entity_type="checkout_step", entity_id=str(step),
                headline="Minimum order is blocking checkout", summary=f"{int(minimum_blocks)} minimum-order blocks were recorded.",
                impact_score=65, confidence_score=clamp_score(65 * quality_multiplier), effort_score=40, urgency_score=65,
                evidence={"step": step, "minimumOrderBlocks": int(minimum_blocks), "entered": entered},
                recommended_action={"type": "human_review", "description": "Review threshold communication and non-discount basket-building options."},
            ))
        if drop_rate >= 0.35:
            candidates.append(OpportunityCandidate(
                type="CHECKOUT_DROP", entity_type="checkout_step", entity_id=str(step),
                headline=f"High checkout drop-off at {step}", summary=f"The observed drop-off rate is {drop_rate:.1%} across {entered} entrants.",
                impact_score=clamp_score(45 + drop_rate * 45), confidence_score=clamp_score(70 * quality_multiplier), effort_score=50, urgency_score=70,
                evidence={"step": step, "entered": entered, "completed": completed, "dropOffRate": drop_rate, "deliveryAreaRejections": int(area_rejections)},
                recommended_action={"type": "funnel_review", "description": "Inspect the step by device and source, then test one verified friction reduction."},
            ))
    return candidates


def basket_candidates(rows: list[tuple], quality_multiplier: float) -> list[OpportunityCandidate]:
    candidates = []
    for item_a, name_a, item_b, name_b, pair_orders, support, confidence, reverse_confidence, lift in rows:
        pair_orders = int(pair_orders)
        lift_value = float(lift or 0)
        if pair_orders < 5 or lift_value < 1.20:
            continue
        candidates.append(OpportunityCandidate(
            type="BUNDLE_OPPORTUNITY", entity_type="item_pair", entity_id=f"{item_a}:{item_b}",
            headline=f"Bundle candidate: {name_a} + {name_b}",
            summary=f"The pair appeared in {pair_orders} completed orders with lift {lift_value:.2f}.",
            impact_score=clamp_score(45 + min(35, pair_orders)), confidence_score=clamp_score(min(90, 45 + pair_orders * 2) * quality_multiplier),
            effort_score=55, urgency_score=40,
            evidence={"itemAId": item_a, "itemAName": name_a, "itemBId": item_b, "itemBName": name_b,
                      "pairOrders": pair_orders, "support": float(support or 0), "confidence": float(confidence or 0),
                      "reverseConfidence": float(reverse_confidence or 0), "lift": lift_value},
            recommended_action={"type": "human_review", "description": "Review margin and cannibalization, then test an approved bundle rather than publishing automatically."},
        ))
    return candidates


def campaign_candidates(rows: list[tuple], baseline: float, quality_multiplier: float) -> list[OpportunityCandidate]:
    candidates = []
    for source, medium, campaign, sessions, orders, revenue_cents in rows:
        sessions, orders = int(sessions), int(orders)
        conversion = orders / sessions if sessions else 0
        if not campaign or sessions < 30 or baseline <= 0 or conversion >= baseline * 0.50:
            continue
        candidates.append(OpportunityCandidate(
            type="CAMPAIGN_MISMATCH", entity_type="campaign", entity_id=f"{source}:{medium}:{campaign}",
            headline=f"Campaign underperformance: {campaign}",
            summary=f"The campaign converted at {conversion:.1%} versus a tenant baseline of {baseline:.1%}.",
            impact_score=60, confidence_score=clamp_score(65 * quality_multiplier), effort_score=45, urgency_score=60,
            evidence={"source": source, "medium": medium, "campaign": campaign, "sessions": sessions,
                      "orders": orders, "conversionRate": conversion, "tenantConversionBaseline": baseline,
                      "revenueCents": int(revenue_cents)},
            recommended_action={"type": "campaign_review", "description": "Verify landing-page, advertised product, price, availability, branch, and delivery-area consistency."},
        ))
    return candidates


def chat_candidates(rows: list[tuple], quality_multiplier: float) -> list[OpportunityCandidate]:
    candidates = []
    for intent, messages, recommendations, clicks, orders in rows:
        messages = int(messages)
        if messages < 10 or str(intent).lower() in {"general", "other"}:
            continue
        candidates.append(OpportunityCandidate(
            type="CHAT_OBJECTION", entity_type="chat_intent", entity_id=str(intent),
            headline=f"Repeated chat objection: {str(intent).replace('_', ' ').title()}",
            summary=f"The intent appeared in {messages} tracked chat messages.",
            impact_score=50, confidence_score=clamp_score(min(85, 45 + messages) * quality_multiplier), effort_score=35, urgency_score=45,
            evidence={"intent": intent, "messages": messages, "recommendations": int(recommendations), "clicks": int(clicks), "orders": int(orders)},
            recommended_action={"type": "content_review", "description": "Review the conversations and improve verified menu, FAQ, or operational information without inventing claims."},
        ))
    return candidates


def competitor_candidates(rows: list[tuple], quality_multiplier: float) -> list[OpportunityCandidate]:
    candidates = []
    for comparison_id, item_id, item_name, product_name, price_index, match_quality in rows:
        index = float(price_index or 0)
        quality = float(match_quality or 0)
        if quality < 70 or index < 110:
            continue
        candidates.append(OpportunityCandidate(
            type="COMPETITOR_PRICE_GAP", entity_type="product_comparison", entity_id=str(comparison_id),
            headline=f"Verified price gap for {item_name}",
            summary=f"The approved normalized price index versus {product_name} is {index:.1f}.",
            impact_score=55, confidence_score=clamp_score(quality * quality_multiplier), effort_score=60, urgency_score=45,
            evidence={"comparisonId": comparison_id, "ownItemId": item_id, "ownItemName": item_name,
                      "competitorProductName": product_name, "priceIndex": index, "matchQuality": quality},
            recommended_action={"type": "human_review", "description": "Review portion, quality, positioning, costs, and margin before considering any pricing or value test."},
        ))
    return candidates


def _quality_multiplier(cursor, tenant_id: int) -> float:
    cursor.execute("SELECT status FROM data_quality_checks WHERE tenant_id = %s", (tenant_id,))
    statuses = [row[0] for row in cursor.fetchall()]
    if "error" in statuses:
        return 0.60
    if "warning" in statuses:
        return 0.85
    return 1.0


def detect_opportunities(cursor, tenant_id: int, metadata: dict[str, Any]) -> list[int]:
    period_end = date.fromisoformat(str(metadata["date"])) if metadata.get("date") else date.today()
    window_days = max(7, min(180, int(os.getenv("OPPORTUNITY_WINDOW_DAYS", "30"))))
    period_start = period_end - timedelta(days=window_days - 1)
    quality = _quality_multiplier(cursor, tenant_id)
    cursor.execute(
        """SELECT c.item_id, m.name, c.classification, c.confidence_score, c.metrics
           FROM menu_item_classifications c JOIN menu_items m ON m.id = c.item_id AND m.restaurant_id = c.tenant_id
           WHERE c.tenant_id = %s AND c.period_end = (SELECT max(period_end) FROM menu_item_classifications WHERE tenant_id = %s)""",
        (tenant_id, tenant_id),
    )
    candidates = item_candidates(cursor.fetchall(), quality)
    cursor.execute(
        """SELECT normalized_query, sum(searches), sum(zero_result_searches), sum(clicks), sum(add_to_carts), sum(orders)
           FROM daily_search_metrics WHERE tenant_id = %s AND metric_date BETWEEN %s AND %s
           GROUP BY normalized_query""",
        (tenant_id, period_start, period_end),
    )
    candidates.extend(search_candidates(cursor.fetchall(), quality))
    cursor.execute(
        """SELECT step, sum(entered), sum(completed), sum(failures), sum(delivery_area_rejections), sum(minimum_order_blocks)
           FROM daily_checkout_metrics WHERE tenant_id = %s AND metric_date BETWEEN %s AND %s GROUP BY step""",
        (tenant_id, period_start, period_end),
    )
    candidates.extend(checkout_candidates(cursor.fetchall(), quality))
    cursor.execute(
        """SELECT ba.item_a_id, ma.name, ba.item_b_id, mb.name, ba.pair_orders, ba.support,
                  ba.confidence, ba.reverse_confidence, ba.lift
           FROM basket_associations ba JOIN menu_items ma ON ma.id = ba.item_a_id AND ma.restaurant_id = ba.tenant_id
           JOIN menu_items mb ON mb.id = ba.item_b_id AND mb.restaurant_id = ba.tenant_id
           WHERE ba.tenant_id = %s AND ba.window_end = (SELECT max(window_end) FROM basket_associations WHERE tenant_id = %s)""",
        (tenant_id, tenant_id),
    )
    candidates.extend(basket_candidates(cursor.fetchall(), quality))
    cursor.execute(
        """SELECT source, medium, campaign, sum(sessions), sum(orders), sum(revenue_cents)
           FROM daily_source_metrics WHERE tenant_id = %s AND metric_date BETWEEN %s AND %s
           GROUP BY source, medium, campaign""",
        (tenant_id, period_start, period_end),
    )
    source_rows = cursor.fetchall()
    total_sessions = sum(int(row[3]) for row in source_rows)
    total_orders = sum(int(row[4]) for row in source_rows)
    candidates.extend(campaign_candidates(source_rows, total_orders / total_sessions if total_sessions else 0, quality))
    cursor.execute(
        """SELECT intent, sum(messages), sum(recommendations), sum(clicks), sum(orders)
           FROM daily_chat_metrics WHERE tenant_id = %s AND metric_date BETWEEN %s AND %s GROUP BY intent""",
        (tenant_id, period_start, period_end),
    )
    candidates.extend(chat_candidates(cursor.fetchall(), quality))
    cursor.execute(
        """SELECT pc.id, pc.own_item_id, m.name, cp.name, pc.price_index, pc.match_quality
           FROM product_comparisons pc JOIN menu_items m ON m.id = pc.own_item_id AND m.restaurant_id = pc.tenant_id
           JOIN competitor_products cp ON cp.id = pc.competitor_product_id AND cp.tenant_id = pc.tenant_id
           WHERE pc.tenant_id = %s AND pc.approved_by_human = true""",
        (tenant_id,),
    )
    candidates.extend(competitor_candidates(cursor.fetchall(), quality))
    max_candidates = max(1, min(100, int(os.getenv("OPPORTUNITY_MAX_DETECTED", "50"))))
    candidates = sorted(candidates, key=lambda item: item.priority, reverse=True)[:max_candidates]
    ids: list[int] = []
    fingerprints: list[str] = []
    for candidate in candidates:
        fingerprints.append(candidate.fingerprint)
        cursor.execute("SELECT id, priority_score, status FROM opportunities WHERE tenant_id = %s AND fingerprint = %s", (tenant_id, candidate.fingerprint))
        existing = cursor.fetchone()
        trend = "new"
        if existing:
            delta = candidate.priority - float(existing[1])
            trend = "worsening" if delta >= 5 else "improving" if delta <= -5 else "unchanged"
        cursor.execute(
            """INSERT INTO opportunities
               (tenant_id, location_id, type, entity_type, entity_id, period_start, period_end,
                headline, summary, estimated_revenue_impact_cents, estimated_margin_impact_cents,
                impact_score, confidence_score, effort_score, urgency_score, priority_score,
                evidence_json, recommended_action_json, detector_version, fingerprint, trend, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,'RECOMMENDED')
               ON CONFLICT (tenant_id, fingerprint) DO UPDATE SET
                 period_start = EXCLUDED.period_start, period_end = EXCLUDED.period_end,
                 headline = EXCLUDED.headline, summary = EXCLUDED.summary,
                 estimated_revenue_impact_cents = EXCLUDED.estimated_revenue_impact_cents,
                 estimated_margin_impact_cents = EXCLUDED.estimated_margin_impact_cents,
                 impact_score = EXCLUDED.impact_score, confidence_score = EXCLUDED.confidence_score,
                 effort_score = EXCLUDED.effort_score, urgency_score = EXCLUDED.urgency_score,
                 priority_score = EXCLUDED.priority_score, evidence_json = EXCLUDED.evidence_json,
                 recommended_action_json = EXCLUDED.recommended_action_json, trend = EXCLUDED.trend,
                 last_detected_at = NOW(), updated_at = NOW(),
                 status = CASE WHEN opportunities.status IN ('DETECTED','NEEDS_REVIEW','RECOMMENDED')
                               THEN 'RECOMMENDED' ELSE opportunities.status END
               RETURNING id""",
            (
                tenant_id, candidate.location_id, candidate.type, candidate.entity_type, candidate.entity_id,
                period_start, period_end, candidate.headline, candidate.summary,
                candidate.estimated_revenue_impact_cents, candidate.estimated_margin_impact_cents,
                candidate.impact_score, candidate.confidence_score, candidate.effort_score,
                candidate.urgency_score, candidate.priority, json.dumps(candidate.evidence),
                json.dumps(candidate.recommended_action), DETECTOR_VERSION, candidate.fingerprint, trend,
            ),
        )
        opportunity_id = int(cursor.fetchone()[0])
        ids.append(opportunity_id)
        cursor.execute(
            """INSERT INTO opportunity_evidence
               (tenant_id, opportunity_id, evidence_key, value_json, source_table, period_start, period_end)
               VALUES (%s,%s,'detector_snapshot',%s::jsonb,'analytics_aggregates',%s,%s)
               ON CONFLICT (opportunity_id, evidence_key) DO UPDATE SET value_json = EXCLUDED.value_json,
                 period_start = EXCLUDED.period_start, period_end = EXCLUDED.period_end, created_at = NOW()""",
            (tenant_id, opportunity_id, json.dumps(candidate.evidence), period_start, period_end),
        )
    if fingerprints:
        cursor.execute(
            """UPDATE opportunities SET status = 'EXPIRED', updated_at = NOW()
               WHERE tenant_id = %s AND status IN ('DETECTED','NEEDS_REVIEW','RECOMMENDED')
                 AND NOT (fingerprint = ANY(%s))""",
            (tenant_id, fingerprints),
        )
    else:
        cursor.execute(
            "UPDATE opportunities SET status = 'EXPIRED', updated_at = NOW() WHERE tenant_id = %s AND status IN ('DETECTED','NEEDS_REVIEW','RECOMMENDED')",
            (tenant_id,),
        )
    return ids


def generate_weekly_cards(cursor, tenant_id: int, metadata: dict[str, Any]) -> None:
    detect_opportunities(cursor, tenant_id, metadata)
    limit = max(1, min(20, int(os.getenv("WEEKLY_OPPORTUNITY_CARD_LIMIT", "8"))))
    cursor.execute(
        """SELECT id, type, headline, summary, evidence_json, recommended_action_json,
                  impact_score, confidence_score, priority_score
           FROM opportunities WHERE tenant_id = %s AND status IN ('RECOMMENDED','NEEDS_REVIEW')
             AND ai_explanation_json IS NULL ORDER BY priority_score DESC LIMIT %s""",
        (tenant_id, limit),
    )
    provider = get_ai_provider()
    for row in cursor.fetchall():
        opportunity_id = int(row[0])
        evidence = {
            "type": row[1], "headline": row[2], "summary": row[3], "evidence": row[4],
            "recommendedAction": row[5], "impactScore": float(row[6]),
            "confidenceScore": float(row[7]), "priorityScore": float(row[8]),
        }
        result = provider.generate_opportunity_card(evidence)
        output = result.card.model_dump() if result.card else None
        cursor.execute(
            """INSERT INTO ai_generation_logs
               (tenant_id, opportunity_id, operation, provider, model, prompt_version,
                input_evidence_hash, output_json, validation_result, latency_ms,
                input_tokens, output_tokens, error)
               VALUES (%s,%s,'generate_opportunity_card',%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)""",
            (tenant_id, opportunity_id, result.provider, result.model, result.prompt_version,
             result.evidence_hash, json.dumps(output) if output else None, result.validation_result,
             result.latency_ms, result.input_tokens, result.output_tokens, result.error),
        )
        if output:
            cursor.execute("UPDATE opportunities SET ai_explanation_json = %s::jsonb, updated_at = NOW() WHERE id = %s AND tenant_id = %s", (json.dumps(output), opportunity_id, tenant_id))
