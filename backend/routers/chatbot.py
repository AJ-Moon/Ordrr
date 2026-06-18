"""
AI Chatbot router — POST /api/chat

Uses OpenAI GPT-4o to answer questions and place real orders through
the existing DB schema. Follows the same patterns as orders.py and menu.py.
"""
import json
import os
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from db import get_db
from dependencies.auth import get_optional_current_user, get_restaurant_id, TokenData
from core.money import cents_to_float
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
from services.entitlements import consume_feature_usage, get_feature_access
from services.jobs import enqueue_job
from services.rate_limits import consume_intervention_rate

router = APIRouter()


def _chatbot_disabled_response(message: str):
    return {"reply": message, "session_id": None, "action": None, "disabled": True}


def _enforce_chat_rate_limits(restaurant_id: int, session_id: Optional[str]) -> None:
    """Throttle the public AI chat endpoint before any OpenAI spend.

    Two layers: a per-tenant ceiling that caps total billing exposure, and a
    tighter per-session cap so a single visitor cannot spam the model. Both keys
    fit the intervention_request_windows.scope column (varchar(60))."""
    consume_intervention_rate(
        restaurant_id,
        "chatbot",
        "CHATBOT_RATE_LIMIT_PER_MINUTE",
        120,
    )
    if session_id:
        consume_intervention_rate(
            restaurant_id,
            f"chatbot:{session_id}"[:60],
            "CHATBOT_SESSION_RATE_LIMIT_PER_MINUTE",
            15,
        )


# ─── Request / Response models ────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    conversation_history: List[ChatMessage] = Field(default_factory=list)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_setting(cur, key: str, restaurant_id: int, default: str = "") -> str:
    cur.execute(
        "SELECT value FROM settings WHERE key = %s AND restaurant_id = %s",
        (key, restaurant_id),
    )
    row = cur.fetchone()
    return row[0] if row else default


# ─── Main endpoint ─────────────────────────────────────────────────────────────

