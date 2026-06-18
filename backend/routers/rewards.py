from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db import get_db
from dependencies.auth import get_current_user, get_restaurant_id, TokenData

router = APIRouter()


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
        WHERE restaurant_id = %s
          AND key IN ('points_per_dollar', 'min_redeem_points', 'points_value_cents', 'rewards_enabled')
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


@router.get("/settings")
def get_reward_settings_public(restaurant_id: int = Depends(get_restaurant_id)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cfg = _get_rewards_program_settings(cur, restaurant_id)

    conversion_rate = cfg["points_value_cents"] / 100.0
    return {
        "mode": "points",
        "minRedeem": cfg["min_redeem_points"],
        "conversionRate": conversion_rate,
        "pointsPerDollar": cfg["points_per_dollar"],
        "pointsValueCents": cfg["points_value_cents"],
        "rewardsEnabled": cfg["rewards_enabled"],
    }


def _get_points(user_id: str, restaurant_id: int) -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT points FROM points WHERE user_id = %s AND restaurant_id = %s",
                (user_id, restaurant_id),
            )
            row = cur.fetchone()
    return row[0] if row else 0


def _run_points_expiry(cur, user_id: str, restaurant_id: int) -> None:
    """Expire points past their expiry date and log a transaction. Call inside an open cursor."""
    cur.execute(
        """SELECT points FROM points
           WHERE user_id = %s AND restaurant_id = %s
             AND expires_at IS NOT NULL AND expires_at < NOW() AND points > 0""",
        (user_id, restaurant_id),
    )
    row = cur.fetchone()
    if row and row[0] > 0:
        expired_pts = row[0]
        cur.execute(
            "UPDATE points SET points = 0, updated_at = NOW() WHERE user_id = %s AND restaurant_id = %s",
            (user_id, restaurant_id),
        )
        cur.execute(
            """INSERT INTO points_transactions
               (user_id, restaurant_id, type, points, balance_after)
               VALUES (%s, %s, 'expire', %s, 0)""",
            (user_id, restaurant_id, -expired_pts),
        )


@router.get("/points")
def get_points(current_user: TokenData = Depends(get_current_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            _run_points_expiry(cur, current_user.id, current_user.restaurant_id)
            cur.execute(
                "SELECT points FROM points WHERE user_id = %s AND restaurant_id = %s",
                (current_user.id, current_user.restaurant_id),
            )
            row = cur.fetchone()
    return {"points": row[0] if row else 0}


class RedeemRequest(BaseModel):
    rewardId: str
    pointsCost: int


@router.post("/redeem")
def redeem_reward(body: RedeemRequest, current_user: TokenData = Depends(get_current_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cfg = _get_rewards_program_settings(cur, current_user.restaurant_id)

            if not cfg["rewards_enabled"]:
                raise HTTPException(status_code=400, detail="Rewards program is disabled")

            if body.pointsCost < cfg["min_redeem_points"]:
                raise HTTPException(
                    status_code=400,
                    detail={"pointsCost": [f"Minimum redeem is {cfg['min_redeem_points']} points"]},
                )

            # Atomic read+deduct in one query: the WHERE points >= %s prevents
            # concurrent redemptions from both succeeding on the same balance.
            cur.execute(
                """UPDATE points
                   SET points = points - %s, updated_at = NOW()
                   WHERE user_id = %s AND restaurant_id = %s AND points >= %s
                   RETURNING points""",
                (body.pointsCost, current_user.id, current_user.restaurant_id, body.pointsCost),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Insufficient points")
    return {"success": True, "remainingPoints": row[0]}


@router.get("/history")
def get_points_history(current_user: TokenData = Depends(get_current_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT type, points, balance_after, order_id, created_at
                   FROM points_transactions
                   WHERE user_id = %s AND restaurant_id = %s
                   ORDER BY created_at DESC
                   LIMIT 20""",
                (current_user.id, current_user.restaurant_id),
            )
            rows = cur.fetchall()
    return [
        {
            "type": r[0],
            "points": r[1],
            "balanceAfter": r[2],
            "orderId": r[3],
            "createdAt": r[4].isoformat() if r[4] else "",
        }
        for r in rows
    ]

