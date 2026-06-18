import json
import math
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from db import get_db
from dependencies.auth import get_current_user, get_optional_current_user, get_restaurant_id, TokenData
from core.money import cents_to_float, percentage_of_cents
from services.commerce import (
    RequestedLine,
    calculate_order_margin,
    emit_order_created,
    generate_order_id,
    load_money_setting_cents,
    mark_cart_converted,
    persist_cart_snapshot,
    persist_order_items,
    price_menu_lines,
)
from services.consent import ensure_customer_with_cursor
from services.jobs import enqueue_job
from services.advanced_conversion import validate_private_offer

router = APIRouter()


class OrderItem(BaseModel):
    menuItemId: int
    quantity: int
    name: str = ""
    price: float = 0
    category: Optional[str] = ""


class CreateOrderRequest(BaseModel):
    items: List[OrderItem]
    guestName: Optional[str] = None
    guestEmail: Optional[str] = None
    guestPhone: Optional[str] = None
    address: Optional[str] = ""
    orderType: str = "delivery"
    paymentMethod: str = "cash"
    branchId: Optional[int] = None
    notes: Optional[str] = ""
    pointsToRedeem: int = 0
    customerLat: Optional[float] = None
    customerLng: Optional[float] = None
    cartId: Optional[str] = None
    visitorId: Optional[str] = None
    sessionId: Optional[str] = None
    privateOfferCode: Optional[str] = None
    idempotencyKey: Optional[str] = None

    @field_validator("items")
    @classmethod
    def items_not_empty(cls, v: list) -> list:
        if len(v) < 1:
            raise ValueError("items must not be empty")
        return v

    @field_validator("orderType")
    @classmethod
    def validate_order_type(cls, v: str) -> str:
        if v not in {"delivery", "pickup", "dine-in"}:
            raise ValueError("orderType must be delivery, pickup, or dine-in")
        return v

    @field_validator("paymentMethod")
    @classmethod
    def validate_payment_method(cls, v: str) -> str:
        if v not in {"cash", "card"}:
            raise ValueError("paymentMethod must be cash or card")
        return v


def _row_to_order(r):
    items = r[5]
    if isinstance(items, str):
        items = json.loads(items)
    return {
        "id": r[0],
        "userId": r[1],
        "guestName": r[2] or "",
        "guestEmail": r[3] or "",
        "guestPhone": r[4] or "",
        "items": items,
        "subtotal": float(r[6] or 0),
        "discountAmount": float(r[7] or 0),
        "deliveryCharge": float(r[8] or 0),
        "total": float(r[9] or 0),
        "status": r[10],
        "orderType": r[11] or "delivery",
        "paymentMethod": r[12] or "cash",
        "branchId": r[13],
        "address": r[14] or "",
        "notes": r[15] or "",
        "pointsEarned": r[16] or 0,
        "pointsRedeemed": r[17] or 0,
        "createdAt": r[18].isoformat() if r[18] else "",
        "source": r[19] or "online",
        "claimStatus": r[20] or "unclaimed",
    }


def _get_setting(cur, key: str, restaurant_id: int, default: str = "") -> str:
    cur.execute("SELECT value FROM settings WHERE key = %s AND restaurant_id = %s", (key, restaurant_id))
    row = cur.fetchone()
    return row[0] if row else default


def _safe_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _get_rewards_program_settings(cur, restaurant_id: int):
    cur.execute(
        """
        SELECT key, value
        FROM settings
        WHERE key IN ('points_per_dollar', 'min_redeem_points', 'points_value_cents', 'rewards_enabled')
          AND restaurant_id = %s
        """,
        (restaurant_id,),
    )
    raw = {k: v for k, v in cur.fetchall()}

    points_per_dollar = max(0, _safe_int(raw.get("points_per_dollar"), 10))
    min_redeem_points = max(1, _safe_int(raw.get("min_redeem_points"), 100))
    points_value_cents = max(0, _safe_int(raw.get("points_value_cents"), 1))
    rewards_enabled = _safe_bool(raw.get("rewards_enabled"), True)

    return {
        "points_per_dollar": points_per_dollar,
        "min_redeem_points": min_redeem_points,
        "points_value_cents": points_value_cents,
        "rewards_enabled": rewards_enabled,
    }


