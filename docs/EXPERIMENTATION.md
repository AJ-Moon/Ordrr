# Experimentation

Status: implemented in Phase 4.

FastAPI owns configuration, approval/start/pause transitions, audience checks, allocation, stable assignment, conflict keys, exposure acceptance, order attribution, and evaluation. Assignment uses a SHA-256 bucket of `experiment_id|visitor_id`; `(experiment_id, visitor_id)` is unique, so assignment is sticky. Visitors already assigned to a running experiment with the same conflict key are excluded from another assignment.

The reusable frontend experiment slot requests an active assignment and records exposure only after the assigned text is rendered. Exposure keys are tenant-idempotent. Completed orders are attributed only after first exposure using authoritative visitor/order records.

The initial supported primary metric is `order_conversion`. Evaluation requires the configured minimum sample per variant, reports revenue and contribution margin, and compares treatment against control with a two-proportion confidence interval. Multiple treatments use a Bonferroni-adjusted confidence level. A winner requires the adjusted interval to exclude zero and margin, refund-rate, and cancellation-rate guardrails to remain healthy. Results are `WINNER`, `LOSER`, `INCONCLUSIVE`, or `INSUFFICIENT_DATA`; raw percentage differences cannot declare a winner.

Default operational bounds:

- Minimum sample: 100 per variant (API minimum 20).
- Confidence: 95% (allowed 80%-99.9%).
- Allocation: 1%-100%.
- Refund and cancellation guardrails: 10%, configurable through environment variables.
