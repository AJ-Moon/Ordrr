"""Public theme endpoint — returns per-tenant visual theme settings."""
import json as _json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from db import get_db
from dependencies.auth import get_restaurant_id

router = APIRouter()


def _normalize_theme_slides(value: Optional[str]) -> list[dict]:
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


@router.get("")
def get_theme(restaurant_id: int = Depends(get_restaurant_id)):
    """
    Return the theme settings for the current tenant.
    Tenant is resolved from the HTTP Host header (hostname → domains table).
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            # Verify the tenant actually exists and get its name
            cur.execute("SELECT name FROM restaurants WHERE id = %s", (restaurant_id,))
            restaurant_row = cur.fetchone()
            if not restaurant_row:
                raise HTTPException(status_code=404, detail="Restaurant not found")
            default_name = restaurant_row[0]

            cur.execute(
                """SELECT primary_color, secondary_color, accent_color,
                          logo_url, favicon_url, restaurant_name,
                          hero_text, hero_subtext, font_family,
                          layout_style, slogan, hero_image_url
                   FROM theme_settings WHERE restaurant_id = %s""",
                (restaurant_id,),
            )
            row = cur.fetchone()

            cur.execute(
                "SELECT value FROM settings WHERE restaurant_id = %s AND key = 'hero_slides'",
                (restaurant_id,),
            )
            slides_row = cur.fetchone()

    slides = _normalize_theme_slides(slides_row[0] if slides_row else None)

    if not row:
        return {
            "restaurantId": restaurant_id,
            "primaryColor": "#e85d04",
            "secondaryColor": "#faa307",
            "accentColor": "#f48c06",
            "logoUrl": "",
            "faviconUrl": "",
            "restaurantName": default_name,
            "heroText": "",
            "heroSubtext": "",
            "fontFamily": "Inter",
            "layout": "classic",
            "slogan": "",
            "heroImageUrl": "",
            "slides": slides,
        }

    return {
        "restaurantId": restaurant_id,
        "primaryColor": row[0],
        "secondaryColor": row[1],
        "accentColor": row[2],
        "logoUrl": row[3],
        "faviconUrl": row[4],
        # Fall back to the restaurant's canonical name if theme name is empty
        "restaurantName": row[5] or default_name,
        "heroText": row[6],
        "heroSubtext": row[7],
        "fontFamily": row[8],
        "layout": row[9] or "classic",
        "slogan": row[10] or row[7] or "",
        "heroImageUrl": row[11] or "",
        "slides": slides,
    }
