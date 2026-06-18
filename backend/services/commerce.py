import json
import secrets
from dataclasses import dataclass
from typing import Iterable, Optional

from fastapi import HTTPException

from core.money import MarginBreakdown, cents_to_float, to_cents
from services.events import emit_server_event


@dataclass(frozen=True)
class RequestedLine:
    menu_item_id: int
    quantity: int


@dataclass(frozen=True)
class PricedLine:
    menu_item_id: int
    name: str
    category: str
    quantity: int
    currency: str
    gross_unit_price_cents: int
    net_unit_price_cents: int
    ingredient_cost_cents: Optional[int]
    packaging_cost_cents: int

    @property
    def line_revenue_cents(self) -> int:
        return self.net_unit_price_cents * self.quantity

    @property
    def line_ingredient_cost_cents(self) -> Optional[int]:
        if self.ingredient_cost_cents is None:
            return None
        return self.ingredient_cost_cents * self.quantity

    @property
    def line_packaging_cost_cents(self) -> int:
        return self.packaging_cost_cents * self.quantity

    @property
    def line_margin_cents(self) -> Optional[int]:
        ingredient = self.line_ingredient_cost_cents
        if ingredient is None:
            return None
        return self.line_revenue_cents - ingredient - self.line_packaging_cost_cents

    def legacy_json(self) -> dict:
        return {
            "menuItemId": self.menu_item_id,
            "name": self.name,
            "quantity": self.quantity,
            "price": cents_to_float(self.net_unit_price_cents),
            "category": self.category,
        }


def normalize_requested_lines(lines: Iterable[RequestedLine]) -> list[RequestedLine]:
    combined: dict[int, int] = {}
    for line in lines:
        if line.quantity < 1 or line.quantity > 99:
            raise HTTPException(status_code=422, detail="Item quantity must be between 1 and 99")
        combined[line.menu_item_id] = combined.get(line.menu_item_id, 0) + line.quantity
        if combined[line.menu_item_id] > 99:
            raise HTTPException(status_code=422, detail="Combined item quantity cannot exceed 99")
    if not combined:
        raise HTTPException(status_code=422, detail="items must not be empty")
    return [RequestedLine(menu_item_id=item_id, quantity=quantity) for item_id, quantity in combined.items()]


def price_menu_lines(cursor, tenant_id: int, requested: Iterable[RequestedLine]) -> list[PricedLine]:
    normalized = normalize_requested_lines(requested)
    item_ids = [line.menu_item_id for line in normalized]
    cursor.execute(
        """SELECT id, name, category, currency,
                  COALESCE(price_cents, round(price * 100)::bigint),
                  COALESCE(sale_price_cents,
                           CASE WHEN sale_price IS NULL THEN NULL ELSE round(sale_price * 100)::bigint END),
                  ingredient_cost_cents, COALESCE(packaging_cost_cents, 0), is_available
           FROM menu_items
           WHERE restaurant_id = %s AND id = ANY(%s)""",
        (tenant_id, item_ids),
    )
    rows = {int(row[0]): row for row in cursor.fetchall()}
    if set(item_ids) != set(rows):
        raise HTTPException(status_code=422, detail="One or more menu items do not belong to this restaurant")

    priced: list[PricedLine] = []
    for request_line in normalized:
        row = rows[request_line.menu_item_id]
        if not row[8]:
            raise HTTPException(status_code=409, detail=f"{row[1]} is currently unavailable")
        gross_cents = int(row[4])
        sale_cents = int(row[5]) if row[5] is not None else None
        net_cents = min(gross_cents, sale_cents) if sale_cents is not None else gross_cents
        priced.append(
            PricedLine(
                menu_item_id=int(row[0]), name=row[1], category=row[2] or "",
                quantity=request_line.quantity, currency=(row[3] or "USD").upper(),
                gross_unit_price_cents=gross_cents, net_unit_price_cents=net_cents,
                ingredient_cost_cents=int(row[6]) if row[6] is not None else None,
                packaging_cost_cents=int(row[7] or 0),
            )
        )
    currencies = {line.currency for line in priced}
    if len(currencies) != 1:
        raise HTTPException(status_code=409, detail="Cart contains mixed currencies")
    return priced


def load_money_setting_cents(cursor, tenant_id: int, key: str, default: str = "0") -> int:
    cursor.execute("SELECT value FROM settings WHERE restaurant_id = %s AND key = %s", (tenant_id, key))
    row = cursor.fetchone()
    try:
        return max(0, to_cents(row[0] if row else default))
    except ValueError:
        return max(0, to_cents(default))


def generate_order_id() -> str:
    return f"FH-{secrets.randbelow(900000) + 100000}"