_ORDER_SELECT = """
    SELECT id, user_id, guest_name, guest_email, guest_phone,
           items, subtotal, discount_amount, delivery_charge, total,
           status, order_type, payment_method, branch_id,
           address, notes, points_earned, points_redeemed, created_at,
           source, claim_status
    FROM orders
"""


@router.post("/", status_code=201)
def create_order(
    body: CreateOrderRequest,
    current_user: Optional[TokenData] = Depends(get_optional_current_user),
    restaurant_id: int = Depends(get_restaurant_id),
):
    # Use restaurant_id from token if available (more trusted)
    if current_user:
        restaurant_id = current_user.restaurant_id

    if not current_user:
        if not body.guestName or not body.guestName.strip():
            raise HTTPException(status_code=400, detail="guestName is required for guest checkout")
        if not body.guestPhone or not body.guestPhone.strip():
            raise HTTPException(status_code=400, detail="guestPhone is required for guest checkout")

    idempotency_key = (body.idempotencyKey or "").strip()[:80] or None

    with get_db() as conn:
        with conn.cursor() as cur:
            # Idempotency: a retried submission with the same key returns the original
            # order instead of creating a duplicate. Scoped per tenant.
            if idempotency_key:
                cur.execute(
                    _ORDER_SELECT + " WHERE restaurant_id = %s AND idempotency_key = %s",
                    (restaurant_id, idempotency_key),
                )
                existing = cur.fetchone()
                if existing:
                    return _row_to_order(existing)

            priced_lines = price_menu_lines(
                cur,
                restaurant_id,
                [RequestedLine(menu_item_id=item.menuItemId, quantity=item.quantity) for item in body.items],
            )
            currency = priced_lines[0].currency
            subtotal_cents = sum(line.line_revenue_cents for line in priced_lines)

            if not _safe_bool(_get_setting(cur, "restaurant_open", restaurant_id, "true"), True):
                raise HTTPException(status_code=409, detail="Restaurant is currently closed")

            minimum_order_cents = load_money_setting_cents(cur, restaurant_id, "min_order_amount")
            if subtotal_cents < minimum_order_cents:
                raise HTTPException(
                    status_code=400,
                    detail=f"Minimum order is {cents_to_float(minimum_order_cents):.2f} {currency}",
                )

            if body.branchId is not None:
                cur.execute(
                    "SELECT is_open FROM branches WHERE id = %s AND restaurant_id = %s",
                    (body.branchId, restaurant_id),
                )
                branch = cur.fetchone()
                if not branch:
                    raise HTTPException(status_code=400, detail="Branch is not valid for this restaurant")
                if not branch[0]:
                    raise HTTPException(status_code=409, detail="Selected branch is currently closed")

            visitor_id = (body.visitorId or "checkout-visitor").strip()[:100]
            session_id = (body.sessionId or "checkout-session").strip()[:100]
            cart_id = (body.cartId or f"cart-{generate_order_id()}").strip()[:100]
            customer_id = None
            if current_user:
                customer_id = ensure_customer_with_cursor(
                    cur, restaurant_id, current_user.id, current_user.email
                )

            persist_cart_snapshot(
                cur,
                tenant_id=restaurant_id,
                cart_id=cart_id,
                visitor_id=visitor_id,
                session_id=session_id,
                customer_id=customer_id,
                user_id=current_user.id if current_user else None,
                lines=priced_lines,
            )

            delivery_charge_cents = 0
            if body.orderType == "delivery":
                delivery_charge_cents = load_money_setting_cents(cur, restaurant_id, "delivery_charge")

            # ── Server-side delivery radius guard ─────────────────────────────
            if body.orderType == "delivery" and body.customerLat is not None and body.customerLng is not None:
                lat_str = _get_setting(cur, "restaurant_lat", restaurant_id, "").strip()
                lng_str = _get_setting(cur, "restaurant_lng", restaurant_id, "").strip()
                radius_str = _get_setting(cur, "delivery_radius_km", restaurant_id, "").strip()
                if lat_str and lng_str:
                    try:
                        rest_lat = float(lat_str)
                        rest_lng = float(lng_str)
                        radius_km = max(0.1, float(radius_str)) if radius_str else 5.0

                        def _hav(lat1, lng1, lat2, lng2):
                            R = 6371
                            dl = (lat2 - lat1) * math.pi / 180
                            dg = (lng2 - lng1) * math.pi / 180
                            a = (math.sin(dl / 2) ** 2
                                 + math.cos(lat1 * math.pi / 180)
                                 * math.cos(lat2 * math.pi / 180)
                                 * math.sin(dg / 2) ** 2)
                            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

                        dist = _hav(body.customerLat, body.customerLng, rest_lat, rest_lng)
                        if dist > radius_km:
                            raise HTTPException(
                                status_code=400,
                                detail="Delivery not available to this address."
                            )
                    except HTTPException:
                        raise
                    except Exception:
                        pass  # Don't block order if radius check errors

            rewards_cfg = _get_rewards_program_settings(cur, restaurant_id)

            discount_cents = 0
            points_redeemed = 0
            private_offer = None
            if current_user and body.pointsToRedeem > 0 and rewards_cfg["rewards_enabled"]:
                if body.pointsToRedeem >= rewards_cfg["min_redeem_points"]:
                    cur.execute(
                        """SELECT points FROM points
                           WHERE user_id = %s AND restaurant_id = %s
                           AND (expires_at IS NULL OR expires_at > NOW())""",
                        (current_user.id, restaurant_id),
                    )
                    prow = cur.fetchone()
                    user_pts = prow[0] if prow else 0
                    redeem = min(body.pointsToRedeem, user_pts)

                    # Cap the integer discount to the configured share of subtotal.
                    max_pct = max(0, _safe_int(
                        _get_setting(cur, "max_points_discount_percent", restaurant_id, "20"), 20
                    ))
                    points_value_cents = rewards_cfg["points_value_cents"]
                    if points_value_cents > 0:
                        max_discount_from_points = percentage_of_cents(subtotal_cents, max_pct)
                        max_redeemable_points = max_discount_from_points // points_value_cents
                        redeem = min(redeem, max_redeemable_points)

                    points_redeemed = redeem
                    discount_cents = redeem * rewards_cfg["points_value_cents"]

            line_margins = [line.line_margin_cents for line in priced_lines]
            margin_before_private_offer = sum(int(value or 0) for value in line_margins) if all(value is not None for value in line_margins) else None
            if body.privateOfferCode:
                private_offer = validate_private_offer(
                    cur,
                    tenant_id=restaurant_id,
                    code=body.privateOfferCode,
                    subtotal_cents=subtotal_cents,
                    estimated_margin_before_discount_cents=None if margin_before_private_offer is None else margin_before_private_offer - discount_cents,
                    visitor_id=visitor_id,
                    customer_id=customer_id,
                )
                discount_cents += int(private_offer["discountCents"])

            total_cents = max(0, subtotal_cents + delivery_charge_cents - discount_cents)
            margin = calculate_order_margin(priced_lines, revenue_cents=total_cents)

            # Points are awarded only when order is marked delivered, not at placement.
            points_earned = 0

            order_id = generate_order_id()
            legacy_items = [line.legacy_json() for line in priced_lines]
            items_json = json.dumps(legacy_items)

            cur.execute(
                """INSERT INTO orders
                   (id, restaurant_id, user_id, guest_name, guest_email, guest_phone,
                    items, subtotal, discount_amount, delivery_charge, total,
                    status, order_type, payment_method, branch_id,
                    address, notes, points_earned, points_redeemed, source,
                    currency, subtotal_cents, discount_cents, delivery_charge_cents,
                    total_cents, ingredient_cost_cents, packaging_cost_cents,
                    contribution_margin_cents, cart_id, visitor_id, session_id, idempotency_key)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'placed',%s,%s,%s,%s,%s,%s,%s,'online',
                           %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    order_id, restaurant_id,
                    current_user.id if current_user else None,
                    body.guestName or "",
                    body.guestEmail or "",
                    body.guestPhone or "",
                    items_json, cents_to_float(subtotal_cents), cents_to_float(discount_cents),
                    cents_to_float(delivery_charge_cents), cents_to_float(total_cents),
                    body.orderType, body.paymentMethod, body.branchId,
                    body.address or "", body.notes or "",
                    points_earned, points_redeemed,
                    currency, subtotal_cents, discount_cents, delivery_charge_cents,
                    total_cents,
                    margin.ingredient_cost_cents if margin else 0,
                    margin.packaging_cost_cents if margin else 0,
                    margin.contribution_margin_cents if margin else None,
                    cart_id, visitor_id, session_id, idempotency_key,
                ),
            )
            if private_offer:
                cur.execute(
                    """INSERT INTO private_offer_redemptions
                       (tenant_id,offer_id,order_id,cart_id,visitor_id,customer_id,subtotal_cents,
                        discount_cents,contribution_margin_after_discount_cents,status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'REDEEMED')""",
                    (
                        restaurant_id,
                        private_offer["id"],
                        order_id,
                        cart_id,
                        visitor_id,
                        customer_id,
                        subtotal_cents,
                        int(private_offer["discountCents"]),
                        private_offer["contributionMarginAfterDiscountCents"],
                    ),
                )
            persist_order_items(cur, tenant_id=restaurant_id, order_id=order_id, lines=priced_lines)
            mark_cart_converted(cur, tenant_id=restaurant_id, cart_id=cart_id)
            emit_order_created(
                cur,
                tenant_id=restaurant_id,
                order_id=order_id,
                cart_id=cart_id,
                visitor_id=visitor_id,
                session_id=session_id,
                customer_id=customer_id,
                location_id=body.branchId,
                total_cents=total_cents,
                currency=currency,
            )
            enqueue_job(
                cur,
                tenant_id=restaurant_id,
                job_name="analytics.aggregate_daily",
                idempotency_key=f"order-created:{order_id}",
                metadata={"orderId": order_id},
            )

            if current_user:
                if points_redeemed > 0:
                    cur.execute(
                        """INSERT INTO points (user_id, restaurant_id, points) VALUES (%s, %s, 0)
                           ON CONFLICT (user_id, restaurant_id) DO UPDATE
                           SET points = GREATEST(0, points.points - %s), updated_at = NOW()
                           RETURNING points""",
                        (current_user.id, restaurant_id, points_redeemed),
                    )
                    bal_row = cur.fetchone()
                    balance_after = bal_row[0] if bal_row else 0
                    cur.execute(
                        """INSERT INTO points_transactions
                           (user_id, restaurant_id, order_id, type, points, balance_after)
                           VALUES (%s, %s, %s, 'redeem', %s, %s)""",
                        (current_user.id, restaurant_id, order_id, -points_redeemed, balance_after),
                    )

    return {
        "id": order_id,
        "userId": current_user.id if current_user else None,
        "guestName": body.guestName or "",
        "guestPhone": body.guestPhone or "",
        "items": legacy_items,
        "subtotal": cents_to_float(subtotal_cents),
        "discountAmount": cents_to_float(discount_cents),
        "deliveryCharge": cents_to_float(delivery_charge_cents),
        "total": cents_to_float(total_cents),
        "currency": currency,
        "cartId": cart_id,
        "status": "placed",
        "orderType": body.orderType,
        "paymentMethod": body.paymentMethod,
        "branchId": body.branchId,
        "address": body.address or "",
        "notes": body.notes or "",
        "pointsEarned": points_earned,
        "pointsRedeemed": points_redeemed,
        "privateOfferCode": body.privateOfferCode,
        "createdAt": datetime.utcnow().isoformat(),
        "source": "online",
    }


@router.get("/history")
def get_order_history(current_user: TokenData = Depends(get_current_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                _ORDER_SELECT + "WHERE (user_id = %s OR claimed_by_user_id = %s) "
                "AND restaurant_id = %s ORDER BY created_at DESC",
                (current_user.id, current_user.id, current_user.restaurant_id),
            )
            rows = cur.fetchall()
    return [_row_to_order(r) for r in rows]


@router.get("/track")
def track_order_public(
    order_id: str,
    phone: str,
    restaurant_id: int = Depends(get_restaurant_id),
):
    """Public order tracking — match by order ID + guest_phone or user phone."""
    if not order_id or not phone:
        raise HTTPException(status_code=400, detail="order_id and phone are required")
    with get_db() as conn:
        with conn.cursor() as cur:
            # Normalize both stored and input phone to last 10 digits so that
            # local format "03344215243" matches stored "+923344215243".
            cur.execute(
                _ORDER_SELECT +
                """WHERE id = %s AND restaurant_id = %s AND (
                    RIGHT(REGEXP_REPLACE(guest_phone, '[^0-9]', '', 'g'), 10)
                        = RIGHT(REGEXP_REPLACE(%s, '[^0-9]', '', 'g'), 10)
                    OR EXISTS (
                        SELECT 1 FROM users
                        WHERE id = orders.user_id
                          AND RIGHT(REGEXP_REPLACE(phone, '[^0-9]', '', 'g'), 10)
                                  = RIGHT(REGEXP_REPLACE(%s, '[^0-9]', '', 'g'), 10)
                    )
                )""",
                (order_id, restaurant_id, phone, phone),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found. Check the order number and phone.")
    return _row_to_order(row)


# ─────────────────────────────────────────────────────────────────────────────
# Claim in-store order
# ─────────────────────────────────────────────────────────────────────────────

class ClaimOrderRequest(BaseModel):
    receiptNumber: str
    phone: Optional[str] = None


@router.post("/claim")
def claim_order(
    body: ClaimOrderRequest,
    current_user: TokenData = Depends(get_current_user),
):
    rid = current_user.restaurant_id
    receipt = body.receiptNumber.strip()
    if not receipt:
        raise HTTPException(status_code=400, detail="Receipt number is required")

    with get_db() as conn:
        with conn.cursor() as cur:
            # Find order by ID or claim_code
            cur.execute(
                """SELECT id, status, claim_status, claimed_by_user_id, guest_phone, total,
                          items, points_earned, created_at,
                          rs.claim_expiry_days, rs.require_phone_match
                   FROM orders o
                   LEFT JOIN reward_settings rs ON rs.restaurant_id = o.restaurant_id
                   WHERE o.restaurant_id = %s AND (o.id = %s OR o.claim_code = %s)
                   LIMIT 1""",
                (rid, receipt, receipt),
            )
            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Order not found. Check the receipt number.")

            (
                order_id, status, claim_status, claimed_by_user_id, guest_phone,
                total, items, points_earned_orig, created_at,
                claim_expiry_days, require_phone_match,
            ) = row

            rewards_cfg = _get_rewards_program_settings(cur, rid)

            if claim_status == "claimed":
                raise HTTPException(status_code=409, detail="This order has already been claimed.")

            if status not in ("delivered", "completed"):
                raise HTTPException(status_code=400, detail="Only completed orders can be claimed.")

            # Check expiry
            expiry_days = claim_expiry_days or 30
            if created_at and (datetime.utcnow() - created_at.replace(tzinfo=None)).days > expiry_days:
                raise HTTPException(status_code=410, detail=f"Claim window expired ({expiry_days} days).")

            # Optional phone match
            if require_phone_match and guest_phone:
                provided = (body.phone or "").strip().replace(" ", "").replace("-", "")
                stored = guest_phone.strip().replace(" ", "").replace("-", "")
                if provided != stored:
                    raise HTTPException(status_code=400, detail="Phone number does not match this order.")

            # Calculate points to award
            points_to_award = 0
            if rewards_cfg["rewards_enabled"]:
                subtotal = float(total)
                points_to_award = int(subtotal * rewards_cfg["points_per_dollar"])

            # Link the order to user
            cur.execute(
                """UPDATE orders SET claimed_by_user_id = %s, claimed_at = NOW(),
                   claim_status = 'claimed', updated_at = NOW()
                   WHERE id = %s""",
                (current_user.id, order_id),
            )

            # Award points
            if points_to_award > 0:
                cur.execute(
                    """INSERT INTO points (user_id, restaurant_id, points) VALUES (%s, %s, %s)
                       ON CONFLICT (user_id, restaurant_id) DO UPDATE
                       SET points = points.points + %s, updated_at = NOW()""",
                    (current_user.id, rid, points_to_award, points_to_award),
                )

            # Audit log
            cur.execute(
                """INSERT INTO order_claims (order_id, user_id, receipt_number, status, claimed_at)
                   VALUES (%s, %s, %s, 'success', NOW())""",
                (order_id, current_user.id, receipt),
            )

    return {
        "success": True,
        "orderId": order_id,
        "pointsEarned": points_to_award,
        "message": f"Order claimed successfully! You earned {points_to_award} points.",
    }


@router.get("/{order_id}")
def get_order(order_id: str, current_user: TokenData = Depends(get_current_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                _ORDER_SELECT + "WHERE id = %s AND (user_id = %s OR claimed_by_user_id = %s)"
                " AND restaurant_id = %s",
                (order_id, current_user.id, current_user.id, current_user.restaurant_id),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    return _row_to_order(row)
