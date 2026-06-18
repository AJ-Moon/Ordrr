"""Admin router — fully multi-tenant."""
import base64
import csv
import io
import json as _json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
import pypdf
import pypdfium2

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from jose import jwt
from pydantic import BaseModel

from db import get_db
from dependencies.auth import get_current_admin, get_restaurant_id
from services.audit import record_audit
from services.rate_limits import consume_auth_rate
from services.events import emit_server_event
from services.jobs import enqueue_job
from core.money import cents_to_float, to_cents

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_CHUNK_SIZE = 1024 * 1024
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
try:
    MAX_IMAGE_UPLOAD_BYTES = max(1, int(os.getenv("ADMIN_IMAGE_MAX_BYTES", str(5 * 1024 * 1024))))
except ValueError:
    MAX_IMAGE_UPLOAD_BYTES = 5 * 1024 * 1024

VALID_ORDER_STATUSES = [
    "placed", "confirmed", "preparing", "ready",
    "out_for_delivery", "delivered", "cancelled",
]

ORDER_PROGRESS_STATUSES = ["received", "preparing", "ready", "delivered"]


# ─────────────────────────────────────────────────────────────────────────────
# Auth helpers
# ─────────────────────────────────────────────────────────────────────────────

def _verify(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())


def _touch_admin_last_login(admin_id: str) -> None:
    """Best-effort last-login stamp; no-op if migration 0011 not yet applied."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE admin_users SET last_login_at = NOW() WHERE id = %s",
                    (admin_id,),
                )
    except Exception:
        pass


def _sign_admin_token(admin_id: str, email: str, role: str, restaurant_id: int) -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
    expire = datetime.utcnow() + timedelta(hours=12)
    return jwt.encode(
        {
            "id": admin_id,
            "email": email,
            "role": role,
            "type": "admin",
            "restaurant_id": restaurant_id,
            "exp": expire,
        },
        secret,
        algorithm="HS256",
    )


def _restaurant_id(admin: dict) -> int:
    return int(admin.get("restaurant_id", 1))


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────

class AdminLoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def admin_login(body: AdminLoginRequest, request: Request, rid: int = Depends(get_restaurant_id)):
    # Tenant resolved from: Host header → domains table → X-Restaurant-ID header → default 1.
    # On localhost, frontend sends X-Restaurant-ID header to select the tenant.
    consume_auth_rate(request, f"admin_login:{rid}", body.email)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, email, password_hash, name, role, restaurant_id
                   FROM admin_users WHERE email = %s AND restaurant_id = %s""",
                (body.email, rid),
            )
            row = cur.fetchone()
    if not row or not _verify(body.password, row[2]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    _touch_admin_last_login(str(row[0]))
    token = _sign_admin_token(str(row[0]), row[1], row[4], int(row[5]))
    return {
        "token": token,
        "admin": {
            "id": str(row[0]),
            "email": row[1],
            "name": row[3],
            "role": row[4],
            "restaurantId": int(row[5]),
        },
    }


@router.get("/me")
def admin_me(admin: dict = Depends(get_current_admin)):
    """Verify admin token and return current admin info."""
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, role FROM admin_users WHERE id = %s AND restaurant_id = %s",
                (admin["id"], rid),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Admin not found")
    return {"id": str(row[0]), "email": row[1], "name": row[2], "role": row[3], "restaurantId": rid}


@router.post("/logout")
def admin_logout(admin: dict = Depends(get_current_admin)):
    """Stateless logout acknowledgement (client must discard the token)."""
    return {"success": True, "message": "Logged out. Please discard your token."}


# ─────────────────────────────────────────────────────────────────────────────
# Orders helpers
# ─────────────────────────────────────────────────────────────────────────────

_ORDER_SELECT = """
    SELECT o.id, o.user_id,
           o.guest_name, o.guest_email, o.guest_phone,
           o.items,
           o.subtotal, o.discount_amount, o.delivery_charge, o.total,
           o.status, o.order_type, o.payment_method,
           o.address, o.notes,
           o.points_earned, o.points_redeemed,
           o.source, o.claim_status, o.claimed_by_user_id,
           o.created_at,
           b.name as branch_name,
           COALESCE(u.first_name || ' ' || u.last_name, '') as user_full_name,
           COALESCE(u.phone, '') as user_phone,
           o.branch_id
    FROM orders o
    LEFT JOIN branches b ON b.id = o.branch_id
    LEFT JOIN users u ON u.id = o.user_id
"""


def _order_row(r: tuple) -> dict:
    items = r[5]
    if isinstance(items, str):
        items = _json.loads(items)
    return {
        "id": r[0],
        "userId": r[1] or "",
        "guestName": r[2] or "",
        "guestEmail": r[3] or "",
        "guestPhone": r[4] or "",
        "items": items,
        "subtotal": float(r[6] or 0),
        "discountAmount": float(r[7] or 0),
        "deliveryCharge": float(r[8] or 0),
        "total": float(r[9] or 0),
        "status": r[10] or "placed",
        "orderType": r[11] or "delivery",
        "paymentMethod": r[12] or "cash",
        "address": r[13] or "",
        "notes": r[14] or "",
        "pointsEarned": r[15] or 0,
        "pointsRedeemed": r[16] or 0,
        "source": r[17] or "online",
        "claimStatus": r[18] or "unclaimed",
        "claimedByUserId": r[19] or "",
        "createdAt": r[20].isoformat() if r[20] else "",
        "branchName": r[21] or "",
        "customerName": r[22].strip() or r[2] or "Guest",
        "customerPhone": r[23] or r[4] or "",
        "branchId": r[24],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Current Orders (active / in-kitchen)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orders/current")
def admin_current_orders(admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                _ORDER_SELECT +
                "WHERE o.restaurant_id = %s AND o.status NOT IN ('delivered','cancelled') "
                "ORDER BY o.created_at DESC",
                (rid,),
            )
            rows = cur.fetchall()
    return [_order_row(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Finished Orders (with search / filter / CSV)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orders/finished")
def admin_finished_orders(
    search: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    branch_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    payment_method: Optional[str] = Query(None),
    export: Optional[str] = Query(None),   # "csv"
    admin: dict = Depends(get_current_admin),
):
    rid = _restaurant_id(admin)
    query = _ORDER_SELECT + " WHERE o.restaurant_id = %s AND o.status IN ('delivered','cancelled')"
    params: list = [rid]

    if search:
        query += " AND (o.id ILIKE %s OR o.guest_phone ILIKE %s OR o.guest_name ILIKE %s OR u.phone ILIKE %s OR (u.first_name || ' ' || u.last_name) ILIKE %s)"
        s = f"%{search}%"
        params += [s, s, s, s, s]
    if date_from:
        query += " AND o.created_at >= %s"
        params.append(date_from)
    if date_to:
        query += " AND o.created_at <= %s"
        params.append(date_to + "T23:59:59")
    if branch_id:
        query += " AND o.branch_id = %s"
        params.append(branch_id)
    if status:
        query += " AND o.status = %s"
        params.append(status)
    if payment_method:
        query += " AND o.payment_method = %s"
        params.append(payment_method)

    query += " ORDER BY o.created_at DESC"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    orders = [_order_row(r) for r in rows]

    if export == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Order ID", "Customer", "Phone", "Branch", "Date", "Items",
            "Subtotal", "Discount", "Delivery", "Total", "Status", "Payment", "Source",
        ])
        for o in orders:
            items_str = "; ".join(f"{i['quantity']}x {i['name']}" for i in o["items"])
            writer.writerow([
                o["id"], o["customerName"], o["customerPhone"], o["branchName"],
                o["createdAt"], items_str,
                o["subtotal"], o["discountAmount"], o["deliveryCharge"], o["total"],
                o["status"], o["paymentMethod"], o["source"],
            ])
        csv_data = output.getvalue()
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=orders.csv"},
        )

    return orders


# ─────────────────────────────────────────────────────────────────────────────
# All orders
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orders/all")
def admin_all_orders(
    status: Optional[str] = None,
    admin: dict = Depends(get_current_admin),
):
    rid = _restaurant_id(admin)
    query = _ORDER_SELECT + " WHERE o.restaurant_id = %s"
    params: list = [rid]
    if status:
        query += " AND o.status = %s"
        params.append(status)
    query += " ORDER BY o.created_at DESC"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    return [_order_row(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Update order status
# ─────────────────────────────────────────────────────────────────────────────

class StatusUpdate(BaseModel):
    status: str


@router.patch("/orders/{order_id}/status")
@router.put("/orders/{order_id}/status")
def admin_update_order_status(
    order_id: str,
    body: StatusUpdate,
    admin: dict = Depends(get_current_admin),
):
    status = (body.status or "").strip().lower()
    if status not in ORDER_PROGRESS_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of {ORDER_PROGRESS_STATUSES}",
        )

    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT status, visitor_id, session_id, cart_id, branch_id, total_cents, currency
                   FROM orders WHERE id = %s AND restaurant_id = %s FOR UPDATE""",
                (order_id, rid),
            )
            existing_order = cur.fetchone()
            if not existing_order:
                raise HTTPException(status_code=404, detail="Order not found")
            previous_status = existing_order[0]
            cur.execute(
                "UPDATE orders SET status = %s, completed_at = CASE WHEN %s = 'delivered' THEN COALESCE(completed_at, NOW()) ELSE completed_at END, updated_at = NOW() "
                "WHERE id = %s AND restaurant_id = %s RETURNING id",
                (status, status, order_id, rid),
            )
            cur.fetchone()

            # Award points when order is delivered — single transaction so
            # a points failure rolls back the status update too.
            if status == "delivered" and previous_status != "delivered":
                cur.execute(
                    "SELECT user_id, subtotal FROM orders WHERE id = %s AND restaurant_id = %s",
                    (order_id, rid),
                )
                orow = cur.fetchone()
                if orow:
                    user_id, subtotal = orow
                    if user_id:
                        from routers.orders import _get_rewards_program_settings, _safe_int, _get_setting
                        rewards_cfg = _get_rewards_program_settings(cur, rid)
                        if rewards_cfg["rewards_enabled"]:
                            points_earned = int(float(subtotal or 0) * rewards_cfg["points_per_dollar"])
                            if points_earned > 0:
                                expiry_months = max(1, _safe_int(
                                    _get_setting(cur, "points_expiry_months", rid, "12"), 12
                                ))
                                cur.execute(
                                    """UPDATE orders SET points_earned = %s, updated_at = NOW()
                                       WHERE id = %s AND restaurant_id = %s""",
                                    (points_earned, order_id, rid),
                                )
                                cur.execute(
                                    f"""INSERT INTO points (user_id, restaurant_id, points) VALUES (%s, %s, %s)
                                       ON CONFLICT (user_id, restaurant_id) DO UPDATE
                                       SET points = points.points + %s,
                                           expires_at = NOW() + INTERVAL '{expiry_months} months',
                                           updated_at = NOW()
                                       RETURNING points""",
                                    (user_id, rid, points_earned, points_earned),
                                )
                                bal_row = cur.fetchone()
                                balance_after = bal_row[0] if bal_row else points_earned
                                cur.execute(
                                    """INSERT INTO points_transactions
                                       (user_id, restaurant_id, order_id, type, points, balance_after)
                                       VALUES (%s, %s, %s, 'earn', %s, %s)""",
                                    (user_id, rid, order_id, points_earned, balance_after),
                                )

                emit_server_event(
                    cur,
                    tenant_id=rid,
                    event_id=f"order-completed:{order_id}",
                    event_name="order_completed",
                    visitor_id=existing_order[1] or "server",
                    session_id=existing_order[2] or "server",
                    cart_id=existing_order[3],
                    location_id=existing_order[4],
                    order_id=order_id,
                    properties={
                        "totalCents": int(existing_order[5] or 0),
                        "currency": existing_order[6] or "USD",
                    },
                    consent_state="essential",
                )
                enqueue_job(
                    cur,
                    tenant_id=rid,
                    job_name="analytics.aggregate_daily",
                    idempotency_key=f"order-completed:{order_id}",
                    metadata={"orderId": order_id},
                )

            cur.execute(
                _ORDER_SELECT + " WHERE o.id = %s AND o.restaurant_id = %s",
                (order_id, rid),
            )
            updated = cur.fetchone()

    if not updated:
        raise HTTPException(status_code=404, detail="Order not found")

    return _order_row(updated)


# ─────────────────────────────────────────────────────────────────────────────
# Users / Customer Records
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/users")
def admin_list_users(
    search: Optional[str] = Query(None),
    admin: dict = Depends(get_current_admin),
):
    rid = _restaurant_id(admin)
    query = """
        SELECT
            u.id, u.email, u.first_name, u.last_name, u.phone, u.created_at,
            COALESCE(p.points, 0) AS points,
            COUNT(o.id) AS total_orders,
            COALESCE(SUM(CASE WHEN o.status != 'cancelled' THEN o.total ELSE 0 END), 0) AS total_spent,
            MAX(o.created_at) AS last_order_at
        FROM users u
        LEFT JOIN points p ON p.user_id = u.id AND p.restaurant_id = u.restaurant_id
        LEFT JOIN orders o ON o.user_id = u.id AND o.restaurant_id = u.restaurant_id
        WHERE u.restaurant_id = %s
    """
    params: list = [rid]
    if search:
        query += " AND (u.email ILIKE %s OR u.first_name ILIKE %s OR u.last_name ILIKE %s OR u.phone ILIKE %s)"
        s = f"%{search}%"
        params += [s, s, s, s]
    query += " GROUP BY u.id, u.email, u.first_name, u.last_name, u.phone, u.created_at, p.points ORDER BY last_order_at DESC NULLS LAST"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    return [
        {
            "id": r[0],
            "email": r[1],
            "firstName": r[2] or "",
            "lastName": r[3] or "",
            "phone": r[4] or "",
            "createdAt": r[5].isoformat() if r[5] else "",
            "points": int(r[6]),
            "totalOrders": int(r[7]),
            "totalSpent": float(r[8]),
            "lastOrderAt": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]


@router.get("/users/{user_id}")
def admin_user_detail(user_id: str, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            # Basic user info
            cur.execute(
                "SELECT id, email, first_name, last_name, phone, created_at "
                "FROM users WHERE id = %s AND restaurant_id = %s",
                (user_id, rid),
            )
            user_row = cur.fetchone()
            if not user_row:
                raise HTTPException(status_code=404, detail="User not found")

            # Points
            cur.execute(
                "SELECT points FROM points WHERE user_id = %s AND restaurant_id = %s",
                (user_id, rid),
            )
            pts_row = cur.fetchone()
            points = int(pts_row[0]) if pts_row else 0

            # All orders
            cur.execute(
                _ORDER_SELECT +
                " WHERE o.restaurant_id = %s AND (o.user_id = %s OR o.claimed_by_user_id = %s)"
                " ORDER BY o.created_at DESC",
                (rid, user_id, user_id),
            )
            order_rows = cur.fetchall()
            orders = [_order_row(r) for r in order_rows]

    # Aggregate stats from orders
    completed = [o for o in orders if o["status"] not in ("cancelled",)]
    total_spent = sum(o["total"] for o in completed)
    total_orders = len(orders)
    avg_order = total_spent / len(completed) if completed else 0
    first_order = min((o["createdAt"] for o in orders), default=None)
    last_order = max((o["createdAt"] for o in orders), default=None)

    # Category & item breakdown from JSONB items
    cat_totals: dict = {}
    item_totals: dict = {}
    for o in completed:
        for item in o.get("items", []):
            name = item.get("name", "")
            cat = item.get("category", "Uncategorized")
            qty = int(item.get("quantity", 1))
            price = float(item.get("price", 0))
            spend = qty * price

            cat_totals.setdefault(cat, {"category": cat, "quantity": 0, "totalSpent": 0.0, "topItem": ""})
            cat_totals[cat]["quantity"] += qty
            cat_totals[cat]["totalSpent"] += spend

            item_key = (name, cat)
            item_totals.setdefault(item_key, {"name": name, "category": cat, "quantity": 0, "totalSpent": 0.0, "lastOrdered": ""})
            item_totals[item_key]["quantity"] += qty
            item_totals[item_key]["totalSpent"] += spend
            if o["createdAt"] > item_totals[item_key]["lastOrdered"]:
                item_totals[item_key]["lastOrdered"] = o["createdAt"]

    # Set topItem per category
    for cat, cd in cat_totals.items():
        top = max(
            (v for k, v in item_totals.items() if k[1] == cat),
            key=lambda x: x["quantity"],
            default=None,
        )
        cd["topItem"] = top["name"] if top else ""

    # Favorite category
    fav_cat = max(cat_totals.values(), key=lambda x: x["quantity"], default={})
    favorite_category = fav_cat.get("category", "")

    category_breakdown = sorted(cat_totals.values(), key=lambda x: x["quantity"], reverse=True)
    item_breakdown = sorted(item_totals.values(), key=lambda x: x["quantity"], reverse=True)
    for it in item_breakdown:
        it["totalSpent"] = round(it["totalSpent"], 2)
    for cb in category_breakdown:
        cb["totalSpent"] = round(cb["totalSpent"], 2)

    return {
        "user": {
            "id": user_row[0],
            "email": user_row[1],
            "firstName": user_row[2] or "",
            "lastName": user_row[3] or "",
            "phone": user_row[4] or "",
            "createdAt": user_row[5].isoformat() if user_row[5] else "",
            "points": points,
        },
        "summary": {
            "totalOrders": total_orders,
            "totalSpent": round(total_spent, 2),
            "avgOrderValue": round(avg_order, 2),
            "firstOrder": first_order,
            "lastOrder": last_order,
            "favoriteCategory": favorite_category,
        },
        "categoryBreakdown": category_breakdown,
        "itemBreakdown": item_breakdown,
        "orders": orders,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Menu Items
# ─────────────────────────────────────────────────────────────────────────────

def _delete_upload(image_path: str) -> None:
    """Silently delete a local upload file given its /static/uploads/... path."""
    if not image_path or not image_path.startswith("/static/uploads/"):
        return
    filename = Path(image_path).name
    # Guard against path traversal — filename must be a simple file, no slashes
    if "/" in filename or "\\" in filename or not filename:
        return
    target = UPLOADS_DIR / filename
    try:
        if target.exists() and target.is_file():
            target.unlink()
    except Exception:
        pass  # Never fail the request because of a cleanup error


def _row_to_menu_item(r):
    return {
        "id": r[0], "category": r[1], "name": r[2], "description": r[3],
        "price": float(r[4]),
        "salePrice": float(r[5]) if r[5] is not None else None,
        "image": r[6] or "", "rating": float(r[7] or 0),
        "isSpicy": r[8], "isPopular": r[9],
        "isFeatured": r[10], "isAvailable": r[11],
        "displayOrder": r[12],
        "currency": r[13] or "USD",
        "ingredientCost": cents_to_float(r[14]) if r[14] is not None else None,
        "packagingCost": cents_to_float(r[15]),
    }


@router.get("/menu")
def admin_get_menu(admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, category, name, description, price, sale_price, image, rating,
                         is_spicy, is_popular, is_featured, is_available, display_order,
                         currency, ingredient_cost_cents, packaging_cost_cents
                     FROM menu_items
                     WHERE restaurant_id = %s
                     ORDER BY category, display_order ASC NULLS LAST, name""",
                (rid,),
            )
            rows = cur.fetchall()
    return [_row_to_menu_item(r) for r in rows]


class MenuItemBody(BaseModel):
    category: str
    name: str
    description: str = ""
    price: float
    salePrice: Optional[float] = None
    image: str = ""
    rating: float = 0
    isSpicy: bool = False
    isPopular: bool = False
    isFeatured: bool = False
    isAvailable: bool = True
    displayOrder: Optional[int] = None
    currency: str = "USD"
    ingredientCost: Optional[float] = None
    packagingCost: float = 0


class MenuReorderBody(BaseModel):
    ordered_ids: list[int]


def _matches_image_signature(content_type: str, header: bytes) -> bool:
    if content_type in {"image/jpeg", "image/jpg"}:
        return header.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/gif":
        return header.startswith(b"GIF87a") or header.startswith(b"GIF89a")
    if content_type == "image/webp":
        return len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    return False


@router.post("/upload-image")
async def admin_upload_image(
    file: UploadFile = File(...),
    admin: dict = Depends(get_current_admin),
):
    _ = admin

    content_type = (file.content_type or "").lower().strip()
    if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported image content type")

    first_chunk = await file.read(UPLOAD_CHUNK_SIZE)
    if not first_chunk:
        raise HTTPException(status_code=400, detail="Empty file upload")

    if not _matches_image_signature(content_type, first_chunk):
        raise HTTPException(status_code=400, detail="Invalid image file")

    total_bytes = len(first_chunk)
    if total_bytes > MAX_IMAGE_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded image exceeds max size limit")

    ext = ALLOWED_IMAGE_CONTENT_TYPES[content_type]

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    destination = UPLOADS_DIR / filename

    try:
        with destination.open("wb") as out_file:
            out_file.write(first_chunk)
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_IMAGE_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Uploaded image exceeds max size limit")
                out_file.write(chunk)
    except HTTPException:
        if destination.exists():
            destination.unlink()
        raise
    except Exception:
        if destination.exists():
            destination.unlink()
        raise HTTPException(status_code=500, detail="Failed to save image")
    finally:
        await file.close()

    return {"url": f"/static/uploads/{filename}"}


PARSE_MENU_ALLOWED_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp",
    "application/pdf", "text/plain",
}
PARSE_MENU_MAX_BYTES = 20 * 1024 * 1024  # 20 MB
PARSE_MENU_SYSTEM_PROMPT = (
    'You are a menu parser. Extract all menu items from the provided menu '
    '(image, PDF, or text). Return ONLY a valid JSON array — no markdown, no explanation. '
    'Each object must have exactly these keys: "name" (string), '
    '"description" (string, empty string if not found), '
    '"category" (string, lowercase singular — e.g. "burger" not "Burgers"), '
    '"price" (number, no currency symbol), '
    '"isSpicy" (boolean), "isPopular" (boolean, default false). '
    'If a price is a range, use the lower price.'
)


