from fastapi import APIRouter, Depends, HTTPException

from db import get_db
from dependencies.auth import get_restaurant_id

router = APIRouter()


def _row_to_branch(r):
    return {
        "id": r[0], "name": r[1], "address": r[2], "city": r[3],
        "phone": r[4], "hours": r[5], "isOpen": r[6],
        "mapsUrl": r[7] if len(r) > 7 else "",
        "isDefault": r[8] if len(r) > 8 else False,
    }


@router.get("/")
def get_branches(restaurant_id: int = Depends(get_restaurant_id)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, address, city, phone, hours, is_open, maps_url, is_default "
                "FROM branches WHERE restaurant_id = %s ORDER BY is_default DESC, id",
                (restaurant_id,),
            )
            rows = cur.fetchall()
    return [_row_to_branch(r) for r in rows]


@router.get("/{branch_id}")
def get_branch(branch_id: int, restaurant_id: int = Depends(get_restaurant_id)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, address, city, phone, hours, is_open, maps_url, is_default "
                "FROM branches WHERE id = %s AND restaurant_id = %s",
                (branch_id, restaurant_id),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Branch not found")
    return _row_to_branch(row)


