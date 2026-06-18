"""
Platform super-admin router — manages all restaurant tenants.

Accessible only with a platform_admin JWT (type:"platform_admin").
Restaurant admins cannot reach these endpoints.

Routes are registered under /api/platform-admin/...
"""
import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer
from jose import jwt
from pydantic import BaseModel

from db import get_db
from dependencies.auth import get_platform_admin
from services.audit import record_audit
from services.rate_limits import consume_auth_rate
from services.domains import (
    dns_instructions,
    generate_verification_token,
    verify_domain_ownership,
)

router = APIRouter()

_bearer = HTTPBearer()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _verify(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())


def _hash(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _sign_platform_token(admin_id: str, email: str) -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
    expire = datetime.utcnow() + timedelta(hours=8)
    return jwt.encode(
        {"id": admin_id, "email": email, "type": "platform_admin", "exp": expire},
        secret,
        algorithm="HS256",
    )


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


# ─────────────────────────────────────────────────────────────────────────────
# Platform admin login
# ─────────────────────────────────────────────────────────────────────────────

class PlatformLoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def platform_login(body: PlatformLoginRequest, request: Request):
    consume_auth_rate(request, "platform_login", body.email)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, password_hash, name FROM platform_admins WHERE email = %s",
                (body.email,),
            )
            row = cur.fetchone()
    if not row or not _verify(body.password, row[2]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _sign_platform_token(str(row[0]), row[1])
    return {"token": token, "admin": {"id": str(row[0]), "email": row[1], "name": row[3]}}


# ─────────────────────────────────────────────────────────────────────────────
# Tenant management
# ─────────────────────────────────────────────────────────────────────────────

class CreateTenantRequest(BaseModel):
    name: str
    slug: str
    primary_domain: Optional[str] = None
    admin_email: str
    admin_password: str
    admin_name: str = "Admin"


@router.post("/tenants")
def create_tenant(body: CreateTenantRequest, _: dict = Depends(get_platform_admin)):
    """Create a new restaurant tenant with its first admin user and default data."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # Create restaurant
            cur.execute(
                "SELECT id FROM restaurants WHERE slug = %s", (body.slug,)
            )
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Slug already taken")

            cur.execute(
                "INSERT INTO restaurants (name, slug) VALUES (%s, %s) RETURNING id",
                (body.name, body.slug),
            )
            restaurant_id = cur.fetchone()[0]

            # Add primary domain — UNVERIFIED until ownership is proven via /verify.
            if body.primary_domain:
                cur.execute(
                    """INSERT INTO domains (restaurant_id, domain, is_primary, verified, verification_token)
                       VALUES (%s, %s, TRUE, FALSE, %s)
                       ON CONFLICT (domain) DO NOTHING""",
                    (restaurant_id, body.primary_domain.lower().strip(), generate_verification_token()),
                )

            # Create admin user
            cur.execute(
                "SELECT id FROM admin_users WHERE email = %s AND restaurant_id = %s",
                (body.admin_email, restaurant_id),
            )
            if not cur.fetchone():
                cur.execute(
                    """INSERT INTO admin_users (restaurant_id, email, password_hash, name, role)
                       VALUES (%s, %s, %s, %s, 'admin')""",
                    (restaurant_id, body.admin_email, _hash_password(body.admin_password), body.admin_name),
                )

            # Seed default reward settings
            cur.execute(
                """INSERT INTO reward_settings (restaurant_id, mode, points_per_unit, unit_amount,
                   min_redeem, max_discount, conversion_rate, required_count, auto_apply,
                   claim_expiry_days, require_phone_match)
                   VALUES (%s, 'points', 1, 100, 100, 500, 1.0, 10, false, 30, false)
                   ON CONFLICT (restaurant_id) DO NOTHING""",
                (restaurant_id,),
            )

            # Seed default settings
            for k, v in [
                ("delivery_charge", "0"), ("min_order_amount", "0"),
                ("points_on_guest", "false"), ("restaurant_open", "true"),
            ]:
                cur.execute(
                    "INSERT INTO settings (restaurant_id, key, value) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (restaurant_id, k, v),
                )

            # Seed default content pages
            for slug, title, content in [
                ("privacy", "Privacy Policy", "Update your privacy policy here."),
                ("terms", "Terms of Service", "Update your terms here."),
                ("about", "About Us", "Tell your story here."),
            ]:
                cur.execute(
                    "INSERT INTO content_pages (restaurant_id, slug, title, content) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (restaurant_id, slug, title, content),
                )

            # Seed default theme
            cur.execute(
                """INSERT INTO theme_settings (restaurant_id, restaurant_name, hero_text, hero_subtext)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (restaurant_id) DO NOTHING""",
                (restaurant_id, body.name, f"Welcome to {body.name}",
                 "Order fresh, delicious food delivered to your door."),
            )

            # Start the tenant on the Starter plan with a trial (best-effort; tolerant
            # of partially-migrated databases so tenant creation never hard-fails).
            # A SAVEPOINT scopes any failure to just this seeding step.
            cur.execute("SAVEPOINT sp_plan_seed")
            try:
                cur.execute(
                    "SELECT id, trial_days FROM plans WHERE plan_key = 'starter' AND active = TRUE"
                )
                starter = cur.fetchone()
                if starter:
                    starter_id, starter_trial = starter[0], (starter[1] or 0)
                    cur.execute(
                        """INSERT INTO tenant_plans (tenant_id, plan_id, starts_at)
                           VALUES (%s, %s, CURRENT_DATE)
                           ON CONFLICT (tenant_id, starts_at) DO NOTHING""",
                        (restaurant_id, starter_id),
                    )
                    cur.execute(
                        """INSERT INTO subscriptions
                           (tenant_id, plan_id, status, trial_ends_at,
                            current_period_start, current_period_end)
                           VALUES (%s, %s,
                                   CASE WHEN %s > 0 THEN 'trialing' ELSE 'active' END,
                                   CASE WHEN %s > 0 THEN NOW() + (%s || ' days')::interval ELSE NULL END,
                                   NOW(), NOW() + INTERVAL '1 month')""",
                        (restaurant_id, starter_id, starter_trial, starter_trial, starter_trial),
                    )
                cur.execute("RELEASE SAVEPOINT sp_plan_seed")
            except Exception:
                cur.execute("ROLLBACK TO SAVEPOINT sp_plan_seed")  # plans not migrated — skip

            record_audit(
                cur,
                tenant_id=restaurant_id,
                actor_type="platform_admin",
                actor_id=str(_["id"]),
                action="tenant.created",
                resource_type="tenant",
                resource_id=str(restaurant_id),
                after={"name": body.name, "slug": body.slug,
                       "primaryDomain": (body.primary_domain or None)},
            )
            conn.commit()

    return {
        "success": True,
        "restaurantId": restaurant_id,
        "slug": body.slug,
        "message": f"Tenant '{body.name}' created successfully.",
    }


@router.get("/tenants")
def list_tenants(_: dict = Depends(get_platform_admin)):
    """List all restaurant tenants with domain and admin counts."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT r.id, r.name, r.slug, r.created_at,
                          COUNT(DISTINCT d.id)                                          AS domain_count,
                          COUNT(DISTINCT a.id)                                          AS admin_count,
                          COUNT(DISTINCT o.id)                                          AS order_count,
                          MAX(CASE WHEN d.is_primary THEN d.domain END)                AS primary_domain
                   FROM restaurants r
                   LEFT JOIN domains     d ON d.restaurant_id = r.id
                   LEFT JOIN admin_users a ON a.restaurant_id = r.id
                   LEFT JOIN orders      o ON o.restaurant_id = r.id
                   GROUP BY r.id, r.name, r.slug, r.created_at
                   ORDER BY r.id""",
            )
            rows = cur.fetchall()
    return [
        {
            "id": r[0], "name": r[1], "slug": r[2],
            "createdAt": r[3].isoformat() if r[3] else None,
            "domainCount": r[4], "adminCount": r[5], "orderCount": r[6],
            "primaryDomain": r[7],
        }
        for r in rows
    ]


@router.get("/tenants/{restaurant_id}")
def get_tenant(restaurant_id: int, _: dict = Depends(get_platform_admin)):
    """Get a single tenant with all domains and admin users."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, slug, created_at FROM restaurants WHERE id = %s", (restaurant_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Tenant not found")

            cur.execute(
                "SELECT id, domain, is_primary, verified, created_at FROM domains WHERE restaurant_id = %s ORDER BY is_primary DESC",
                (restaurant_id,),
            )
            domains = [
                {"id": d[0], "domain": d[1], "isPrimary": d[2], "verified": d[3],
                 "createdAt": d[4].isoformat() if d[4] else None}
                for d in cur.fetchall()
            ]

            cur.execute(
                "SELECT id, email, name, role, created_at FROM admin_users WHERE restaurant_id = %s",
                (restaurant_id,),
            )
            admins = [
                {"id": a[0], "email": a[1], "name": a[2], "role": a[3],
                 "createdAt": a[4].isoformat() if a[4] else None}
                for a in cur.fetchall()
            ]

    return {
        "id": row[0], "name": row[1], "slug": row[2],
        "createdAt": row[3].isoformat() if row[3] else None,
        "domains": domains,
        "admins": admins,
    }


class AddDomainRequest(BaseModel):
    domain: str
    is_primary: bool = False


@router.post("/tenants/{restaurant_id}/domains")
def add_domain(restaurant_id: int, body: AddDomainRequest, _: dict = Depends(get_platform_admin)):
    domain = body.domain.lower().strip()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM restaurants WHERE id = %s", (restaurant_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Tenant not found")
            # Reject if domain already belongs to a different restaurant
            cur.execute(
                "SELECT restaurant_id FROM domains WHERE domain = %s",
                (domain,),
            )
            existing = cur.fetchone()
            if existing and existing[0] != restaurant_id:
                raise HTTPException(
                    status_code=400,
                    detail="Domain is already assigned to another tenant",
                )
            if body.is_primary:
                cur.execute(
                    "UPDATE domains SET is_primary = FALSE WHERE restaurant_id = %s",
                    (restaurant_id,),
                )
            token = generate_verification_token()
            # New/updated domains start UNVERIFIED. They will not resolve a tenant
            # (resolve_public_tenant requires verified = TRUE) until /verify succeeds.
            cur.execute(
                """INSERT INTO domains (restaurant_id, domain, is_primary, verified, verification_token)
                   VALUES (%s, %s, %s, FALSE, %s)
                   ON CONFLICT (domain) DO UPDATE
                     SET is_primary = EXCLUDED.is_primary,
                         verification_token = COALESCE(domains.verification_token, EXCLUDED.verification_token)
                   RETURNING id, verification_token""",
                (restaurant_id, domain, body.is_primary, token),
            )
            row = cur.fetchone()
            domain_id, effective_token = row[0], row[1]
            record_audit(
                cur,
                tenant_id=restaurant_id,
                actor_type="platform_admin",
                actor_id=str(_["id"]),
                action="domain.created",
                resource_type="domain",
                resource_id=domain,
                after={"domain": domain, "isPrimary": body.is_primary, "verified": False},
            )
    return {
        "success": True,
        "domain": domain,
        "domainId": domain_id,
        "verified": False,
        "instructions": dns_instructions(domain, effective_token),
    }


@router.post("/tenants/{restaurant_id}/domains/{domain_id}/verify")
def verify_domain(restaurant_id: int, domain_id: int, _: dict = Depends(get_platform_admin)):
    """Check DNS/HTTP proof and flip the domain to verified on success."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT domain, verification_token, verified FROM domains "
                "WHERE id = %s AND restaurant_id = %s",
                (domain_id, restaurant_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Domain not found")
            domain, token, already = row[0], row[1], row[2]
            if already:
                return {"success": True, "domain": domain, "verified": True, "method": "already"}

            ok, method = verify_domain_ownership(domain, token or "")
            cur.execute(
                "UPDATE domains SET last_checked_at = NOW(), "
                "verified = %s, verified_at = CASE WHEN %s THEN NOW() ELSE verified_at END, "
                "verification_method = CASE WHEN %s THEN %s ELSE verification_method END "
                "WHERE id = %s AND restaurant_id = %s",
                (ok, ok, ok, method or "dns_txt", domain_id, restaurant_id),
            )
            if ok:
                record_audit(
                    cur,
                    tenant_id=restaurant_id,
                    actor_type="platform_admin",
                    actor_id=str(_["id"]),
                    action="domain.verified",
                    resource_type="domain",
                    resource_id=domain,
                    after={"domain": domain, "method": method},
                )
    if not ok:
        return {
            "success": False,
            "domain": domain,
            "verified": False,
            "detail": "Ownership proof not found yet. DNS changes can take time to propagate.",
            "instructions": dns_instructions(domain, token or ""),
        }
    return {"success": True, "domain": domain, "verified": True, "method": method}


@router.delete("/tenants/{restaurant_id}/domains/{domain_id}")
def remove_domain(restaurant_id: int, domain_id: int, _: dict = Depends(get_platform_admin)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM domains WHERE id = %s AND restaurant_id = %s RETURNING domain",
                (domain_id, restaurant_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Domain not found")
            record_audit(
                cur,
                tenant_id=restaurant_id,
                actor_type="platform_admin",
                actor_id=str(_["id"]),
                action="domain.deleted",
                resource_type="domain",
                resource_id=str(domain_id),
                before={"domain": row[0]},
            )
    return {"success": True, "removed": row[0]}


class ResetAdminPasswordRequest(BaseModel):
    admin_id: str
    new_password: str


@router.post("/tenants/{restaurant_id}/reset-admin")
def reset_admin_password(
    restaurant_id: int,
    body: ResetAdminPasswordRequest,
    _: dict = Depends(get_platform_admin),
):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE admin_users SET password_hash = %s WHERE id = %s AND restaurant_id = %s RETURNING id",
                (_hash_password(body.new_password), body.admin_id, restaurant_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Admin user not found")
            # Resetting a tenant admin's password is a privileged takeover/impersonation
            # path and MUST be audited. Never log the password itself.
            record_audit(
                cur,
                tenant_id=restaurant_id,
                actor_type="platform_admin",
                actor_id=str(_["id"]),
                action="admin.password_reset",
                resource_type="admin_user",
                resource_id=str(body.admin_id),
            )
    return {"success": True, "message": "Password updated."}


@router.post("/tenants/{restaurant_id}/add-admin")
def add_restaurant_admin(
    restaurant_id: int,
    body: dict,
    _: dict = Depends(get_platform_admin),
):
    """Create a new admin user for a tenant."""
    email = body.get("email", "").strip()
    password = body.get("password", "").strip()
    name = body.get("name", "Admin").strip()
    role = body.get("role", "employee").strip()
    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM restaurants WHERE id = %s", (restaurant_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Tenant not found")
            record_audit(
                cur,
                tenant_id=restaurant_id,
                actor_type="platform_admin",
                actor_id=str(_["id"]),
                action="tenant.updated",
                resource_type="tenant",
                resource_id=str(restaurant_id),
                after={"name": name},
            )
            cur.execute(
                "SELECT id FROM admin_users WHERE email = %s AND restaurant_id = %s",
                (email, restaurant_id),
            )
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Admin email already exists for this tenant")
            cur.execute(
                "INSERT INTO admin_users (restaurant_id, email, password_hash, name, role) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (restaurant_id, email, _hash_password(password), name, role),
            )
            new_id = cur.fetchone()[0]
            conn.commit()
    return {"success": True, "id": str(new_id)}


# ─────────────────────────────────────────────────────────────────────────────
# Platform-level stats
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Current platform admin identity
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/me")
def platform_me(admin: dict = Depends(get_platform_admin)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, name FROM platform_admins WHERE id = %s",
                (admin["id"],),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Admin not found")
    return {"id": str(row[0]), "email": row[1], "name": row[2]}


# ─────────────────────────────────────────────────────────────────────────────
# Update tenant name / slug
# ─────────────────────────────────────────────────────────────────────────────

class UpdateTenantRequest(BaseModel):
    name: str


@router.put("/tenants/{restaurant_id}")
def update_tenant(
    restaurant_id: int,
    body: UpdateTenantRequest,
    _: dict = Depends(get_platform_admin),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE restaurants SET name = %s WHERE id = %s RETURNING id",
                (name, restaurant_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Tenant not found")
            record_audit(
                cur,
                tenant_id=restaurant_id,
                actor_type="platform_admin",
                actor_id=str(_["id"]),
                action="tenant.updated",
                resource_type="tenant",
                resource_id=str(restaurant_id),
                after={"name": name},
            )
    return {"success": True}


# ─────────────────────────────────────────────────────────────────────────────
# Delete tenant (cascades all data)
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/tenants/{restaurant_id}", status_code=204)
def delete_tenant(restaurant_id: int, _: dict = Depends(get_platform_admin)):
    """
    Permanently delete a restaurant tenant and ALL related data.
    orders and points lack ON DELETE CASCADE so must be removed manually first.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM restaurants WHERE id = %s", (restaurant_id,))
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Tenant not found")
            # Record the destructive action before the cascade. audit_logs.tenant_id
            # is ON DELETE SET NULL, so this record survives the tenant deletion.
            record_audit(
                cur,
                tenant_id=restaurant_id,
                actor_type="platform_admin",
                actor_id=str(_["id"]),
                action="tenant.deleted",
                resource_type="tenant",
                resource_id=str(restaurant_id),
                before={"name": existing[0]},
            )
            # order_claims references orders — delete first
            cur.execute(
                "DELETE FROM order_claims WHERE order_id IN "
                "(SELECT id FROM orders WHERE restaurant_id = %s)",
                (restaurant_id,),
            )
            cur.execute("DELETE FROM points WHERE restaurant_id = %s", (restaurant_id,))
            cur.execute("DELETE FROM orders WHERE restaurant_id = %s", (restaurant_id,))
            # everything else has ON DELETE CASCADE
            cur.execute("DELETE FROM restaurants WHERE id = %s", (restaurant_id,))


# ─────────────────────────────────────────────────────────────────────────────
# Remove an admin user from a tenant
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/tenants/{restaurant_id}/admins/{admin_id}", status_code=204)
def remove_restaurant_admin(
    restaurant_id: int,
    admin_id: str,
    _: dict = Depends(get_platform_admin),
):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM admin_users WHERE id = %s AND restaurant_id = %s RETURNING id",
                (admin_id, restaurant_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Admin user not found")
            record_audit(
                cur,
                tenant_id=restaurant_id,
                actor_type="platform_admin",
                actor_id=str(_["id"]),
                action="admin.removed",
                resource_type="admin_user",
                resource_id=str(admin_id),
            )


# ─────────────────────────────────────────────────────────────────────────────
# Tenant lifecycle (suspend / activate / cancel)
# ─────────────────────────────────────────────────────────────────────────────

_TENANT_STATUSES = {"active", "trialing", "suspended", "cancelled"}


class TenantStatusRequest(BaseModel):
    status: str
    reason: Optional[str] = ""


@router.patch("/tenants/{restaurant_id}/status")
def set_tenant_status(
    restaurant_id: int,
    body: TenantStatusRequest,
    _: dict = Depends(get_platform_admin),
):
    new_status = body.status.strip().lower()
    if new_status not in _TENANT_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(_TENANT_STATUSES)}")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE restaurants SET status = %s WHERE id = %s RETURNING id",
                (new_status, restaurant_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Tenant not found")
            # Keep the active subscription roughly in sync with a suspend/cancel.
            if new_status in {"suspended", "cancelled"}:
                cur.execute(
                    "UPDATE subscriptions SET status = %s, updated_at = NOW() "
                    "WHERE tenant_id = %s AND status IN "
                    "('trialing','active','past_due','grace','complimentary')",
                    (new_status, restaurant_id),
                )
            record_audit(
                cur,
                tenant_id=restaurant_id,
                actor_type="platform_admin",
                actor_id=str(_["id"]),
                action=f"tenant.{new_status}",
                resource_type="tenant",
                resource_id=str(restaurant_id),
                after={"status": new_status, "reason": body.reason or ""},
            )
    return {"success": True, "status": new_status}


# ─────────────────────────────────────────────────────────────────────────────
# Subscription plans
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/plans")
def list_plans(_: dict = Depends(get_platform_admin)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, plan_key, name, description, currency,
                          monthly_price_cents, annual_price_cents, trial_days, active, sort_order
                   FROM plans ORDER BY sort_order, id"""
            )
            rows = cur.fetchall()
    return [
        {
            "id": r[0], "planKey": r[1], "name": r[2], "description": r[3],
            "currency": r[4], "monthlyPriceCents": r[5], "annualPriceCents": r[6],
            "trialDays": r[7], "active": r[8], "sortOrder": r[9],
        }
        for r in rows
    ]


class AssignPlanRequest(BaseModel):
    plan_key: str
    status: Optional[str] = None          # defaults to trialing if trial_days>0 else active
    trial_days: Optional[int] = None      # overrides plan default
    complimentary: bool = False


@router.post("/tenants/{restaurant_id}/plan")
def assign_plan(
    restaurant_id: int,
    body: AssignPlanRequest,
    _: dict = Depends(get_platform_admin),
):
    """Assign/replace a tenant's plan and (re)issue its subscription record.

    Entitlements are resolved live from tenant_plans + plan_entitlements, so changing
    the plan immediately changes what the tenant can do — there is no browser-trusted
    plan state."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, trial_days FROM plans WHERE plan_key = %s AND active = TRUE",
                (body.plan_key.strip(),),
            )
            plan = cur.fetchone()
            if not plan:
                raise HTTPException(status_code=404, detail="Plan not found or inactive")
            plan_id, plan_trial_days = plan[0], plan[1]

            cur.execute("SELECT id FROM restaurants WHERE id = %s", (restaurant_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Tenant not found")

            # Capture previous plan for history.
            cur.execute(
                """SELECT tp.plan_id FROM tenant_plans tp
                   WHERE tp.tenant_id = %s AND tp.starts_at <= CURRENT_DATE
                     AND (tp.ends_at IS NULL OR tp.ends_at >= CURRENT_DATE)
                   ORDER BY tp.starts_at DESC LIMIT 1""",
                (restaurant_id,),
            )
            prev = cur.fetchone()
            from_plan_id = prev[0] if prev else None

            # Close any open tenant_plan that STARTED on an earlier day, then open
            # (or, if one already starts today, update) the row effective today.
            # Only closing earlier-dated rows avoids violating the
            # CHECK (ends_at >= starts_at) constraint when the plan is changed on the
            # same day the tenant (and its starter row) was created.
            cur.execute(
                "UPDATE tenant_plans SET ends_at = CURRENT_DATE - 1 "
                "WHERE tenant_id = %s AND starts_at < CURRENT_DATE "
                "AND (ends_at IS NULL OR ends_at >= CURRENT_DATE)",
                (restaurant_id,),
            )
            cur.execute(
                """INSERT INTO tenant_plans (tenant_id, plan_id, starts_at)
                   VALUES (%s, %s, CURRENT_DATE)
                   ON CONFLICT (tenant_id, starts_at)
                   DO UPDATE SET plan_id = EXCLUDED.plan_id, ends_at = NULL""",
                (restaurant_id, plan_id),
            )

            trial_days = body.trial_days if body.trial_days is not None else plan_trial_days
            if body.complimentary:
                status = "complimentary"
            elif body.status:
                status = body.status.strip().lower()
            else:
                status = "trialing" if trial_days and trial_days > 0 else "active"

            # Retire any current subscription, then open the new one.
            cur.execute(
                "UPDATE subscriptions SET status = 'expired', updated_at = NOW() "
                "WHERE tenant_id = %s AND status IN "
                "('trialing','active','past_due','grace','complimentary')",
                (restaurant_id,),
            )
            cur.execute(
                """INSERT INTO subscriptions
                   (tenant_id, plan_id, status, trial_ends_at, current_period_start, current_period_end)
                   VALUES (%s, %s, %s,
                           CASE WHEN %s > 0 THEN NOW() + (%s || ' days')::interval ELSE NULL END,
                           NOW(),
                           NOW() + INTERVAL '1 month')
                   RETURNING id""",
                (restaurant_id, plan_id, status, trial_days or 0, trial_days or 0),
            )
            sub_id = cur.fetchone()[0]

            cur.execute(
                """INSERT INTO plan_history (tenant_id, from_plan_id, to_plan_id, actor_type, actor_id, reason)
                   VALUES (%s, %s, %s, 'platform_admin', %s, %s)""",
                (restaurant_id, from_plan_id, plan_id, str(_["id"]),
                 f"assigned {body.plan_key} ({status})"),
            )
            record_audit(
                cur,
                tenant_id=restaurant_id,
                actor_type="platform_admin",
                actor_id=str(_["id"]),
                action="subscription.assigned",
                resource_type="subscription",
                resource_id=str(sub_id),
                after={"planKey": body.plan_key, "status": status, "trialDays": trial_days},
            )
    return {"success": True, "planKey": body.plan_key, "status": status, "subscriptionId": sub_id}


@router.get("/tenants/{restaurant_id}/subscription")
def get_subscription(restaurant_id: int, _: dict = Depends(get_platform_admin)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT s.id, p.plan_key, p.name, s.status, s.trial_ends_at,
                          s.current_period_start, s.current_period_end, s.created_at
                   FROM subscriptions s JOIN plans p ON p.id = s.plan_id
                   WHERE s.tenant_id = %s
                   ORDER BY s.created_at DESC LIMIT 1""",
                (restaurant_id,),
            )
            row = cur.fetchone()
    if not row:
        return {"subscription": None}
    return {
        "subscription": {
            "id": row[0], "planKey": row[1], "planName": row[2], "status": row[3],
            "trialEndsAt": row[4].isoformat() if row[4] else None,
            "currentPeriodStart": row[5].isoformat() if row[5] else None,
            "currentPeriodEnd": row[6].isoformat() if row[6] else None,
            "createdAt": row[7].isoformat() if row[7] else None,
        }
    }


@router.get("/stats")
def platform_stats(_: dict = Depends(get_platform_admin)):
    """High-level platform metrics."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM restaurants")
            total_tenants = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM orders")
            total_orders = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM users")
            total_customers = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM domains WHERE verified = TRUE")
            total_domains = cur.fetchone()[0]

            cur.execute(
                "SELECT r.name, COUNT(o.id) as order_count FROM restaurants r LEFT JOIN orders o ON o.restaurant_id = r.id GROUP BY r.id, r.name ORDER BY order_count DESC LIMIT 10"
            )
            top_tenants = [{"name": row[0], "orders": row[1]} for row in cur.fetchall()]

    return {
        "totalTenants": total_tenants,
        "totalOrders": total_orders,
        "totalCustomers": total_customers,
        "totalDomains": total_domains,
        "topTenants": top_tenants,
    }
