from contextlib import asynccontextmanager
from datetime import datetime
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request as StarletteRequest
import psycopg2

from db import get_db, reset_request_context, set_platform_mode, set_request_tenant
from dependencies.auth import get_restaurant_id, resolve_request_tenant_id
from routers import auth, menu, orders, branches, rewards, contact, faqs, admin
from routers import platform_admin, theme, chatbot, delivery, revenue_operator, events, carts
from routers import analytics, competitors, opportunities, experiments, missions, operational_missions, advanced_conversion

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Flavor Hub API", version="1.0.0", lifespan=lifespan)

_backend_dir = Path(__file__).resolve().parent
_static_dir = _backend_dir / "static"
(_static_dir / "uploads").mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

_frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
allowed_origins = [o.strip() for o in _frontend_origin.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_PLATFORM_PATH_PREFIX = "/api/platform-admin"


class TenantContextMiddleware:
    """Pure-ASGI middleware that establishes the RLS tenant context per request.

    Runs in the request's async task so the context variables it sets propagate
    into the threadpool where sync handlers execute. Platform-admin endpoints run
    in cross-tenant ("platform") mode; everything else is pinned to the tenant
    resolved from the request host (or dev header). Unknown hosts get no tenant
    context, so RLS denies all tenant data and the route returns its normal 404.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        is_platform = path.startswith(_PLATFORM_PATH_PREFIX)
        tenant_id = None
        if not is_platform and path.startswith("/api/"):
            request = StarletteRequest(scope)
            tenant_id = await run_in_threadpool(resolve_request_tenant_id, request)

        set_request_tenant(tenant_id)
        set_platform_mode(is_platform)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_request_context()


app.add_middleware(TenantContextMiddleware)


@app.middleware("http")
async def add_upload_cache_headers(request: Request, call_next):
    """Uploaded images have UUID-based filenames so they are safe to cache for 1 year."""
    response = await call_next(request)
    if request.url.path.startswith("/static/uploads/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response

app.include_router(auth.router,            prefix="/api/auth",             tags=["auth"])
app.include_router(menu.router,            prefix="/api/menu",             tags=["menu"])
app.include_router(orders.router,          prefix="/api/orders",           tags=["orders"])
app.include_router(branches.router,        prefix="/api/branches",         tags=["branches"])
app.include_router(rewards.router,         prefix="/api/rewards",          tags=["rewards"])
app.include_router(contact.router,         prefix="/api/contact",          tags=["contact"])
app.include_router(faqs.router,            prefix="/api/faqs",             tags=["faqs"])
app.include_router(admin.router,           prefix="/api/admin",            tags=["admin"])
app.include_router(theme.router,           prefix="/api/theme",            tags=["theme"])
app.include_router(platform_admin.router,  prefix="/api/platform-admin",   tags=["platform-admin"])
app.include_router(chatbot.router,         prefix="/api",                  tags=["chatbot"])
app.include_router(delivery.router,        prefix="/api",                  tags=["delivery"])
app.include_router(revenue_operator.router, prefix="/api/v1",              tags=["revenue-operator"])
app.include_router(events.router,           prefix="/api/v1",              tags=["events"])
app.include_router(carts.router,            prefix="/api/v1",              tags=["carts"])
app.include_router(analytics.router,        prefix="/api/v1",              tags=["analytics"])
app.include_router(competitors.router,      prefix="/api/v1",              tags=["competitors"])
app.include_router(opportunities.router,    prefix="/api/v1",              tags=["opportunities"])
app.include_router(experiments.router,      prefix="/api/v1",              tags=["experiments"])
app.include_router(missions.router,         prefix="/api/v1",              tags=["missions"])
app.include_router(operational_missions.router, prefix="/api/v1",          tags=["operational-missions"])
app.include_router(advanced_conversion.router, prefix="/api/v1",           tags=["advanced-conversion"])


@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/settings")
def public_settings(restaurant_id: int = Depends(get_restaurant_id)):
    """Public site settings for the current tenant (resolved from hostname)."""
    PUBLIC_KEYS = {
        "phone", "email", "address", "hours", "whatsapp",
        "instagram_url", "facebook_url", "twitter_url", "tiktok_url",
        "delivery_charge", "min_order_amount", "restaurant_open",
        "announcement", "announcement_active", "maps_embed", "tagline", "brand_name",
    }
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT key, value FROM settings WHERE restaurant_id = %s",
                (restaurant_id,),
            )
            rows = cur.fetchall()
    return {r[0]: r[1] for r in rows if r[0] in PUBLIC_KEYS}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.exception_handler(psycopg2.OperationalError)
async def db_operational_error_handler(request: Request, exc: psycopg2.OperationalError):
    return JSONResponse(
        status_code=503,
        content={"error": "Database temporarily unavailable"},
    )


@app.exception_handler(psycopg2.InterfaceError)
async def db_interface_error_handler(request: Request, exc: psycopg2.InterfaceError):
    return JSONResponse(
        status_code=503,
        content={"error": "Database temporarily unavailable"},
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "5000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
