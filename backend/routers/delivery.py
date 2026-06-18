"""Delivery radius check endpoint — uses Haversine formula, no external libraries."""
import math
from fastapi import APIRouter, Depends
from fastapi import HTTPException
from pydantic import BaseModel

from db import get_db
from dependencies.auth import get_restaurant_id

router = APIRouter()


# ─── Haversine ────────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371
    d_lat = (lat2 - lat1) * math.pi / 180
    d_lng = (lng2 - lng1) * math.pi / 180
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1 * math.pi / 180)
        * math.cos(lat2 * math.pi / 180)
        * math.sin(d_lng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─── Endpoint ─────────────────────────────────────────────────────────────────

from typing import Optional

class DeliveryCheckRequest(BaseModel):
    customerLat: float
    customerLng: float
    restaurantId: Optional[int] = None


@router.post("/check-delivery")
def check_delivery(
    body: DeliveryCheckRequest,
    restaurant_id: int = Depends(get_restaurant_id),
):
    """
    Check whether a customer coordinate is within the restaurant's delivery radius.
    Returns { withinRadius, distanceKm }.
    """
    rid = body.restaurantId if body.restaurantId is not None else restaurant_id

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT key, value FROM settings
                WHERE restaurant_id = %s
                  AND key IN ('restaurant_lat', 'restaurant_lng', 'delivery_radius_km')
                """,
                (rid,),
            )
            rows = cur.fetchall()

    settings: dict[str, str] = {r[0]: r[1] for r in rows}

    lat_str = settings.get("restaurant_lat", "").strip()
    lng_str = settings.get("restaurant_lng", "").strip()
    radius_str = settings.get("delivery_radius_km", "").strip()

    # If the restaurant hasn't configured a location, allow delivery everywhere
    if not lat_str or not lng_str:
        return {"withinRadius": True, "distanceKm": 0.0, "configured": False}

    try:
        rest_lat = float(lat_str)
        rest_lng = float(lng_str)
    except ValueError:
        return {"withinRadius": True, "distanceKm": 0.0, "configured": False}

    radius_km = 5.0  # sensible default
    if radius_str:
        try:
            radius_km = max(0.1, float(radius_str))
        except ValueError:
            pass

    distance = haversine_km(body.customerLat, body.customerLng, rest_lat, rest_lng)
    within = distance <= radius_km

    return {
        "withinRadius": within,
        "distanceKm": round(distance, 2),
        "configured": True,
    }
