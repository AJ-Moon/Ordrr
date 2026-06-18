from fastapi import APIRouter, Depends, HTTPException
from db import get_db
from dependencies.auth import get_restaurant_id

router = APIRouter()


@router.get("/")
def get_faqs(restaurant_id: int = Depends(get_restaurant_id)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, question, answer, category, order_index FROM faqs "
                "WHERE restaurant_id = %s ORDER BY order_index, id",
                (restaurant_id,),
            )
            rows = cur.fetchall()
    return [{"id": r[0], "question": r[1], "answer": r[2], "category": r[3], "orderIndex": r[4]} for r in rows]


@router.get("/content/{slug}")
def get_content(slug: str, restaurant_id: int = Depends(get_restaurant_id)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT slug, title, content, updated_at FROM content_pages WHERE restaurant_id = %s AND slug = %s",
                (restaurant_id, slug),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Page not found")
    updated_at = row[3].strftime("%B %d, %Y") if row[3] else None
    return {"slug": row[0], "title": row[1], "content": row[2], "updatedAt": updated_at}
