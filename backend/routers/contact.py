from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from db import get_db
from dependencies.auth import get_restaurant_id

router = APIRouter()


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = ""
    subject: str
    message: str

    model_config = {"str_strip_whitespace": True}


@router.post("/")
def contact(body: ContactRequest, restaurant_id: int = Depends(get_restaurant_id)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO contact_messages (restaurant_id, name, email, phone, subject, message) VALUES (%s, %s, %s, %s, %s, %s)",
                (restaurant_id, body.name, body.email, body.phone or "", body.subject, body.message),
            )
    return {"success": True, "message": "Message received. We'll get back to you shortly."}

