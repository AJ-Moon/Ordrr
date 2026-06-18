import os
from typing import Callable, Optional

import psycopg2
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from db import get_db

bearer_scheme = HTTPBearer(auto_error=False)

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "testserver"}


class TenantContext(BaseModel):
    id: int
    name: str = ""
    slug: str = ""
    hostname: str = ""
    source: str


class TokenData(BaseModel):
    id: str
    email: str
    restaurant_id: int
    role: str = "customer"
    token_type: str = "customer"


def normalize_hostname(host_header: str) -> str:
    host = (host_header or "").strip().lower()
    if host.startswith("[") and "]" in host:
        return host[1 : host.index("]")]
    return host.split(":", 1)[0].rstrip(".")


def is_local_hostname(hostname: str) -> bool:
    return hostname in _LOCAL_HOSTS or hostname.endswith(".localhost")


def _is_production() -> bool:
    """True if EITHER APP_ENV or ENVIRONMENT marks production. Fails closed."""
    for key in ("APP_ENV", "ENVIRONMENT"):
        val = os.getenv(key)
        if val and val.strip().lower() == "production":
            return True
    return False


def _allow_dev_tenant_header() -> bool:
    # Development conveniences (X-Restaurant-ID header, default-tenant fallback,
    # cross-tenant token tolerance) are HARD-disabled in production regardless of
    # any other flag. This closes the "APP_ENV unset" tenant-bypass class of bugs.
    if _is_production():
        return False
    configured = os.getenv("ALLOW_DEV_TENANT_HEADER")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes", "on"}
    return True


def _trust_forwarded_host() -> bool:
    return os.getenv("TRUST_FORWARDED_HOST", "").strip().lower() in {"1", "true", "yes", "on"}


def request_hostname(request: Request) -> str:
    """Resolve the client-facing hostname.

    Behind a trusted reverse proxy / platform rewrite (Vercel, Cloudflare, nginx)
    the original customer domain arrives in X-Forwarded-Host while Host carries the
    internal upstream name. Only honour X-Forwarded-Host when TRUST_FORWARDED_HOST
    is explicitly enabled, so an untrusted client cannot spoof tenancy with a header.
    """
    if _trust_forwarded_host():
        forwarded = request.headers.get("x-forwarded-host", "")
        if forwarded:
            # A proxy chain may append values; the left-most is the original client host.
            return normalize_hostname(forwarded.split(",")[0])
    return normalize_hostname(request.headers.get("host", ""))


_TENANT_SELECT_WITH_STATUS = {
    "hostname": """SELECT r.id, r.name, r.slug, r.status
                   FROM domains d
                   JOIN restaurants r ON r.id = d.restaurant_id
                   WHERE lower(d.domain) = %s AND d.verified = TRUE
                   LIMIT 1""",
    "id": "SELECT id, name, slug, status FROM restaurants WHERE id = %s LIMIT 1",
}
_TENANT_SELECT_LEGACY = {
    "hostname": """SELECT r.id, r.name, r.slug
                   FROM domains d
                   JOIN restaurants r ON r.id = d.restaurant_id
                   WHERE lower(d.domain) = %s AND d.verified = TRUE
                   LIMIT 1""",
    "id": "SELECT id, name, slug FROM restaurants WHERE id = %s LIMIT 1",
}


def _lookup_tenant(*, hostname: Optional[str] = None, tenant_id: Optional[int] = None) -> Optional[TenantContext]:
    key = "hostname" if hostname is not None else "id"
    param = hostname if hostname is not None else tenant_id
    source = "domain" if hostname is not None else "development_header"
    status_val = None
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(_TENANT_SELECT_WITH_STATUS[key], (param,))
                    row = cur.fetchone()
                    if row is not None:
                        status_val = row[3]
                except psycopg2.errors.UndefinedColumn:
                    # restaurants.status not migrated yet — degrade gracefully.
                    conn.rollback()
                    cur.execute(_TENANT_SELECT_LEGACY[key], (param,))
                    row = cur.fetchone()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Tenant directory is temporarily unavailable")

    if not row:
        return None
    # A suspended or cancelled tenant's public storefront is taken offline.
    if status_val in {"suspended", "cancelled"}:
        raise HTTPException(status_code=403, detail="This restaurant is currently unavailable")
    return TenantContext(
        id=int(row[0]),
        name=row[1] or "",
        slug=row[2] or "",
        hostname=hostname or "",
        source=source,
    )


