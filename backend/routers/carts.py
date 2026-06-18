from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from db import get_db
from dependencies.auth import TenantContext, TokenData, get_optional_current_user, resolve_public_tenant
from services.commerce import RequestedLine, persist_cart_snapshot, price_menu_lines
from services.consent import ensure_customer_with_cursor
from services.events import emit_server_event

router = APIRouter()


class CartLineInput(BaseModel):
    menuItemId: int
    quantity: int = Field(ge=1, le=99)


class CartSyncRequest(BaseModel):
    cartId: str = Field(min_length=8, max_length=100)
    visitorId: str = Field(min_length=8, max_length=100)
    sessionId: str = Field(min_length=8, max_length=100)
    items: list[CartLineInput] = Field(max_length=100)


@router.post("/carts/sync")
def sync_cart(
    body: CartSyncRequest,
    tenant: TenantContext = Depends(resolve_public_tenant),
    user: Optional[TokenData] = Depends(get_optional_current_user),
):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM carts WHERE tenant_id = %s AND id = %s", (tenant.id, body.cartId))
            existed = cur.fetchone() is not None
            if not body.items:
                if existed:
                    cur.execute(
                        "UPDATE carts SET status = 'expired', subtotal_cents = 0, updated_at = NOW() WHERE tenant_id = %s AND id = %s AND status = 'active'",
                        (tenant.id, body.cartId),
                    )
                    cur.execute("DELETE FROM cart_lines WHERE tenant_id = %s AND cart_id = %s", (tenant.id, body.cartId))
                return {"cartId": body.cartId, "currency": None, "subtotalCents": 0, "items": []}
            lines = price_menu_lines(
                cur,
                tenant.id,
                [RequestedLine(menu_item_id=item.menuItemId, quantity=item.quantity) for item in body.items],
            )
            customer_id = None
            if user:
                customer_id = ensure_customer_with_cursor(cur, tenant.id, user.id, user.email)
            persist_cart_snapshot(
                cur,
                tenant_id=tenant.id,
                cart_id=body.cartId,
                visitor_id=body.visitorId,
                session_id=body.sessionId,
                customer_id=customer_id,
                user_id=user.id if user else None,
                lines=lines,
            )
            if not existed:
                emit_server_event(
                    cur,
                    tenant_id=tenant.id,
                    event_id=f"cart-created:{body.cartId}",
                    event_name="cart_created",
                    visitor_id=body.visitorId,
                    session_id=body.sessionId,
                    customer_id=customer_id,
                    cart_id=body.cartId,
                    properties={"subtotalCents": sum(line.line_revenue_cents for line in lines), "currency": lines[0].currency},
                    consent_state="essential",
                )
    return {
        "cartId": body.cartId,
        "currency": lines[0].currency,
        "subtotalCents": sum(line.line_revenue_cents for line in lines),
        "items": [line.legacy_json() for line in lines],
    }
