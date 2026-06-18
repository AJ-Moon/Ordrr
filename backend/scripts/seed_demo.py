"""Deterministic demo-data seeder for the ORDER revenue-operator platform.

Populates the *new* commerce/analytics model (analytics_events, carts,
order_line_items, orders with status='delivered') plus competitors, one
experiment and one of each first-phase mission, then runs the real
aggregation + detection job handlers so every dashboard shows live data.

The seed is idempotent: analytics events use deterministic event_ids
(ON CONFLICT DO NOTHING) and orders use deterministic ids, while
competitors/experiments/missions are skipped when an entity with the same
name already exists. Safe to re-run.

Usage:  python -m scripts.seed_demo            (defaults: 35 days, tenant 1)
        python -m scripts.seed_demo --days 21 --tenant 1
"""
import argparse
import json
import random
import zlib
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from psycopg2.extras import execute_values

load_dotenv()

from db import get_db  # noqa: E402
from services.commerce import (  # noqa: E402
    RequestedLine,
    persist_cart_snapshot,
    persist_order_items,
    price_menu_lines,
)

# Column order mirrors services.events.insert_event so seeded rows are identical
# to production ingestion. Events are buffered and bulk-inserted with
# execute_values (one round-trip per day instead of one per event) to keep the
# seed fast and cheap against a remote database.
_EVENT_COLUMNS = (
    "event_id, tenant_id, location_id, visitor_id, session_id, customer_id, event_name, "
    "occurred_at, page_path, referrer, source, medium, campaign, content, term, click_id, "
    "item_id, category_id, cart_id, order_id, experiment_id, variant_id, mission_id, "
    "properties, schema_version, is_server_event, consent_state"
)


def _event_tuple(*, event_id, tenant_id, visitor_id, session_id, event_name, occurred_at,
                 location_id=None, customer_id=None, page_path=None, referrer=None,
                 source=None, medium=None, campaign=None, content=None, term=None,
                 click_id=None, item_id=None, category_id=None, cart_id=None, order_id=None,
                 experiment_id=None, variant_id=None, mission_id=None, properties=None,
                 schema_version=1, is_server_event=False, consent_state="unknown"):
    return (
        event_id, tenant_id, location_id, visitor_id, session_id, customer_id, event_name,
        occurred_at, page_path, referrer, source, medium, campaign, content, term, click_id,
        item_id, category_id, cart_id, order_id, experiment_id, variant_id, mission_id,
        json.dumps(properties or {}), schema_version, is_server_event, consent_state,
    )


def _flush_events(cur, buf):
    if not buf:
        return
    execute_values(
        cur,
        f"""INSERT INTO analytics_events ({_EVENT_COLUMNS}) VALUES %s
            ON CONFLICT (tenant_id, event_id) DO NOTHING""",
        buf,
        template="(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)",
        page_size=500,
    )
    buf.clear()

UTC = timezone.utc
RNG_SEED = 20260614

# Items engineered to produce distinct menu-matrix classifications.
LEAKING_ITEM = 7        # BBQ Chicken pizza — lots of attention, weak add-to-cart
HIDDEN_WINNER_ITEM = 11  # Loaded Fries — little attention, strong conversion

SOURCES = [
    ("google", "organic", "", 0.40, 0.10),
    ("(direct)", "(none)", "", 0.18, 0.09),
    ("instagram", "social", "spring_launch", 0.15, 0.16),   # strong source
    ("facebook", "cpc", "summer_promo", 0.15, 0.03),        # weak campaign
    ("google", "cpc", "bbq_deal", 0.12, 0.08),
]

NO_RESULT_QUERIES = ["vegan pizza", "sushi", "gluten free bun", "salad bowl"]
RESULT_QUERIES = [("burger", 4), ("pizza", 4), ("fries", 2), ("milkshake", 1)]

# Weighted chat objection intents (spec §17) for the chatbot-analytics dashboard.
CHAT_INTENTS = [
    ("PRICE_CONCERN", 0.22), ("DELIVERY_AREA", 0.16), ("PORTION_SIZE", 0.12),
    ("DEAL_REQUEST", 0.11), ("DELIVERY_TIME", 0.10), ("INGREDIENT", 0.08),
    ("AVAILABILITY", 0.07), ("ALLERGEN", 0.05), ("PAYMENT", 0.04),
    ("PRODUCT_COMPARISON", 0.03), ("OTHER", 0.02),
]