@router.post("/chat")
def chat(
    body: ChatRequest,
    restaurant_id: int = Depends(get_restaurant_id),
    current_user: Optional[TokenData] = Depends(get_optional_current_user),
):
    # Throttle before loading context or calling OpenAI to bound cost/abuse.
    _enforce_chat_rate_limits(restaurant_id, body.session_id)

    # Plan entitlement: the AI chatbot is a paid feature. Disabled plans get a
    # graceful message (so the widget can hide), not an error.
    access = get_feature_access(restaurant_id, "ai.chatbot")
    if not access.enabled:
        return _chatbot_disabled_response(
            "Live chat isn't available right now. You can browse the menu and order "
            "directly, or call us for help."
        )
    # Meter usage against the plan's AI message allowance (if any limit is set).
    if access.limit is not None:
        from fastapi import HTTPException
        try:
            consume_feature_usage(restaurant_id, "ai.chatbot")
        except HTTPException as exc:
            if exc.status_code == 429:
                return _chatbot_disabled_response(
                    "We've reached today's live-chat capacity. Please order from the "
                    "menu or call us — sorry about that!"
                )
            raise

    with get_db() as conn:
        with conn.cursor() as cur:

            # ── Step 1: Load restaurant context ───────────────────────────────

            # Menu items
            cur.execute(
                """SELECT id, name, description, price, category, is_spicy, is_popular
                   FROM menu_items
                   WHERE restaurant_id = %s AND is_available = TRUE
                   ORDER BY display_order ASC NULLS LAST, is_popular DESC""",
                (restaurant_id,),
            )
            menu_rows = cur.fetchall()
            menu_items = [
                {
                    "id": r[0], "name": r[1], "description": r[2] or "",
                    "price": float(r[3]), "category": r[4],
                    "is_spicy": bool(r[5]), "is_popular": bool(r[6]),
                }
                for r in menu_rows
            ]

            # Settings
            cur.execute(
                """SELECT key, value FROM settings
                   WHERE restaurant_id = %s
                   AND key IN ('delivery_charge','min_order_amount','restaurant_open',
                               'points_per_dollar','rewards_enabled','phone','cash_on_delivery')""",
                (restaurant_id,),
            )
            settings = {r[0]: r[1] for r in cur.fetchall()}

            # Branches
            cur.execute(
                """SELECT name, address, city, phone, hours, is_open
                   FROM branches WHERE restaurant_id = %s""",
                (restaurant_id,),
            )
            branches = [
                {
                    "name": r[0], "address": r[1], "city": r[2],
                    "phone": r[3], "hours": r[4], "is_open": bool(r[5]),
                }
                for r in cur.fetchall()
            ]

            # FAQs
            cur.execute(
                "SELECT question, answer FROM faqs WHERE restaurant_id = %s",
                (restaurant_id,),
            )
            faqs = [{"question": r[0], "answer": r[1]} for r in cur.fetchall()]

            # Restaurant name from theme_settings
            cur.execute(
                "SELECT restaurant_name FROM theme_settings WHERE restaurant_id = %s LIMIT 1",
                (restaurant_id,),
            )
            theme_row = cur.fetchone()
            restaurant_name = (theme_row[0] if theme_row else None) or "Our Restaurant"

            # ── Step 2: Load or create chat session ───────────────────────────

            session_id = body.session_id
            cart: list = []
            stage = "browsing"
            guest_info: dict = {}

            if session_id:
                cur.execute(
                    "SELECT cart, stage, guest_info FROM chat_sessions WHERE id = %s AND restaurant_id = %s",
                    (session_id, restaurant_id),
                )
                row = cur.fetchone()
                if row:
                    raw_cart = row[0]
                    cart = raw_cart if isinstance(raw_cart, list) else (json.loads(raw_cart) if raw_cart else [])
                    stage = row[1] or "browsing"
                    raw_gi = row[2]
                    guest_info = raw_gi if isinstance(raw_gi, dict) else (json.loads(raw_gi) if raw_gi else {})
                else:
                    session_id = None  # Will be created below

            if not session_id:
                cur.execute(
                    """INSERT INTO chat_sessions (restaurant_id, user_id, cart, stage, guest_info)
                       VALUES (%s, %s, '[]'::jsonb, 'browsing', '{}'::jsonb)
                       RETURNING id""",
                    (restaurant_id, current_user.id if current_user else None),
                )
                session_id = cur.fetchone()[0]
                conn.commit()

            # ── Step 3: Get logged-in user name ───────────────────────────────

            user_name = "Guest"
            if current_user:
                cur.execute(
                    "SELECT first_name, last_name, phone, email FROM users WHERE id = %s AND restaurant_id = %s",
                    (current_user.id, restaurant_id),
                )
                u = cur.fetchone()
                if u:
                    user_name = f"{u[0] or ''} {u[1] or ''}".strip() or current_user.email
                    guest_info = {
                        "name": user_name,
                        "phone": u[2] or "",
                        "email": u[3] or current_user.email,
                    }

            last_order_items = None
            if current_user:
                cur.execute(
                    """SELECT items FROM orders 
                       WHERE user_id = %s AND restaurant_id = %s 
                       ORDER BY created_at DESC LIMIT 1""",
                    (current_user.id, restaurant_id)
                )
                last_order_row = cur.fetchone()
                if last_order_row:
                    last_order_items = last_order_row[0]

            # ── Step 4: Build system prompt ───────────────────────────────────

            is_open = str(settings.get("restaurant_open", "true")).lower() == "true"
            cash_on_delivery = str(settings.get("cash_on_delivery", "true")).lower() == "true"
            payment_note = "Cash on Delivery" if cash_on_delivery else "Card (at door)"

            system_prompt = f"""You are {restaurant_name}'s friendly AI order assistant.

RESTAURANT INFO:
Name: {restaurant_name}
Status: {"OPEN — customers can order now" if is_open else "CLOSED — restaurant is currently closed"}
Delivery charge: {settings.get("delivery_charge", "0")}
Minimum order: {settings.get("min_order_amount", "0")}
Default payment: {payment_note}
Contact phone: {settings.get("phone", "N/A")}

MENU (only available items — never invent prices or items outside this list):
{json.dumps(menu_items, indent=2)}

BRANCHES:
{json.dumps(branches, indent=2)}

FAQS:
{json.dumps(faqs, indent=2)}

CURRENT CART:
{json.dumps(cart, indent=2)}

CURRENT STAGE: {stage}
Stage flow: browsing → collecting_details → confirming → ordered

LOGGED IN USER: {user_name} {"(authenticated — skip name/email/phone collection)" if current_user else "(guest — need to collect name, phone, email)"}
{"USER DETAILS: " + json.dumps(guest_info) if guest_info else ""}
{"PREVIOUS ORDER (for personalization): " + json.dumps(last_order_items) if last_order_items else ""}

YOUR RULES:
1. Be warm, friendly, and concise. Max 3 sentences unless showing order summary.
2. When customer mentions any food, fuzzy-match to real menu item names and confirm: "I found [Item Name] for $X — shall I add it?"
3. When customer confirms an item, add it to cart and show updated cart summary.
4. When customer seems ready to order (says "order", "checkout", "that's all", etc.), move to collecting_details stage.
5. If logged in, skip name/email/phone collection. If guest, collect full name, phone, email one step at a time in a friendly way.
6. Collect: order type (delivery or pickup). If delivery, collect address. If pickup, confirm which branch.
7. Before placing, show EXACT summary and ask for YES confirmation:
   "Here's your order:
   [list each item with qty × price]
   Subtotal: $X
   Delivery: $X
   Total: $X
   [Delivering to: address / Picking up from: branch]
   Payment: {payment_note}
   
   Reply YES to place your order! 🎉"
8. When customer replies YES — trigger the place_order action in your tool call. DO NOT trigger place_order if it is a delivery order and you haven't collected an address.
9. Never invent menu items, prices, or info not in this context.
10. If restaurant is closed, say so warmly but let them browse.
11. For order status, say: "Check your orders at /track"
12. If you cannot help, suggest calling: {settings.get("phone", "us directly")}

OR when customer says YES to the order summary:
{{
  "reply": "Great! Placing your order now... ✅",
  "cart": [...],
  "stage": "confirming",
  "action": {{
    "type": "place_order",
    "items": [{{"menu_item_id": 1, "name": "Item", "quantity": 2, "unit_price": 9.99}}],
    "guest_name": "string or null if logged in",
    "guest_email": "string or null if logged in",
    "guest_phone": "string or null if logged in",
    "order_type": "delivery or pickup",
    "address": "string or empty",
    "payment_method": "cash",
    "notes": ""
  }}
}}"""

            # ── Step 5: Call OpenAI API ────────────────────────────────────────

            api_key = os.getenv("OPENAI_API_KEY")
            messages_payload = [{"role": "system", "content": system_prompt}]

            for msg in body.conversation_history[-20:]:  # last 20 messages for context window
                messages_payload.append({"role": msg.role, "content": msg.content})

            messages_payload.append({"role": "user", "content": body.message})

            ai_reply = ""
            ai_cart = cart
            ai_stage = stage
            ai_action = None

            try:
                tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": "respond_to_customer",
                            "description": "Respond to the customer, update their cart, and optionally place their order.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "reply": {
                                        "type": "string",
                                        "description": "The text message to send to the customer."
                                    },
                                    "cart": {
                                        "type": "array",
                                        "description": "The current state of the customer's cart.",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "integer"},
                                                "name": {"type": "string"},
                                                "price": {"type": "number"},
                                                "qty": {"type": "integer"}
                                            },
                                            "required": ["id", "name", "price", "qty"]
                                        }
                                    },
                                    "stage": {
                                        "type": "string",
                                        "enum": ["browsing", "collecting_details", "confirming", "ordered"]
                                    },
                                    "action": {
                                        "type": ["object", "null"],
                                        "description": "Include this object only if the user has explicitly confirmed they want to place the order right now.",
                                        "properties": {
                                            "type": {"type": "string", "enum": ["place_order"]},
                                            "items": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "menu_item_id": {"type": "integer"},
                                                        "name": {"type": "string"},
                                                        "quantity": {"type": "integer"},
                                                        "unit_price": {"type": "number"}
                                                    },
                                                    "required": ["menu_item_id", "name", "quantity", "unit_price"]
                                                }
                                            },
                                            "guest_name": {"type": ["string", "null"]},
                                            "guest_email": {"type": ["string", "null"]},
                                            "guest_phone": {"type": ["string", "null"]},
                                            "order_type": {"type": "string", "enum": ["delivery", "pickup"]},
                                            "address": {"type": ["string", "null"]},
                                            "payment_method": {"type": "string"},
                                            "notes": {"type": ["string", "null"]}
                                        },
                                        "required": ["type", "items", "order_type", "payment_method"]
                                    }
                                },
                                "required": ["reply", "cart", "stage"]
                            }
                        }
                    }
                ]

                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "gpt-4o-mini",
                            "messages": messages_payload,
                            "tools": tools,
                            "tool_choice": {"type": "function", "function": {"name": "respond_to_customer"}},
                            "max_tokens": 1024,
                            "temperature": 0.7,
                        },
                    )
                    resp.raise_for_status()
                    
                    msg_obj = resp.json()["choices"][0]["message"]
                    
                    if msg_obj.get("tool_calls"):
                        tool_call = msg_obj["tool_calls"][0]
                        parsed = json.loads(tool_call["function"]["arguments"])
                    elif msg_obj.get("content"):
                        raw_text = msg_obj["content"].strip()
                        if raw_text.startswith("```"):
                            raw_text = raw_text.split("```")[1]
                            if raw_text.startswith("json"):
                                raw_text = raw_text[4:]
                        parsed = json.loads(raw_text.strip())
                    else:
                        parsed = {}

                ai_reply = parsed.get("reply", "")
                ai_cart = parsed.get("cart", cart)
                ai_stage = parsed.get("stage", stage)
                ai_action = parsed.get("action")

            except Exception:
                ai_reply = "Sorry, I'm having a little trouble right now. Please try again in a moment, or call us directly!"
                ai_cart = cart
                ai_stage = stage
                ai_action = None

            # ── Step 6: Place order if AI requested it ────────────────────────

            response_action = None

            if ai_action and ai_action.get("type") == "place_order":
                try:
                    act = ai_action
                    order_items = act.get("items", [])
                    order_type = act.get("order_type", "delivery")
                    address = act.get("address") or ""

                    if not is_open:
                        raise ValueError("The restaurant is currently closed, so I cannot place the order yet.")
                    if order_type not in {"delivery", "pickup"}:
                        raise ValueError("Please choose delivery or pickup before placing the order.")

                    if order_items:
                        if order_type == "delivery" and not address.strip():
                            ai_reply = "Please provide your delivery address before we can finalize the order!"
                            ai_stage = "collecting_details"
                            ai_action = None
                        else:
                            payment_method = act.get("payment_method", "cash")
                            if payment_method not in {"cash", "card"}:
                                raise ValueError("Please choose cash or card before placing the order.")

                            priced_lines = price_menu_lines(
                                cur,
                                restaurant_id,
                                [
                                    RequestedLine(
                                        menu_item_id=int(item["menu_item_id"]),
                                        quantity=int(item["quantity"]),
                                    )
                                    for item in order_items
                                ],
                            )
                            subtotal_cents = sum(line.line_revenue_cents for line in priced_lines)
                            minimum_order_cents = load_money_setting_cents(
                                cur, restaurant_id, "min_order_amount"
                            )
                            if subtotal_cents < minimum_order_cents:
                                raise ValueError(
                                    "The minimum order is "
                                    f"{cents_to_float(minimum_order_cents):.2f} "
                                    f"{priced_lines[0].currency}."
                                )
                            delivery_charge_cents = 0
                            if order_type == "delivery":
                                delivery_charge_cents = load_money_setting_cents(
                                    cur, restaurant_id, "delivery_charge"
                                )

                            total_cents = subtotal_cents + delivery_charge_cents
                            margin = calculate_order_margin(priced_lines, revenue_cents=total_cents)
                            order_id = generate_order_id()
                            visitor_id = f"chat-visitor-{session_id}"[:100]
                            analytics_session_id = f"chat-session-{session_id}"[:100]
                            cart_id = f"chat-cart-{session_id}"[:100]
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
                                session_id=analytics_session_id,
                                customer_id=customer_id,
                                user_id=current_user.id if current_user else None,
                                lines=priced_lines,
                            )

                            legacy_items = [line.legacy_json() for line in priced_lines]
                            items_json = json.dumps(legacy_items)

                            guest_name = None if current_user else (act.get("guest_name") or guest_info.get("name") or "")
                            guest_email = None if current_user else (act.get("guest_email") or guest_info.get("email") or "")
                            guest_phone = None if current_user else (act.get("guest_phone") or guest_info.get("phone") or "")
                            if not current_user and (not (guest_name or "").strip() or not (guest_phone or "").strip()):
                                raise ValueError("Please provide your name and phone number before placing the order.")

                            cur.execute(
                                """INSERT INTO orders
                                   (id, restaurant_id, user_id, guest_name, guest_email, guest_phone,
                                    items, subtotal, discount_amount, delivery_charge, total,
                                    status, order_type, payment_method, branch_id,
                                    address, notes, points_earned, points_redeemed, source,
                                    currency, subtotal_cents, discount_cents, delivery_charge_cents,
                                    total_cents, ingredient_cost_cents, packaging_cost_cents,
                                    contribution_margin_cents, cart_id, visitor_id, session_id)
                                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,'placed',%s,%s,NULL,%s,%s,0,0,'chatbot',
                                           %s,%s,0,%s,%s,%s,%s,%s,%s,%s,%s)""",
                                (
                                    order_id, restaurant_id,
                                    current_user.id if current_user else None,
                                    guest_name or "",
                                    guest_email or "",
                                    guest_phone or "",
                                    items_json, cents_to_float(subtotal_cents),
                                    cents_to_float(delivery_charge_cents), cents_to_float(total_cents),
                                    order_type, payment_method,
                                    address,
                                    act.get("notes") or "",
                                    priced_lines[0].currency, subtotal_cents, delivery_charge_cents,
                                    total_cents,
                                    margin.ingredient_cost_cents if margin else 0,
                                    margin.packaging_cost_cents if margin else 0,
                                    margin.contribution_margin_cents if margin else None,
                                    cart_id, visitor_id, analytics_session_id,
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
                                session_id=analytics_session_id,
                                customer_id=customer_id,
                                location_id=None,
                                total_cents=total_cents,
                                currency=priced_lines[0].currency,
                            )
                            enqueue_job(
                                cur,
                                tenant_id=restaurant_id,
                                job_name="analytics.aggregate_daily",
                                idempotency_key=f"order-created:{order_id}",
                                metadata={"orderId": order_id},
                            )

                            ai_stage = "ordered"
                            ai_cart = []
                            response_action = {
                                "type": "order_placed",
                                "order_id": order_id,
                                "total": cents_to_float(total_cents),
                            }
                            
                            track_phone = guest_phone or guest_info.get("phone") or ""
                            
                            ai_reply = (
                                f"🎉 Your order **#{order_id}** has been placed! "
                                f"Total: ${cents_to_float(total_cents):.2f}. "
                                f"You can track it [here](/track?order_id={order_id}&phone={track_phone}). Thank you!"
                            )

                except ValueError as exc:
                    ai_reply = str(exc)
                    ai_stage = "collecting_details"
                    ai_action = None
                except Exception:
                    ai_reply = "I had trouble placing your order. Please try the checkout page or call us directly!"

            # ── Step 7: Update chat session ───────────────────────────────────

            # Save guest info collected during conversation
            if ai_action and ai_action.get("type") == "place_order" and not current_user:
                guest_info = {
                    "name": ai_action.get("guest_name") or guest_info.get("name") or "",
                    "email": ai_action.get("guest_email") or guest_info.get("email") or "",
                    "phone": ai_action.get("guest_phone") or guest_info.get("phone") or "",
                }

            cur.execute(
                """UPDATE chat_sessions
                   SET cart = %s::jsonb, stage = %s, guest_info = %s::jsonb, updated_at = NOW()
                   WHERE id = %s""",
                (
                    json.dumps(ai_cart),
                    ai_stage,
                    json.dumps(guest_info),
                    session_id,
                ),
            )
            conn.commit()

    return {
        "reply": ai_reply,
        "session_id": session_id,
        "action": response_action,
    }
