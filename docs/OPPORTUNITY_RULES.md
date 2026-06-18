# Opportunity Rules

Status: implemented in Phase 3 (`opportunity-v1`).

## Scoring and lifecycle

- Scores are clamped to `0..100`.
- `priority = impact * 0.35 + confidence * 0.30 + (100 - effort) * 0.15 + urgency * 0.20`.
- Current data-quality warnings multiply detector confidence by `0.85`; errors multiply it by `0.60`.
- A stable SHA-256 fingerprint over detector version, type, entity, and location deduplicates recurring findings.
- A priority change of at least `+5` is `worsening`, at most `-5` is `improving`, otherwise `unchanged`.
- Detection preserves `APPROVED`, `DISMISSED`, and other terminal decisions. Active findings absent from a later run become `EXPIRED`.

## Deterministic detectors

- Menu matrix: persisted `LEAKING`, `HIDDEN_WINNER`, and `WEAK` classifications.
- Search: at least 10 searches and at least 40% zero results.
- Checkout: at least 20 entrants; payment failure requires at least 5 failures and a 10% failure rate; minimum-order friction requires at least 5 blocks; checkout drop requires at least 35% drop-off.
- Basket: at least 5 completed pair orders and lift of at least 1.20.
- Campaign: at least 30 sessions and conversion below 50% of the tenant baseline.
- Chat: at least 10 messages for a non-general intent.
- Competitor: a human-approved comparison, match quality at least 70, and normalized price index at least 110.

The detector window defaults to 30 days and is bounded to 7-180 days. A run returns at most 50 candidates by default and never more than 100.

## AI boundary

AI receives only the already-fixed aggregate evidence, scores, and deterministic recommended action. It may explain the card using validated structured output; it may not invent metrics, change scores, approve actions, or execute changes. Every attempt records provider/model, evidence hash, validation result, latency, token counts, and any error. With no API key, generation is disabled safely and deterministic opportunities remain available.