def _pick_intent(rng):
    r = rng.random()
    cum = 0.0
    for intent, weight in CHAT_INTENTS:
        cum += weight
        if r <= cum:
            return intent
    return "OTHER"


def _eid(*parts) -> str:
    return "seed-" + "-".join(str(p) for p in parts)


def _pick_source(rng):
    r = rng.random()
    cum = 0.0
    for src in SOURCES:
        cum += src[3]
        if r <= cum:
            return src
    return SOURCES[0]


def _item_profile(item_id):
    """(impression_p, view_rate, atc_rate, purchase_rate) per item."""
    if item_id == LEAKING_ITEM:
        return 0.80, 0.72, 0.06, 0.45
    if item_id == HIDDEN_WINNER_ITEM:
        return 0.26, 0.55, 0.52, 0.70
    return 0.45, 0.45, 0.22, 0.55


def set_item_costs(cur, tenant_id):
    """Give every item a realistic ingredient + packaging cost so margins and
    contribution metrics can be computed (fixes the missing-cost data gap)."""
    cur.execute(
        """UPDATE menu_items
           SET ingredient_cost_cents = round(COALESCE(price_cents, round(price*100)) * 0.32)::bigint,
               packaging_cost_cents = CASE WHEN COALESCE(packaging_cost_cents,0) = 0 THEN 35
                                           ELSE packaging_cost_cents END
           WHERE restaurant_id = %s AND ingredient_cost_cents IS NULL""",
        (tenant_id,),
    )


def _insert_order(cur, buf, *, tenant_id, order_id, lines, day, source, session_id, visitor_id, cart_id, branch_id):
    subtotal = sum(ln.line_revenue_cents for ln in lines)
    ingredient = sum((ln.line_ingredient_cost_cents or 0) for ln in lines)
    packaging = sum(ln.line_packaging_cost_cents for ln in lines)
    delivery = 299
    tax = round(subtotal * 0.08)
    payment_cost = round(subtotal * 0.029) + 30
    commission = 0
    total = subtotal + delivery + tax
    margin = subtotal - ingredient - packaging - payment_cost - commission
    completed_at = day.replace(hour=18, minute=random.randint(0, 59), tzinfo=UTC)
    items_json = json.dumps([ln.legacy_json() for ln in lines])
    cur.execute(
        """INSERT INTO orders
           (id, subtotal, status, source, restaurant_id, items, currency,
            delivery_charge, total, order_type, payment_method, branch_id,
            subtotal_cents, discount_cents, delivery_charge_cents, tax_cents, refund_cents,
            payment_cost_cents, commission_cents, packaging_cost_cents, ingredient_cost_cents,
            contribution_margin_cents, total_cents, cart_id, visitor_id, session_id,
            completed_at, created_at)
           VALUES (%s,%s,'delivered',%s,%s,%s::jsonb,%s,
                   %s,%s,'delivery','card',%s,
                   %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (id) DO NOTHING""",
        (
            order_id, subtotal / 100.0, source[0], tenant_id, items_json, lines[0].currency,
            delivery / 100.0, total / 100.0, branch_id,
            subtotal, 0, delivery, tax, 0, payment_cost, commission, packaging, ingredient,
            margin, total, cart_id, visitor_id, session_id, completed_at, completed_at,
        ),
    )
    persist_order_items(cur, tenant_id=tenant_id, order_id=order_id, lines=lines)
    for name in ("order_completed", "order_created"):
        buf.append(_event_tuple(
            event_id=_eid(name, order_id), tenant_id=tenant_id, visitor_id=visitor_id,
            session_id=session_id, event_name=name, occurred_at=completed_at, cart_id=cart_id,
            order_id=order_id, location_id=branch_id, is_server_event=True, source=source[0],
            medium=source[1], campaign=source[2] or None, properties={"totalCents": total},
            consent_state="essential",
        ))


