# Mission Workflows

Status: Phase 6 implemented.

All missions use the common lifecycle `DRAFT/NEEDS_APPROVAL -> APPROVED -> RUNNING`, with pause, cancel, completion, audit history, eligibility snapshots, deterministic SHA-256 treatment/holdout assignment, actions, guardrails, events, and incremental result snapshots.

Implemented missions:

- **Abandoned Cart Recovery:** requires a non-empty inactive cart, no delivered order for that cart, minimum value, customer contact, granted channel consent, no suppression, available frequency capacity, a running mission, and treatment assignment. Actions advance by sequence and optional delay. No discount is created automatically.
- **Intelligent Bundle:** uses two authoritative available menu items, server prices/costs, a minimum-margin check, and a customer-side cart card only for treatment visitors. Holdouts see no card. Later orders are compared by stable visitor assignment.
- **Lapsed Customer Win-Back:** calculates order count, lifetime revenue/margin, average order value, customer-specific or tenant-fallback reorder interval, expected reorder date, preferred categories/location/daypart, discount dependency, favorite item, and deterministic segments before contact/consent/frequency checks.
- **Quiet-Hour Demand:** evaluates enabled capacity windows by location, weekday, normal/maximum capacity, target utilization, historical demand, cancellation rate, and margin-qualified inventory. Missions pause on breached live capacity or low-stock guardrails. Public banners are treatment-only and rate-limited.
- **New Product Demand Test:** creates product concepts and variants that can be exposed publicly only as `COMING SOON`, `LIMITED TEST`, `PREORDER`, or `JOIN WAITLIST`. Interest, waitlist, and preorder events feed mission results without implying immediate menu availability.

Messaging uses provider interfaces for email, SMS, and WhatsApp. Phase 5 exposes only the mock provider; configuration rejects any non-mock provider, so development and test execution cannot send a real message. Every accepted send creates `campaign_messages`, `message_deliveries`, analytics, and mission-event records.

Results compare treatment and holdout conversion rates and report incremental orders/revenue, revenue, contribution margin, discount cost, message cost, delivery counts, operational violations, capacity utilization, qualified interest, waitlist conversion, preorder conversion, preferred price, and estimated concept contribution where applicable.
