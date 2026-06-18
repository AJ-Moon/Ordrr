import contextvars
import os
import time
from contextlib import contextmanager
from typing import Optional

import psycopg2
from psycopg2 import pool

_POOL = None

# ─────────────────────────────────────────────────────────────────────────────
# Per-request tenant context (RLS).
#
# These context variables are populated by TenantContextMiddleware (in main.py)
# in the request's async context, which reliably propagates into the threadpool
# where sync route handlers and their services run. Every get_db() then applies
# them as Postgres session GUCs (app.tenant_id / app.is_platform) so Row-Level
# Security enforces tenant isolation at the database — independent of whether a
# query remembered its "WHERE restaurant_id = ...".
# ─────────────────────────────────────────────────────────────────────────────
_tenant_var: "contextvars.ContextVar[Optional[int]]" = contextvars.ContextVar(
    "app_tenant_id", default=None
)
_platform_var: "contextvars.ContextVar[bool]" = contextvars.ContextVar(
    "app_is_platform", default=False
)

_UNSET = object()


def set_request_tenant(tenant_id: Optional[int]) -> None:
    _tenant_var.set(tenant_id)


def set_platform_mode(on: bool) -> None:
    _platform_var.set(bool(on))


def reset_request_context() -> None:
    _tenant_var.set(None)
    _platform_var.set(False)


def current_request_tenant() -> Optional[int]:
    return _tenant_var.get()


def _pool_enabled() -> bool:
    return os.getenv("DB_POOL_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _get_pool():
    global _POOL
    if not _pool_enabled():
        return None
    if _POOL is None:
        _POOL = pool.SimpleConnectionPool(
            minconn=max(1, int(os.getenv("DB_POOL_MIN_CONNECTIONS", "1"))),
            maxconn=max(1, int(os.getenv("DB_POOL_MAX_CONNECTIONS", "5"))),
            dsn=os.getenv("DATABASE_URL"),
            connect_timeout=10,
        )
    return _POOL


def _connect() -> psycopg2.extensions.connection:
    """Open a fresh connection to the database."""
    db_pool = _get_pool()
    if db_pool is not None:
        return db_pool.getconn()
    return psycopg2.connect(
        dsn=os.getenv("DATABASE_URL"),
        connect_timeout=10,
    )


def _apply_tenant_context(conn, tenant_id: Optional[int], is_platform: bool) -> None:
    """Set the RLS session GUCs for this connection/transaction.

    set_config(..., is_local=false) keeps the value for the connection; because we
    re-apply it at the start of every get_db(), pooled connections never leak a
    previous request's tenant. The values are rolled back automatically if the
    surrounding transaction aborts.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.tenant_id', %s, false), "
            "       set_config('app.is_platform', %s, false)",
            (
                "" if tenant_id is None else str(int(tenant_id)),
                "on" if is_platform else "off",
            ),
        )


@contextmanager
def get_db(*, tenant_id=_UNSET, platform=_UNSET):
    """Yield a psycopg2 connection with RLS tenant context applied.

    By default the tenant/platform context is taken from the per-request context
    variables. Callers that run outside a request (workers) or that legitimately
    need cross-tenant access (the super-admin router) pass explicit overrides:

        get_db(platform=True)        # super-admin / system: see all tenants
        get_db(tenant_id=42)         # pin a specific tenant

    Creates a fresh connection per call (unless pooling is enabled) and retries up
    to 3 times on transient network errors.
    """
    eff_tenant = _tenant_var.get() if tenant_id is _UNSET else tenant_id
    eff_platform = _platform_var.get() if platform is _UNSET else bool(platform)

    last_err = None
    conn = None

    for attempt in range(4):
        try:
            conn = _connect()
            break
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
            last_err = exc
            if attempt < 3:
                time.sleep(0.2 * (attempt + 1))
                continue
            raise

    if conn is None:
        if last_err:
            raise last_err
        raise psycopg2.OperationalError("Could not open database connection")

    try:
        _apply_tenant_context(conn, eff_tenant, eff_platform)
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            db_pool = _get_pool()
            if db_pool is not None:
                db_pool.putconn(conn)
            else:
                conn.close()
        except Exception:
            pass