def persist_cart_snapshot(
    cursor,
    *,
    tenant_id: int,
    cart_id: str,
    visitor_id: str,
    session_id: str,
    customer_id: Optional[str],
    user_id: Optional[str],
    lines: list[PricedLine],
) -> None:
    currency = lines[0].currency
    subtotal_cents = sum(line.line_revenue_cents for line in lines)
    cursor.execute(
        """INSERT INTO carts
           (id, tenant_id, visitor_id, session_id, customer_id, user_id, currency, status, subtotal_cents)
           VALUES (%s,%s,%s,%s,%s,%s,%s,'active',%s)
           ON CONFLICT (id) DO UPDATE SET
             visitor_id = EXCLUDED.visitor_id, session_id = EXCLUDED.session_id,
             customer_id = COALESCE(EXCLUDED.customer_id, carts.customer_id),
             user_id = COALESCE(EXCLUDED.user_id, carts.user_id),
             currency = EXCLUDED.currency, subtotal_cents = EXCLUDED.subtotal_cents,
             status = 'active', updated_at = NOW()
           WHERE carts.tenant_id = EXCLUDED.tenant_id""",
        (cart_id, tenant_id, visitor_id, session_id, customer_id, user_id, currency, subtotal_cents),
    )
    cursor.execute("DELETE FROM cart_lines WHERE tenant_id = %s AND cart_id = %s", (tenant_id, cart_id))
    for line in lines:
        cursor.execute(
            """INSERT INTO cart_lines
               (tenant_id, cart_id, menu_item_id, quantity, unit_price_cents, line_total_cents)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (tenant_id, cart_id, line.menu_item_id, line.quantity, line.net_unit_price_cents, line.line_revenue_cents),
        )


def persist_order_items(cursor, *, tenant_id: int, order_id: str, lines: list[PricedLine]) -> None:
    for line in lines:
        snapshot = {
            "menuItemId": line.menu_item_id,
            "name": line.name,
            "category": line.category,
            "currency": line.currency,
            "grossUnitPriceCents": line.gross_unit_price_cents,
            "netUnitPriceCents": line.net_unit_price_cents,
            "ingredientCostCents": line.ingredient_cost_cents,
            "packagingCostCents": line.packaging_cost_cents,
        }
        cursor.execute(
            """INSERT INTO order_line_items
               (tenant_id, order_id, menu_item_id, item_name, category_name, quantity, currency,
                gross_unit_price_cents, discount_cents, net_unit_price_cents,
                ingredient_cost_cents, packaging_cost_cents, line_revenue_cents,
                line_contribution_margin_cents, snapshot)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
            (
                tenant_id, order_id, line.menu_item_id, line.name, line.category, line.quantity,
                line.currency, line.gross_unit_price_cents,
                (line.gross_unit_price_cents - line.net_unit_price_cents) * line.quantity,
                line.net_unit_price_cents, line.ingredient_cost_cents, line.packaging_cost_cents,
                line.line_revenue_cents, line.line_margin_cents, json.dumps(snapshot),
            ),
        )


def calculate_order_margin(
    lines: list[PricedLine],
    *,
    revenue_cents: int,
    payment_cost_cents: int = 0,
    commission_cents: int = 0,
    refund_cents: int = 0,
) -> Optional[MarginBreakdown]:
    ingredient_costs = [line.line_ingredient_cost_cents for line in lines]
    if any(cost is None for cost in ingredient_costs):
        return None
    return MarginBreakdown(
        revenue_cents=revenue_cents,
        ingredient_cost_cents=sum(int(cost or 0) for cost in ingredient_costs),
        packaging_cost_cents=sum(line.line_packaging_cost_cents for line in lines),
        payment_cost_cents=payment_cost_cents,
        commission_cents=commission_cents,
        refund_cents=refund_cents,
    )


def mark_cart_converted(cursor, *, tenant_id: int, cart_id: str) -> None:
    cursor.execute(
        """UPDATE carts SET status = 'converted', converted_at = NOW(), updated_at = NOW()
           WHERE tenant_id = %s AND id = %s""",
        (tenant_id, cart_id),
    )


def emit_order_created(
    cursor,
    *,
    tenant_id: int,
    order_id: str,
    cart_id: str,
    visitor_id: str,
    session_id: str,
    customer_id: Optional[str],
    location_id: Optional[int],
    total_cents: int,
    currency: str,
) -> None:
    emit_server_event(
        cursor,
        tenant_id=tenant_id,
        event_id=f"order-created:{order_id}",
        event_name="order_created",
        visitor_id=visitor_id,
        session_id=session_id,
        customer_id=customer_id,
        location_id=location_id,
        cart_id=cart_id,
        order_id=order_id,
        properties={"totalCents": total_cents, "currency": currency},
        consent_state="essential",
    )