@router.post("/parse-menu")
async def admin_parse_menu(
    file: Optional[UploadFile] = File(None),
    text: str = Form(""),
    admin: dict = Depends(get_current_admin),
):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Menu parsing is not configured (missing OPENAI_API_KEY on the server)",
        )

    content_parts: list = []

    if file and file.filename:
        content_type = (file.content_type or "").lower().strip()
        if content_type not in PARSE_MENU_ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Use JPG, PNG, WebP, PDF, or TXT.",
            )
        raw = await file.read()
        if len(raw) > PARSE_MENU_MAX_BYTES:
            raise HTTPException(status_code=413, detail="File too large (max 20 MB)")

        if content_type.startswith("image/"):
            b64 = base64.b64encode(raw).decode()
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:{content_type};base64,{b64}"},
            })
            content_parts.append({"type": "text", "text": "Parse this menu image and return JSON only."})
        elif content_type == "application/pdf":
            try:
                reader = pypdf.PdfReader(io.BytesIO(raw))
                pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
            except Exception:
                pdf_text = ""

            if pdf_text:
                # Text-based PDF — send as text (fast, cheap)
                content_parts.append({
                    "type": "text",
                    "text": f"Parse this menu text and return JSON only:\n\n{pdf_text}",
                })
            else:
                # Image-based PDF (Canva, scanned, etc.) — render pages as images
                try:
                    pdf_doc = pypdfium2.PdfDocument(raw)
                    page_count = len(pdf_doc)
                    if page_count == 0:
                        raise HTTPException(status_code=422, detail="PDF has no pages.")
                    # Cap at 6 pages to stay within token limits
                    pages_to_render = min(page_count, 6)
                    content_parts.append({
                        "type": "text",
                        "text": f"This menu PDF has {page_count} page(s). Parse all items visible in the images below and return JSON only.",
                    })
                    for i in range(pages_to_render):
                        page = pdf_doc[i]
                        bitmap = page.render(scale=2.0)  # 2x = ~144 dpi, clear enough for GPT
                        pil_img = bitmap.to_pil()
                        buf = io.BytesIO()
                        pil_img.save(buf, format="PNG")
                        b64 = base64.b64encode(buf.getvalue()).decode()
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        })
                except HTTPException:
                    raise
                except Exception as exc:
                    raise HTTPException(
                        status_code=422,
                        detail="Could not render PDF pages. Try uploading a JPG/PNG photo of your menu instead.",
                    )
        else:
            file_text = raw.decode("utf-8", errors="replace")
            content_parts.append({
                "type": "text",
                "text": f"Parse this menu text and return JSON only:\n\n{file_text}",
            })

    if text.strip():
        content_parts.append({
            "type": "text",
            "text": f"Additional menu text to parse:\n\n{text.strip()}",
        })

    if not content_parts:
        raise HTTPException(status_code=400, detail="Upload a file or provide menu text.")

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 4096,
                    "messages": [
                        {"role": "system", "content": PARSE_MENU_SYSTEM_PROMPT},
                        {"role": "user", "content": content_parts},
                    ],
                },
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Menu parsing timed out. Please try again.")
    except Exception:
        raise HTTPException(status_code=502, detail="Could not reach the parsing service. Check your connection.")

    if not resp.is_success:
        raise HTTPException(
            status_code=502,
            detail="Menu parsing failed. Try a clearer image or paste the text manually.",
        )

    raw_text: str = (
        resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    )

    # Strip markdown code fences if the model wraps the JSON
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]

    try:
        parsed = _json.loads(cleaned)
        if not isinstance(parsed, list):
            raise ValueError("Not a list")
    except Exception:
        start, end = cleaned.find("["), cleaned.rfind("]")
        if start < 0 or end <= start:
            raise HTTPException(
                status_code=422,
                detail="Could not parse the menu response. Try a clearer image or paste the text manually.",
            )
        try:
            parsed = _json.loads(cleaned[start : end + 1])
        except Exception:
            raise HTTPException(
                status_code=422,
                detail="Could not parse the menu response. Try a clearer image or paste the text manually.",
            )

    items = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        try:
            price = max(0.0, float(entry.get("price", 0)))
        except (TypeError, ValueError):
            price = 0.0
        items.append({
            "name": name,
            "description": str(entry.get("description", "")).strip(),
            "category": str(entry.get("category", "uncategorized")).strip().lower(),
            "price": price,
            "isSpicy": bool(entry.get("isSpicy", False)),
            "isPopular": bool(entry.get("isPopular", False)),
        })

    if not items:
        raise HTTPException(
            status_code=422,
            detail="No menu items found. Try a clearer image or paste the text manually.",
        )

    return {"items": items}