def seed_events_and_orders(cur, tenant_id, days):
    rng = random.Random(RNG_SEED)
    random.seed(RNG_SEED)
    cur.execute(
        "SELECT id FROM menu_items WHERE restaurant_id = %s AND is_available = TRUE ORDER BY id",
        (tenant_id,),
    )
    item_ids = [int(r[0]) for r in cur.fetchall()]
    cur.execute("SELECT id FROM branches WHERE restaurant_id = %s ORDER BY id", (tenant_id,))
    branch_ids = [int(r[0]) for r in cur.fetchall()] or [None]

    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    orders = carts = events_sessions = 0
    buf: list[tuple] = []

    for d in range(days, 0, -1):
        day = today - timedelta(days=d)
        weekday = day.weekday()
        base = 14 if weekday >= 4 else 10
        n_sessions = base + rng.randint(-2, 4)
        for s in range(n_sessions):
            session_id = _eid("sess", day.date(), s)
            visitor_id = _eid("vis", (d * 7 + s) % 120)  # ~120 recurring visitors
            branch_id = rng.choice(branch_ids)
            source = _pick_source(rng)
            device = "mobile" if rng.random() < 0.62 else "desktop"
            ts = day.replace(hour=rng.randint(9, 22), minute=rng.randint(0, 59), tzinfo=UTC)
            events_sessions += 1

            def ev(name, occurred, **kw):
                buf.append(_event_tuple(
                    event_id=_eid(name, session_id, kw.pop("seq", name)),
                    tenant_id=tenant_id, visitor_id=visitor_id, session_id=session_id,
                    event_name=name, occurred_at=occurred, location_id=branch_id,
                    source=source[0], medium=source[1], campaign=source[2] or None,
                    page_path=kw.pop("page", "/menu"),
                    properties={"deviceClass": device, **kw.pop("props", {})},
                    consent_state="analytics_granted", **kw,
                ))

            ev("page_viewed", ts, page="/", seq="home")
            ev("menu_viewed", ts + timedelta(seconds=8), seq="menu")

            # Search behaviour on a subset of sessions.
            if rng.random() < 0.22:
                if rng.random() < 0.4:
                    q = rng.choice(NO_RESULT_QUERIES)
                    ev("search_performed", ts + timedelta(seconds=12),
                       props={"query": q, "resultCount": 0}, seq="search0")
                else:
                    q, rc = rng.choice(RESULT_QUERIES)
                    ev("search_performed", ts + timedelta(seconds=12),
                       props={"query": q, "resultCount": rc}, seq="search")
                    if rng.random() < 0.5:
                        ev("search_result_clicked", ts + timedelta(seconds=16),
                           props={"query": q}, seq="searchclick")

            # Chatbot objections on a subset of sessions, classified by intent so
            # the chatbot-analytics dashboard (daily_chat_metrics) is populated.
            if rng.random() < 0.18:
                intent = _pick_intent(rng)
                ev("chat_opened", ts + timedelta(seconds=18), seq="chatopen")
                ev("chat_message_sent", ts + timedelta(seconds=20),
                   props={"intent": intent}, seq="chatmsg")
                if rng.random() < 0.55:
                    rec_item = rng.choice([6, 11, 1, 14])
                    ev("chat_recommendation_shown", ts + timedelta(seconds=22),
                       item_id=rec_item, props={"intent": intent}, seq="chatrec")
                    if rng.random() < 0.4:
                        ev("chat_recommendation_clicked", ts + timedelta(seconds=24),
                           item_id=rec_item, props={"intent": intent}, seq="chatrecclick")

            cart_lines: list[RequestedLine] = []
            offset = 20
            for item_id in item_ids:
                imp_p, view_rate, atc_rate, _ = _item_profile(item_id)
                if rng.random() > imp_p:
                    continue
                offset += 3
                ev("item_impression", ts + timedelta(seconds=offset), item_id=item_id, seq=f"imp{item_id}")
                if rng.random() <= view_rate:
                    offset += 2
                    ev("item_viewed", ts + timedelta(seconds=offset), item_id=item_id,
                       page=f"/menu/{item_id}", seq=f"view{item_id}")
                    if rng.random() <= atc_rate:
                        cart_lines.append(RequestedLine(menu_item_id=item_id, quantity=rng.randint(1, 2)))

            if not cart_lines:
                continue

            cart_id = _eid("cart", session_id)
            try:
                priced = price_menu_lines(cur, tenant_id, cart_lines)
            except Exception:
                continue
            ev("item_added_to_cart", ts + timedelta(seconds=offset + 4),
               item_id=cart_lines[0].menu_item_id, cart_id=cart_id, seq="atc")
            ev("cart_created", ts + timedelta(seconds=offset + 5), cart_id=cart_id, seq="cartc")
            persist_cart_snapshot(
                cur, tenant_id=tenant_id, cart_id=cart_id, visitor_id=visitor_id,
                session_id=session_id, customer_id=None, user_id=None, lines=priced,
            )
            carts += 1

            # Checkout funnel + friction.
            if rng.random() < 0.65:
                ev("checkout_started", ts + timedelta(seconds=offset + 10),
                   cart_id=cart_id, props={"step": "CART"}, seq="cko")
                ev("checkout_step_viewed", ts + timedelta(seconds=offset + 14),
                   cart_id=cart_id, props={"step": "DELIVERY_FEE"}, seq="ckdf")
                if rng.random() < 0.12:
                    ev("delivery_area_checked", ts + timedelta(seconds=offset + 16),
                       props={"available": False}, seq="darej")
                if rng.random() < 0.08:
                    ev("minimum_order_blocked", ts + timedelta(seconds=offset + 17),
                       props={"step": "CART"}, seq="minblock")
                if rng.random() < 0.10:
                    ev("payment_failed", ts + timedelta(seconds=offset + 20),
                       props={"step": "PAYMENT_ATTEMPT"}, seq="payfail")
                    continue
                # Convert to a completed order on most checkouts.
                if rng.random() < 0.78:
                    order_id = f"SD{zlib.crc32(session_id.encode()):08x}"  # <=20 chars, deterministic
                    _insert_order(
                        cur, buf, tenant_id=tenant_id, order_id=order_id, lines=priced, day=day,
                        source=source, session_id=session_id, visitor_id=visitor_id,
                        cart_id=cart_id, branch_id=branch_id,
                    )
                    cur.execute(
                        "UPDATE carts SET status='converted', converted_at=NOW() WHERE tenant_id=%s AND id=%s",
                        (tenant_id, cart_id),
                    )
                    orders += 1
        _flush_events(cur, buf)  # one bulk insert per day keeps round-trips low
    return {"sessions": events_sessions, "carts": carts, "orders": orders}


