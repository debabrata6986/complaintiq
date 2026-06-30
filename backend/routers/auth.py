"""Auth router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from auth_utils import create_token, get_current_user, hash_password, verify_password
from db import get_db
from models import LoginIn, RegisterIn, TokenOut, UserPublic, new_id, utcnow_iso

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
async def register(payload: RegisterIn):
    db = get_db()
    # admin / manager / support roles can only be seeded — public register only as customer
    desired_role = payload.role if payload.role == "customer" else "customer"
    existing = await db.users.find_one({"email": payload.email.lower()})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user_doc = {
        "id": new_id(),
        "email": payload.email.lower(),
        "full_name": payload.full_name.strip(),
        "role": desired_role,
        "phone": payload.phone,
        "avatar_url": None,
        "created_at": utcnow_iso(),
        "password_hash": hash_password(payload.password),
    }
    await db.users.insert_one(user_doc)
    public = {k: v for k, v in user_doc.items() if k != "password_hash"}
    token = create_token(user_doc["id"], desired_role)
    return TokenOut(access_token=token, user=UserPublic(**public))


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn):
    db = get_db()
    doc = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
    if not doc or not verify_password(payload.password, doc["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    public = {k: v for k, v in doc.items() if k != "password_hash"}
    token = create_token(doc["id"], doc["role"])
    return TokenOut(access_token=token, user=UserPublic(**public))


@router.get("/me", response_model=UserPublic)
async def me(user: UserPublic = Depends(get_current_user)):
    return user