@router.post("/menu", status_code=201)
def admin_create_menu_item(body: MenuItemBody, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(MAX(display_order), 0) + 1
                FROM menu_items
                WHERE restaurant_id = %s AND category = %s
                """,
                (rid, body.category),
            )
            next_display_order = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO menu_items (restaurant_id, category, name, description, price, sale_price,
                   image, rating, is_spicy, is_popular, is_featured, is_available, display_order,
                   currency, price_cents, sale_price_cents, ingredient_cost_cents, packaging_cost_cents)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id, category, name, description, price, sale_price, image, rating,
                         is_spicy, is_popular, is_featured, is_available, display_order,
                         currency, ingredient_cost_cents, packaging_cost_cents""",
                (rid, body.category, body.name, body.description, body.price, body.salePrice,
                 body.image, body.rating, body.isSpicy, body.isPopular, body.isFeatured,
                 body.isAvailable, body.displayOrder or next_display_order,
                 body.currency.upper(), to_cents(body.price),
                 to_cents(body.salePrice) if body.salePrice is not None else None,
                 to_cents(body.ingredientCost) if body.ingredientCost is not None else None,
                 to_cents(body.packagingCost)),
            )
            created_row = cur.fetchone()
            record_audit(
                cur,
                tenant_id=rid,
                actor_type="admin",
                actor_id=str(admin["id"]),
                action="menu_item.created",
                resource_type="menu_item",
                resource_id=str(created_row[0]),
                after=body.model_dump(),
            )
    return _row_to_menu_item(created_row)