def seed_competitors(tenant_id):
    from routers import competitors as C
    admin = {"restaurant_id": tenant_id, "id": "seed", "role": "owner"}
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM competitors WHERE tenant_id=%s", (tenant_id,))
        if cur.fetchone()[0]:
            return "exists"
    c1 = C.create_competitor(C.CompetitorInput(
        name="Pizza Rivals", website="https://pizzarivals.example", currency="USD",
        referenceItemName="Large Pepperoni", referencePriceCents=1599), admin=admin)
    c2 = C.create_competitor(C.CompetitorInput(
        name="Burger Barn", website="https://burgerbarn.example", currency="USD",
        referenceItemName="Classic Burger", referencePriceCents=899), admin=admin)
    p1 = C.create_product(C.CompetitorProductInput(
        competitorId=c1["id"], name="Large Pepperoni", category="pizza", sizeLabel="Large",
        regularPriceCents=1599, dealPriceCents=1299, marketPositioning="value",
        sourceType="website", confidence=80), admin=admin)
    C.create_product(C.CompetitorProductInput(
        competitorId=c2["id"], name="Classic Burger", category="burgers",
        regularPriceCents=899, marketPositioning="value", sourceType="delivery_app",
        confidence=70), admin=admin)
    C.create_deal(C.CompetitorDealInput(
        competitorId=c1["id"], name="2 Large Pizzas $25", description="Bundle deal",
        priceCents=2500, includedItems=["Large Pepperoni", "Large Cheese"]), admin=admin)
    comp = C.create_comparison(C.ProductComparisonInput(
        ownItemId=6, competitorProductId=p1["id"], matchQuality=85,
        normalizationNotes="Both large pepperoni", competitorNormalizedPriceCents=1299), admin=admin)
    try:
        C.approve_comparison(comp["id"], admin=admin)
    except Exception:
        pass
    try:
        C.verify_competitor(c1["id"], admin=admin)
    except Exception:
        pass
    return "created"


def seed_experiment(tenant_id):
    from routers import experiments as E
    admin = {"restaurant_id": tenant_id, "id": "seed", "role": "owner"}
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM experiments WHERE tenant_id=%s", (tenant_id,))
        if cur.fetchone()[0]:
            return "exists"
    exp = E.create_experiment(E.ExperimentCreate(
        type="BUTTON_COPY", name="Home promo CTA copy",
        hypothesis="A benefit-led CTA increases add-to-cart on the homepage hero.",
        placement="HOME_PROMO_COPY", conflictKey="HOME_PROMO_COPY:copy",
        variants=[
            E.VariantInput(key="control", name="Control", config={"text": "Order online"}, weight=50, isControl=True),
            E.VariantInput(key="treatment", name="Treatment", config={"text": "Get it in 30 minutes"}, weight=50, isControl=False),
        ]), admin=admin)
    E.approve_experiment(exp["id"], admin=admin)
    E.start_experiment(exp["id"], admin=admin)
    return "created"


