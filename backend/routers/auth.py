import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from jose import jwt
from pydantic import BaseModel, EmailStr

from db import get_db
from dependencies.auth import get_current_user, get_restaurant_id, TokenData
from services.rate_limits import consume_auth_rate

router = APIRouter()


def _hash(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _verify(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    firstName: str
    lastName: str
    phone: Optional[str] = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _sign_token(user_id: str, email: str, restaurant_id: int) -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
    expire = datetime.utcnow() + timedelta(days=7)
    return jwt.encode(
        {"id": user_id, "email": email, "type": "user", "restaurant_id": restaurant_id, "exp": expire},
        secret,
        algorithm="HS256",
    )


@router.post("/register", status_code=201)
def register(body: RegisterRequest, restaurant_id: int = Depends(get_restaurant_id)):
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail={"password": ["Minimum 8 characters"]})
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE email = %s AND restaurant_id = %s",
                (body.email, restaurant_id),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Email already registered")
            hashed = _hash(body.password)
            cur.execute(
                """INSERT INTO users (restaurant_id, email, password_hash, first_name, last_name, phone)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                (restaurant_id, body.email, hashed, body.firstName, body.lastName, body.phone or ""),
            )
            user_id = str(cur.fetchone()[0])
    token = _sign_token(user_id, body.email, restaurant_id)
    return {
        "token": token,
        "user": {
            "id": user_id, "email": body.email,
            "firstName": body.firstName, "lastName": body.lastName,
            "phone": body.phone or "",
        },
    }


@router.post("/login")
def login(body: LoginRequest, request: Request, restaurant_id: int = Depends(get_restaurant_id)):
    consume_auth_rate(request, f"customer_login:{restaurant_id}", body.email)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, password_hash, first_name, last_name, phone FROM users "
                "WHERE email = %s AND restaurant_id = %s",
                (body.email, restaurant_id),
            )
            row = cur.fetchone()
    if not row or not _verify(body.password, row[2]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _sign_token(str(row[0]), row[1], restaurant_id)
    return {
        "token": token,
        "user": {
            "id": str(row[0]), "email": row[1],
            "firstName": row[3], "lastName": row[4],
            "phone": row[5] or "",
        },
    }


@router.get("/me")
def get_me(current_user: TokenData = Depends(get_current_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, first_name, last_name, phone, created_at FROM users WHERE id = %s AND restaurant_id = %s",
                (current_user.id, current_user.restaurant_id),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": row[0], "email": row[1],
        "firstName": row[2], "lastName": row[3],
        "phone": row[4] or "",
        "createdAt": row[5].isoformat() if row[5] else "",
    }


class UpdateProfileRequest(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    phone: Optional[str] = None


@router.put("/me")
def update_profile(body: UpdateProfileRequest, current_user: TokenData = Depends(get_current_user)):
    updates = []
    params = []
    if body.firstName is not None:
        updates.append("first_name = %s")
        params.append(body.firstName)
    if body.lastName is not None:
        updates.append("last_name = %s")
        params.append(body.lastName)
    if body.phone is not None:
        updates.append("phone = %s")
        params.append(body.phone)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    params.append(current_user.id)
    params.append(current_user.restaurant_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = %s AND restaurant_id = %s RETURNING id, email, first_name, last_name, phone",
                params,
            )
            row = cur.fetchone()
    return {"id": row[0], "email": row[1], "firstName": row[2], "lastName": row[3], "phone": row[4] or ""}
