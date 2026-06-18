from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

from fastapi import Depends, HTTPException

from db import get_db
from dependencies.auth import get_current_admin


@dataclass(frozen=True)
class FeatureAccess:
    key: str
    enabled: bool
    limit: Optional[int]
    source: str


def get_feature_access(tenant_id: int, feature_key: str) -> FeatureAccess:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT enabled, limit_value
                   FROM tenant_feature_overrides
                   WHERE tenant_id = %s AND feature_key = %s""",
                (tenant_id, feature_key),
            )
            row = cur.fetchone()
            if row:
                return FeatureAccess(feature_key, bool(row[0]), row[1], "tenant_override")

            cur.execute(
                """SELECT pe.enabled, pe.limit_value
                   FROM tenant_plans tp
                   JOIN plan_entitlements pe ON pe.plan_id = tp.plan_id
                   WHERE tp.tenant_id = %s AND pe.feature_key = %s
                     AND tp.starts_at <= CURRENT_DATE
                     AND (tp.ends_at IS NULL OR tp.ends_at >= CURRENT_DATE)
                   ORDER BY tp.starts_at DESC
                   LIMIT 1""",
                (tenant_id, feature_key),
            )
            row = cur.fetchone()
            if row:
                return FeatureAccess(feature_key, bool(row[0]), row[1], "plan")

            cur.execute(
                """SELECT default_enabled, default_limit
                   FROM feature_definitions WHERE feature_key = %s""",
                (feature_key,),
            )
            row = cur.fetchone()
            if not row:
                return FeatureAccess(feature_key, False, None, "unknown")
            return FeatureAccess(feature_key, bool(row[0]), row[1], "default")


def has_feature(tenant_id: int, feature_key: str) -> bool:
    return get_feature_access(tenant_id, feature_key).enabled


def get_feature_limit(tenant_id: int, feature_key: str) -> Optional[int]:
    return get_feature_access(tenant_id, feature_key).limit


def consume_feature_usage(tenant_id: int, feature_key: str, amount: int = 1) -> int:
    if amount <= 0:
        raise ValueError("amount must be positive")
    access = get_feature_access(tenant_id, feature_key)
    if not access.enabled:
        raise HTTPException(status_code=403, detail=f"Feature '{feature_key}' is not enabled")

    period_start = date.today().replace(day=1)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO feature_usage
                   (tenant_id, feature_key, period_start, amount)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (tenant_id, feature_key, period_start)
                   DO UPDATE SET amount = feature_usage.amount + EXCLUDED.amount,
                                 updated_at = NOW()
                   RETURNING amount""",
                (tenant_id, feature_key, period_start, amount),
            )
            used = int(cur.fetchone()[0])
            if access.limit is not None and used > access.limit:
                raise HTTPException(status_code=429, detail=f"Feature '{feature_key}' usage limit exceeded")
            return used


def require_feature(feature_key: str) -> Callable:
    def dependency(admin: dict = Depends(get_current_admin)) -> FeatureAccess:
        tenant_id = int(admin["restaurant_id"])
        access = get_feature_access(tenant_id, feature_key)
        if not access.enabled:
            raise HTTPException(status_code=403, detail=f"Feature '{feature_key}' is not enabled")
        return access

    return dependency