def seed_missions(tenant_id):
    from routers import missions as M
    admin = {"restaurant_id": tenant_id, "id": "seed", "role": "owner"}
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM missions WHERE tenant_id=%s", (tenant_id,))
        if cur.fetchone()[0]:
            return "exists"
    specs = [
        M.MissionCreate(
            type="ABANDONED_CART_RECOVERY", name="Abandoned cart reminder",
            objective="Recover abandoned carts with a no-discount reminder first.",
            hypothesis="A timely reminder recovers carts without margin loss.",
            audience={"minimumCartValueCents": 1500},
            actions=[M.MissionActionInput(type="SEND_EMAIL", sequence=1, config={"noAutomaticDiscount": True})]),
        M.MissionCreate(
            type="INTELLIGENT_BUNDLE", name="Pizza + fries bundle test",
            objective="Test a bundle upsell of a popular pizza with loaded fries.",
            hypothesis="Bundling raises average order value without cannibalising.",
            audience={"itemAId": 6, "itemBId": 11, "proposedBundlePriceCents": 1999},
            actions=[M.MissionActionInput(type="SHOW_CART_UPSELL", sequence=1, config={})]),
        M.MissionCreate(
            type="LAPSED_CUSTOMER_WINBACK", name="Lapsed customer win-back",
            objective="Win back customers past their expected reorder date.",
            hypothesis="A personalised reminder reactivates lapsed customers.",
            audience={"minimumOrderCount": 2},
            actions=[M.MissionActionInput(type="SEND_EMAIL", sequence=1, config={"noAutomaticDiscount": True})]),
    ]
    for spec in specs:
        m = M.create_mission(spec, admin=admin)
        try:
            M.approve(m["id"], admin=admin)
        except Exception:
            pass
    return "created"


def _run_job(tenant_id, job_name, metadata, retries=3):
    """Run a single job in its own short transaction. Daily aggregation in one
    long transaction can exceed a pooled connection's lifetime, so each job
    commits independently and retries transient connection drops."""
    from services.analytics_jobs import JOB_HANDLERS
    import psycopg2
    last = None
    for attempt in range(retries):
        try:
            with get_db() as conn, conn.cursor() as cur:
                JOB_HANDLERS[job_name](cur, tenant_id, metadata)
            return
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
            last = exc
    raise last if last else RuntimeError("job failed")


def run_jobs(tenant_id, days):
    today = datetime.now(UTC).date()
    # Per-day commits keep each transaction short (pooler-safe) and idempotent
    # via the DELETE+INSERT inside each aggregation handler.
    for d in range(days, 0, -1):
        _run_job(tenant_id, "analytics.aggregate_daily",
                 {"date": (today - timedelta(days=d)).isoformat()})
    for job in ["analytics.refresh_basket_associations", "analytics.refresh_menu_matrix",
                "customers.refresh_segments", "opportunities.detect_daily",
                "data_quality.refresh"]:
        try:
            _run_job(tenant_id, job, {})
        except Exception as exc:  # noqa: BLE001
            print(f"  ! job {job} failed: {str(exc)[:120]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", type=int, default=1)
    ap.add_argument("--days", type=int, default=35)
    args = ap.parse_args()
    tenant_id = args.tenant

    print(f"Seeding demo data for tenant {tenant_id} over {args.days} days …")
    with get_db() as conn, conn.cursor() as cur:
        set_item_costs(cur, tenant_id)
        stats = seed_events_and_orders(cur, tenant_id, args.days)
    print(f"  events/orders: {stats}")
    print(f"  competitors: {seed_competitors(tenant_id)}")
    print(f"  experiment:  {seed_experiment(tenant_id)}")
    print(f"  missions:    {seed_missions(tenant_id)}")
    print("  running aggregation + detection jobs …")
    run_jobs(tenant_id, args.days)
    print("Done.")


if __name__ == "__main__":
    main()
