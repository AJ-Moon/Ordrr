from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response

from db import get_db
from dependencies.auth import get_restaurant_id

router = APIRouter()


def _row_to_item(r):
    return {
        "id": r[0], "category": r[1], "name": r[2], "description": r[3],
        "price": float(r[4]), "salePrice": float(r[5]) if r[5] is not None else None,
        "image": r[6], "rating": float(r[7]),
        "isSpicy": r[8], "isPopular": r[9], "isFeatured": r[10],
    }


@router.get("/categories")
def get_categories(response: Response, restaurant_id: int = Depends(get_restaurant_id)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT category FROM menu_items WHERE restaurant_id = %s AND is_available = TRUE ORDER BY category",
                (restaurant_id,),
            )
            rows = cur.fetchall()
    response.headers["Cache-Control"] = "public, max-age=300"
    return [r[0] for r in rows]


@router.get("")
@router.get("/")
def get_menu(
    response: Response,
    category: Optional[str] = None,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    restaurant_id: int = Depends(get_restaurant_id),
):
    query = (
        "SELECT id, category, name, description, price, sale_price, image, rating, is_spicy, is_popular, is_featured "
        "FROM menu_items WHERE restaurant_id = %s AND is_available = TRUE"
    )
    params: list = [restaurant_id]
    if category and category != "all":
        query += " AND category = %s"
        params.append(category)
    if search:
        query += " AND name ILIKE %s"
        params.append(f"%{search}%")
    if sort == "price-low":
        query += " ORDER BY price ASC"
    elif sort == "price-high":
        query += " ORDER BY price DESC"
    elif sort == "rating":
        query += " ORDER BY rating DESC"
    else:
        query += " ORDER BY display_order ASC NULLS LAST, is_popular DESC"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    response.headers["Cache-Control"] = "public, max-age=300"
    return [_row_to_item(r) for r in rows]


@router.get("/{item_id}")
def get_menu_item(item_id: int, restaurant_id: int = Depends(get_restaurant_id)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, category, name, description, price, sale_price, image, rating, is_spicy, is_popular, is_featured "
                "FROM menu_items WHERE id = %s AND restaurant_id = %s AND is_available = TRUE",
                (item_id, restaurant_id),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    return _row_to_item(row)