def resolve_public_tenant(
    request: Request,
    x_restaurant_id: Optional[str] = Header(default=None),
) -> TenantContext:
    """Resolve a public request to a verified tenant. No tenant fallbacks in production."""
    hostname = request_hostname(request)

    if hostname and not is_local_hostname(hostname):
        tenant = _lookup_tenant(hostname=hostname)
        if not tenant:
            raise HTTPException(status_code=404, detail="Restaurant not found for this domain")
        return tenant

    # Beyond this point we are on a local/empty host. In production this is never a
    # valid public request, so we refuse rather than guessing a tenant.
    if _is_production():
        raise HTTPException(status_code=404, detail="Restaurant not found for this domain")

    if x_restaurant_id and _allow_dev_tenant_header():
        try:
            requested_id = int(x_restaurant_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="X-Restaurant-ID must be an integer")
        tenant = _lookup_tenant(tenant_id=requested_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        tenant.hostname = hostname
        return tenant

    default_id_raw = os.getenv("DEFAULT_RESTAURANT_ID")
    if not default_id_raw:
        raise HTTPException(status_code=404, detail="Restaurant not found for this domain")
    tenant = _lookup_tenant(tenant_id=int(default_id_raw))
    if not tenant:
        raise HTTPException(status_code=404, detail="Default development restaurant not found")
    tenant.hostname = hostname
    tenant.source = "development_default"
    return tenant


def get_restaurant_id(tenant: TenantContext = Depends(resolve_public_tenant)) -> int:
    """Compatibility dependency for existing tenant-scoped public routes."""
    return tenant.id


def resolve_request_tenant_id(request: Request) -> Optional[int]:
    """Best-effort tenant id for the RLS middleware. Never raises.

    Returns None when the tenant can't be determined (unknown host, suspended
    tenant, etc.); the route's own dependency will then produce the proper error.
    """
    try:
        tenant = resolve_public_tenant(request, request.headers.get("x-restaurant-id"))
        return tenant.id
    except Exception:
        return None


def _decode_token(credentials: Optional[HTTPAuthorizationCredentials]) -> dict:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return jwt.decode(credentials.credentials, secret, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _enforce_token_tenant(payload: dict, tenant: TenantContext) -> int:
    try:
        token_tenant_id = int(payload["restaurant_id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Token is missing a valid tenant claim")

    if token_tenant_id != tenant.id:
        # The only tolerated mismatch is the local development-default tenant, and
        # only while dev conveniences are enabled (never in production).
        if tenant.source == "development_default" and _allow_dev_tenant_header():
            return token_tenant_id
        raise HTTPException(status_code=403, detail="Token is not valid for this tenant")
    return token_tenant_id


def _assert_admin_account_active(admin_id: str, restaurant_id: int) -> None:
    """Enforce admin/user lifecycle on every privileged request.

    A disabled admin or a suspended/cancelled restaurant loses access immediately,
    independent of the (stateless) JWT's remaining lifetime. Degrades gracefully if
    migration 0011 has not yet been applied (status columns absent)."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT a.status, r.status
                       FROM admin_users a
                       JOIN restaurants r ON r.id = a.restaurant_id
                       WHERE a.id = %s AND a.restaurant_id = %s""",
                    (admin_id, restaurant_id),
                )
                row = cur.fetchone()
    except psycopg2.errors.UndefinedColumn:
        return  # status columns not migrated yet; skip lifecycle enforcement
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Account directory is temporarily unavailable")

    if not row:
        raise HTTPException(status_code=401, detail="Admin account no longer exists")
    admin_status, restaurant_status = row[0], row[1]
    if admin_status != "active":
        raise HTTPException(status_code=403, detail="This admin account has been disabled")
    if restaurant_status == "suspended":
        raise HTTPException(status_code=403, detail="This restaurant is currently suspended")
    if restaurant_status == "cancelled":
        raise HTTPException(status_code=403, detail="This restaurant account is closed")


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    tenant: TenantContext = Depends(resolve_public_tenant),
) -> TokenData:
    payload = _decode_token(credentials)
    token_type = payload.get("type", "customer")
    if token_type in {"admin", "platform_admin"}:
        raise HTTPException(status_code=403, detail="Customer credentials required")
    tenant_id = _enforce_token_tenant(payload, tenant)
    try:
        return TokenData(
            id=str(payload["id"]),
            email=str(payload["email"]),
            restaurant_id=tenant_id,
            role=str(payload.get("role", "customer")),
            token_type=str(token_type),
        )
    except KeyError:
        raise HTTPException(status_code=401, detail="Token is missing required claims")


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    tenant: TenantContext = Depends(resolve_public_tenant),
) -> Optional[TokenData]:
    if not credentials:
        return None
    return get_current_user(credentials=credentials, tenant=tenant)


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    tenant: TenantContext = Depends(resolve_public_tenant),
) -> dict:
    payload = _decode_token(credentials)
    if payload.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin credentials required")
    tenant_id = _enforce_token_tenant(payload, tenant)
    _assert_admin_account_active(str(payload.get("id")), tenant_id)
    return payload


def require_tenant_role(*allowed_roles: str) -> Callable:
    normalized = {role.lower() for role in allowed_roles}

    def dependency(admin: dict = Depends(get_current_admin)) -> dict:
        role = str(admin.get("role", "")).lower()
        if role not in normalized:
            raise HTTPException(status_code=403, detail="Insufficient tenant role")
        return admin

    return dependency


def get_platform_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    payload = _decode_token(credentials)
    if payload.get("type") != "platform_admin":
        raise HTTPException(status_code=403, detail="Platform admin credentials required")
    return payload