@router.patch("/menu/reorder")
def admin_reorder_menu_items(body: MenuReorderBody, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    ids = body.ordered_ids
    if not ids:
        return {"success": True}

    unique_ids = list(dict.fromkeys(ids))
    if len(unique_ids) != len(ids):
        raise HTTPException(status_code=400, detail="ordered_ids contains duplicates")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM menu_items WHERE restaurant_id = %s AND id = ANY(%s)",
                (rid, ids),
            )
            found_ids = {row[0] for row in cur.fetchall()}
            if len(found_ids) != len(ids):
                raise HTTPException(status_code=400, detail="One or more item ids are invalid")

            for position, item_id in enumerate(ids, start=1):
                cur.execute(
                    "UPDATE menu_items SET display_order = %s WHERE id = %s AND restaurant_id = %s",
                    (position, item_id, rid),
                )

    return {"success": True}


@router.put("/menu/{item_id}")
@router.patch("/menu/{item_id}")
def admin_update_menu_item(item_id: int, body: MenuItemBody, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            # Fetch current image before overwriting so we can clean up
            cur.execute(
                "SELECT image FROM menu_items WHERE id = %s AND restaurant_id = %s",
                (item_id, rid),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Item not found")
            old_image = existing[0] or ""

            cur.execute(
                """UPDATE menu_items SET category=%s, name=%s, description=%s, price=%s,
                   sale_price=%s, image=%s, rating=%s, is_spicy=%s, is_popular=%s,
                   is_featured=%s, is_available=%s, display_order=COALESCE(%s, display_order),
                   currency=%s, price_cents=%s, sale_price_cents=%s,
                   ingredient_cost_cents=%s, packaging_cost_cents=%s
                   WHERE id=%s AND restaurant_id=%s
                   RETURNING id, category, name, description, price, sale_price, image, rating,
                             is_spicy, is_popular, is_featured, is_available, display_order,
                             currency, ingredient_cost_cents, packaging_cost_cents""",
                (body.category, body.name, body.description, body.price, body.salePrice,
                 body.image, body.rating, body.isSpicy, body.isPopular,
                 body.isFeatured, body.isAvailable, body.displayOrder,
                 body.currency.upper(), to_cents(body.price),
                 to_cents(body.salePrice) if body.salePrice is not None else None,
                 to_cents(body.ingredientCost) if body.ingredientCost is not None else None,
                 to_cents(body.packagingCost), item_id, rid),
            )
            updated_row = cur.fetchone()
            record_audit(
                cur,
                tenant_id=rid,
                actor_type="admin",
                actor_id=str(admin["id"]),
                action="menu_item.updated",
                resource_type="menu_item",
                resource_id=str(item_id),
                after=body.model_dump(),
            )

    # Delete old local upload if the image was replaced with a different one
    if old_image and old_image != body.image:
        _delete_upload(old_image)

    return _row_to_menu_item(updated_row)


@router.delete("/menu/{item_id}", status_code=204)
def admin_delete_menu_item(item_id: int, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM menu_items WHERE id = %s AND restaurant_id = %s RETURNING id, image",
                (item_id, rid),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Item not found")
            record_audit(
                cur,
                tenant_id=rid,
                actor_type="admin",
                actor_id=str(admin["id"]),
                action="menu_item.deleted",
                resource_type="menu_item",
                resource_id=str(item_id),
            )
    _delete_upload(row[1] or "")


# ─────────────────────────────────────────────────────────────────────────────
# FAQs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/faqs")
def admin_get_faqs(admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, question, answer, category, order_index FROM faqs "
                "WHERE restaurant_id = %s ORDER BY order_index",
                (rid,),
            )
            rows = cur.fetchall()
    return [{"id": r[0], "question": r[1], "answer": r[2], "category": r[3], "orderIndex": r[4]} for r in rows]


class FaqBody(BaseModel):
    question: str
    answer: str
    category: str = "General"
    orderIndex: int = 0


@router.post("/faqs", status_code=201)
def admin_create_faq(body: FaqBody, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO faqs (restaurant_id, question, answer, category, order_index) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                (rid, body.question, body.answer, body.category, body.orderIndex),
            )
            new_id = cur.fetchone()[0]
    return {"id": new_id, **body.model_dump()}


@router.put("/faqs/{faq_id}")
def admin_update_faq(faq_id: int, body: FaqBody, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE faqs SET question=%s, answer=%s, category=%s, order_index=%s "
                "WHERE id=%s AND restaurant_id=%s RETURNING id",
                (body.question, body.answer, body.category, body.orderIndex, faq_id, rid),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="FAQ not found")
    return {"id": faq_id, **body.model_dump()}


@router.delete("/faqs/{faq_id}", status_code=204)
def admin_delete_faq(faq_id: int, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM faqs WHERE id=%s AND restaurant_id=%s RETURNING id",
                (faq_id, rid),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="FAQ not found")


# ─────────────────────────────────────────────────────────────────────────────
# Content Pages
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/content/{slug}")
def admin_get_content(slug: str, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT slug, title, content FROM content_pages WHERE restaurant_id=%s AND slug=%s",
                (rid, slug),
            )
            r = cur.fetchone()
    if not r:
        return {"slug": slug, "title": "", "content": ""}
    return {"slug": r[0], "title": r[1], "content": r[2]}


class ContentBody(BaseModel):
    title: str
    content: str


@router.put("/content/{slug}")
def admin_update_content(slug: str, body: ContentBody, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO content_pages (restaurant_id, slug, title, content)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (restaurant_id, slug)
                   DO UPDATE SET title=EXCLUDED.title, content=EXCLUDED.content, updated_at=NOW()""",
                (rid, slug, body.title, body.content),
            )
    return {"slug": slug, **body.model_dump()}


# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/settings")
def admin_get_settings(admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM settings WHERE restaurant_id=%s", (rid,))
            rows = cur.fetchall()
    return {r[0]: r[1] for r in rows}


class SettingsBody(BaseModel):
    model_config = {"extra": "allow"}

    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    hours: Optional[str] = None
    whatsapp: Optional[str] = None
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    twitter_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    youtube_url: Optional[str] = None
    delivery_charge: Optional[str] = None
    min_order_amount: Optional[str] = None
    points_on_guest: Optional[str] = None
    restaurant_open: Optional[str] = None
    announcement: Optional[str] = None
    announcement_active: Optional[str] = None
    points_per_dollar: Optional[str] = None
    min_redeem_points: Optional[str] = None
    points_value_cents: Optional[str] = None
    rewards_enabled: Optional[str] = None
    max_points_discount_percent: Optional[str] = None
    points_expiry_months: Optional[str] = None
    maps_embed: Optional[str] = None
    tagline: Optional[str] = None
    brand_name: Optional[str] = None
    delivery_radius_km: Optional[str] = None
    restaurant_lat: Optional[str] = None
    restaurant_lng: Optional[str] = None


@router.put("/settings")
def admin_update_settings(body: SettingsBody, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    with get_db() as conn:
        with conn.cursor() as cur:
            # executemany sends all upserts in a single round-trip instead of N
            cur.executemany(
                """INSERT INTO settings (restaurant_id, key, value) VALUES (%s,%s,%s)
                   ON CONFLICT (restaurant_id, key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()""",
                [(rid, key, str(value)) for key, value in updates.items()],
            )
            record_audit(
                cur,
                tenant_id=rid,
                actor_type="admin",
                actor_id=str(admin["id"]),
                action="settings.updated",
                resource_type="settings",
                resource_id=str(rid),
                after=updates,
            )
    return updates


# ─────────────────────────────────────────────────────────────────────────────
# Branches
# ─────────────────────────────────────────────────────────────────────────────

def _row_to_branch(r):
    return {
        "id": r[0], "name": r[1], "address": r[2], "city": r[3],
        "phone": r[4], "hours": r[5], "isOpen": r[6],
        "mapsUrl": r[7] or "", "isDefault": r[8] or False,
    }


@router.get("/branches")
def admin_get_branches(admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, address, city, phone, hours, is_open, maps_url, is_default "
                "FROM branches WHERE restaurant_id=%s ORDER BY id",
                (rid,),
            )
            rows = cur.fetchall()
    return [_row_to_branch(r) for r in rows]


class BranchBody(BaseModel):
    name: str
    address: str = ""
    city: str = ""
    phone: str = ""
    hours: str = ""
    mapsUrl: str = ""
    isOpen: bool = True
    isDefault: bool = False


@router.post("/branches", status_code=201)
def admin_create_branch(body: BranchBody, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO branches (restaurant_id, name, address, city, phone, hours, maps_url, is_open, is_default)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (rid, body.name, body.address, body.city, body.phone, body.hours, body.mapsUrl, body.isOpen, body.isDefault),
            )
            new_id = cur.fetchone()[0]
    return {"id": new_id, **body.model_dump()}


@router.put("/branches/{branch_id}")
def admin_update_branch(branch_id: int, body: BranchBody, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE branches SET name=%s, address=%s, city=%s, phone=%s,
                   hours=%s, maps_url=%s, is_open=%s, is_default=%s
                   WHERE id=%s AND restaurant_id=%s RETURNING id""",
                (body.name, body.address, body.city, body.phone,
                 body.hours, body.mapsUrl, body.isOpen, body.isDefault, branch_id, rid),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Branch not found")
    return {"id": branch_id, **body.model_dump()}


@router.delete("/branches/{branch_id}", status_code=204)
def admin_delete_branch(branch_id: int, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM branches WHERE id=%s AND restaurant_id=%s RETURNING id",
                (branch_id, rid),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Branch not found")


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def admin_dashboard(admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM orders WHERE restaurant_id=%s", (rid,))
            total_orders = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM orders WHERE restaurant_id=%s AND created_at::date = CURRENT_DATE", (rid,))
            today_orders = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM orders WHERE restaurant_id=%s AND status='placed'", (rid,))
            pending_orders = cur.fetchone()[0]

            cur.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE restaurant_id=%s AND status!='cancelled'", (rid,))
            total_revenue = float(cur.fetchone()[0])

            cur.execute(
                "SELECT COALESCE(SUM(total),0) FROM orders WHERE restaurant_id=%s AND created_at::date=CURRENT_DATE AND status!='cancelled'",
                (rid,),
            )
            today_revenue = float(cur.fetchone()[0])

            cur.execute("SELECT COUNT(DISTINCT id) FROM users WHERE restaurant_id=%s", (rid,))
            total_customers = cur.fetchone()[0]

            cur.execute("""
                SELECT name, SUM(qty) as total_qty FROM (
                    SELECT elem->>'name' as name, (elem->>'quantity')::int as qty
                    FROM orders, jsonb_array_elements(items) as elem
                    WHERE restaurant_id=%s AND created_at > NOW() - INTERVAL '30 days'
                ) sub GROUP BY name ORDER BY total_qty DESC LIMIT 5
            """, (rid,))
            popular_items = [{"name": r[0], "count": r[1]} for r in cur.fetchall()]

            cur.execute(
                "SELECT id, user_id, guest_name, total, status, created_at "
                "FROM orders WHERE restaurant_id=%s ORDER BY created_at DESC LIMIT 10",
                (rid,),
            )
            recent_orders = [
                {
                    "id": r[0], "userId": r[1], "guestName": r[2],
                    "total": float(r[3]), "status": r[4],
                    "createdAt": r[5].isoformat(),
                }
                for r in cur.fetchall()
            ]

            cur.execute("SELECT COUNT(*) FROM contact_messages WHERE restaurant_id=%s AND is_read=FALSE", (rid,))
            unread_messages = cur.fetchone()[0]

    return {
        "totalOrders": total_orders,
        "todayOrders": today_orders,
        "pendingOrders": pending_orders,
        "totalRevenue": total_revenue,
        "todayRevenue": today_revenue,
        "totalCustomers": total_customers,
        "popularItems": popular_items,
        "recentOrders": recent_orders,
        "unreadMessages": unread_messages,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Contact Messages
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/contact-messages")
def admin_get_contact_messages(admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, email, phone, subject, message, is_read, created_at "
                "FROM contact_messages WHERE restaurant_id=%s ORDER BY created_at DESC",
                (rid,),
            )
            rows = cur.fetchall()
    return [
        {
            "id": r[0], "name": r[1], "email": r[2], "phone": r[3] or "",
            "subject": r[4], "message": r[5],
            "isRead": r[6], "createdAt": r[7].isoformat(),
        }
        for r in rows
    ]


@router.patch("/contact-messages/{msg_id}/read")
def admin_mark_message_read(msg_id: int, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE contact_messages SET is_read=TRUE WHERE id=%s AND restaurant_id=%s RETURNING id",
                (msg_id, rid),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Message not found")
    return {"success": True}


@router.delete("/contact-messages/{msg_id}", status_code=204)
def admin_delete_message(msg_id: int, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM contact_messages WHERE id=%s AND restaurant_id=%s RETURNING id",
                (msg_id, rid),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Message not found")


# ─────────────────────────────────────────────────────────────────────────────
# Reward Settings
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/reward-settings")
def admin_get_reward_settings(admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, mode, points_per_unit, unit_amount, min_redeem,
                          max_discount, conversion_rate, eligible_category,
                          eligible_item_id, required_count, free_item_id, auto_apply,
                          claim_expiry_days, require_phone_match
                   FROM reward_settings WHERE restaurant_id=%s LIMIT 1""",
                (rid,),
            )
            r = cur.fetchone()
    if not r:
        return {}
    return {
        "id": r[0], "mode": r[1],
        "pointsPerUnit": float(r[2]), "unitAmount": float(r[3]),
        "minRedeem": r[4], "maxDiscount": float(r[5]),
        "conversionRate": float(r[6]),
        "eligibleCategory": r[7], "eligibleItemId": r[8],
        "requiredCount": r[9], "freeItemId": r[10],
        "autoApply": r[11],
        "claimExpiryDays": r[12] or 30,
        "requirePhoneMatch": r[13] or False,
    }


class RewardSettingsBody(BaseModel):
    mode: str = "points"
    pointsPerUnit: float = 1
    unitAmount: float = 100
    minRedeem: int = 100
    maxDiscount: float = 500
    conversionRate: float = 1.0
    eligibleCategory: Optional[str] = None
    eligibleItemId: Optional[int] = None
    requiredCount: int = 10
    freeItemId: Optional[int] = None
    autoApply: bool = False
    claimExpiryDays: int = 30
    requirePhoneMatch: bool = False


@router.put("/reward-settings")
def admin_update_reward_settings(body: RewardSettingsBody, admin: dict = Depends(get_current_admin)):
    if body.mode not in {"points", "item-count"}:
        raise HTTPException(status_code=400, detail="mode must be 'points' or 'item-count'")
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM reward_settings WHERE restaurant_id=%s LIMIT 1", (rid,))
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    """UPDATE reward_settings SET
                       mode=%s, points_per_unit=%s, unit_amount=%s, min_redeem=%s,
                       max_discount=%s, conversion_rate=%s, eligible_category=%s,
                       eligible_item_id=%s, required_count=%s, free_item_id=%s,
                       auto_apply=%s, claim_expiry_days=%s, require_phone_match=%s, updated_at=NOW()
                       WHERE id=%s""",
                    (
                        body.mode, body.pointsPerUnit, body.unitAmount, body.minRedeem,
                        body.maxDiscount, body.conversionRate, body.eligibleCategory,
                        body.eligibleItemId, body.requiredCount, body.freeItemId,
                        body.autoApply, body.claimExpiryDays, body.requirePhoneMatch,
                        existing[0],
                    ),
                )
            else:
                cur.execute(
                    """INSERT INTO reward_settings
                       (restaurant_id, mode, points_per_unit, unit_amount, min_redeem,
                        max_discount, conversion_rate, eligible_category, eligible_item_id,
                        required_count, free_item_id, auto_apply, claim_expiry_days, require_phone_match)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        rid,
                        body.mode, body.pointsPerUnit, body.unitAmount, body.minRedeem,
                        body.maxDiscount, body.conversionRate, body.eligibleCategory,
                        body.eligibleItemId, body.requiredCount, body.freeItemId,
                        body.autoApply, body.claimExpiryDays, body.requirePhoneMatch,
                    ),
                )
    return body.model_dump()


# ─────────────────────────────────────────────────────────────────────────────
# Theme settings (admin can update their restaurant's visual theme)
# ─────────────────────────────────────────────────────────────────────────────

class ThemeBody(BaseModel):
    primaryColor: Optional[str] = None
    secondaryColor: Optional[str] = None
    accentColor: Optional[str] = None
    logoUrl: Optional[str] = None
    faviconUrl: Optional[str] = None
    restaurantName: Optional[str] = None
    heroText: Optional[str] = None
    heroSubtext: Optional[str] = None
    fontFamily: Optional[str] = None


@router.get("/theme")
def admin_get_theme(admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT primary_color, secondary_color, accent_color,
                          logo_url, favicon_url, restaurant_name,
                          hero_text, hero_subtext, font_family
                   FROM theme_settings WHERE restaurant_id = %s""",
                (rid,),
            )
            r = cur.fetchone()
    if not r:
        return {}
    return {
        "primaryColor": r[0], "secondaryColor": r[1], "accentColor": r[2],
        "logoUrl": r[3], "faviconUrl": r[4], "restaurantName": r[5],
        "heroText": r[6], "heroSubtext": r[7], "fontFamily": r[8],
    }


@router.put("/theme")
def admin_update_theme(body: ThemeBody, admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO theme_settings
                       (restaurant_id, primary_color, secondary_color, accent_color,
                        logo_url, favicon_url, restaurant_name, hero_text, hero_subtext, font_family)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (restaurant_id) DO UPDATE SET
                       primary_color   = COALESCE(EXCLUDED.primary_color,   theme_settings.primary_color),
                       secondary_color = COALESCE(EXCLUDED.secondary_color, theme_settings.secondary_color),
                       accent_color    = COALESCE(EXCLUDED.accent_color,    theme_settings.accent_color),
                       logo_url        = COALESCE(EXCLUDED.logo_url,        theme_settings.logo_url),
                       favicon_url     = COALESCE(EXCLUDED.favicon_url,     theme_settings.favicon_url),
                       restaurant_name = COALESCE(EXCLUDED.restaurant_name, theme_settings.restaurant_name),
                       hero_text       = COALESCE(EXCLUDED.hero_text,       theme_settings.hero_text),
                       hero_subtext    = COALESCE(EXCLUDED.hero_subtext,    theme_settings.hero_subtext),
                       font_family     = COALESCE(EXCLUDED.font_family,     theme_settings.font_family),
                       updated_at      = NOW()""",
                (rid,
                 body.primaryColor, body.secondaryColor, body.accentColor,
                 body.logoUrl, body.faviconUrl, body.restaurantName,
                body.heroText, body.heroSubtext, body.fontFamily),
            )
            record_audit(
                cur,
                tenant_id=rid,
                actor_type="admin",
                actor_id=str(admin["id"]),
                action="theme.updated",
                resource_type="theme",
                resource_id=str(rid),
                after=body.model_dump(exclude_none=True),
            )
    return {"success": True}


# ─────────────────────────────────────────────────────────────────────────────
# Branding settings (admin website appearance editor)
# ─────────────────────────────────────────────────────────────────────────────

class BrandingBody(BaseModel):
    layout: Optional[str] = None
    primaryColor: Optional[str] = None
    restaurantName: Optional[str] = None
    slogan: Optional[str] = None
    logoUrl: Optional[str] = None
    heroImageUrl: Optional[str] = None
    slides: Optional[list[dict]] = None


def _normalize_branding_slides(value: Optional[str]) -> list[dict]:
    if not value:
        return []
    try:
        data = _json.loads(value)
    except Exception:
        return []
    if not isinstance(data, list):
        return []

    slides: list[dict] = []
    for slide in data[:3]:
        if not isinstance(slide, dict):
            continue
        image = str(slide.get("image", "")).strip()
        headline = str(slide.get("headline", "")).strip()
        subtext = str(slide.get("subtext", "")).strip()
        if image or headline or subtext:
            slides.append({
                "image": image,
                "headline": headline,
                "subtext": subtext,
            })
    return slides


@router.get("/branding")
def admin_get_branding(admin: dict = Depends(get_current_admin)):
    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM restaurants WHERE id = %s", (rid,))
            restaurant_row = cur.fetchone()
            default_name = restaurant_row[0] if restaurant_row else "Restaurant"

            cur.execute(
                """SELECT layout_style, primary_color, restaurant_name,
                          COALESCE(slogan, hero_subtext), logo_url, hero_image_url
                   FROM theme_settings WHERE restaurant_id = %s""",
                (rid,),
            )
            r = cur.fetchone()

            cur.execute(
                "SELECT value FROM settings WHERE restaurant_id = %s AND key = 'hero_slides'",
                (rid,),
            )
            slides_row = cur.fetchone()

    slides = _normalize_branding_slides(slides_row[0] if slides_row else None)

    if not r:
        return {
            "layout": "classic",
            "primaryColor": "#e85d04",
            "restaurantName": default_name,
            "slogan": "",
            "logoUrl": "",
            "heroImageUrl": "",
            "slides": slides,
        }

    return {
        "layout": r[0] or "classic",
        "primaryColor": r[1] or "#e85d04",
        "restaurantName": r[2] or default_name,
        "slogan": r[3] or "",
        "logoUrl": r[4] or "",
        "heroImageUrl": r[5] or "",
        "slides": slides,
    }


@router.patch("/branding")
def admin_update_branding(body: BrandingBody, admin: dict = Depends(get_current_admin)):
    if body.layout is not None and body.layout not in {"classic", "modern", "minimal"}:
        raise HTTPException(status_code=400, detail="Invalid layout")

    if body.slogan is not None and len(body.slogan) > 80:
        raise HTTPException(status_code=400, detail="Slogan must be 80 characters or less")

    normalized_slides: Optional[list[dict]] = None
    if body.slides is not None:
        if not isinstance(body.slides, list):
            raise HTTPException(status_code=400, detail="slides must be an array")
        if len(body.slides) > 3:
            raise HTTPException(status_code=400, detail="A maximum of 3 slides is allowed")

        normalized_slides = []
        for slide in body.slides:
            if not isinstance(slide, dict):
                continue
            image = str(slide.get("image", "")).strip()
            headline = str(slide.get("headline", "")).strip()
            subtext = str(slide.get("subtext", "")).strip()
            if image or headline or subtext:
                normalized_slides.append(
                    {"image": image, "headline": headline, "subtext": subtext}
                )

    rid = _restaurant_id(admin)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO theme_settings
                       (restaurant_id, layout_style, primary_color, restaurant_name, slogan,
                        logo_url, hero_image_url, hero_subtext)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (restaurant_id) DO UPDATE SET
                       layout_style    = COALESCE(EXCLUDED.layout_style,    theme_settings.layout_style),
                       primary_color   = COALESCE(EXCLUDED.primary_color,   theme_settings.primary_color),
                       restaurant_name = COALESCE(EXCLUDED.restaurant_name, theme_settings.restaurant_name),
                       slogan          = COALESCE(EXCLUDED.slogan,          theme_settings.slogan),
                       logo_url        = COALESCE(EXCLUDED.logo_url,        theme_settings.logo_url),
                       hero_image_url  = COALESCE(EXCLUDED.hero_image_url,  theme_settings.hero_image_url),
                       hero_subtext    = COALESCE(EXCLUDED.hero_subtext,    theme_settings.hero_subtext),
                       updated_at      = NOW()""",
                (
                    rid,
                    body.layout,
                    body.primaryColor,
                    body.restaurantName,
                    body.slogan,
                    body.logoUrl,
                    body.heroImageUrl,
                    body.slogan,
                ),
            )

            if normalized_slides is not None:
                cur.execute(
                    """INSERT INTO settings (restaurant_id, key, value)
                       VALUES (%s, 'hero_slides', %s)
                       ON CONFLICT (restaurant_id, key)
                       DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()""",
                    (rid, _json.dumps(normalized_slides)),
                )

            conn.commit()

    return {"success": True}
