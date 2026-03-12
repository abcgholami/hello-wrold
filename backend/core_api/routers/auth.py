"""Authentication endpoints: register, login, refresh, OAuth."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.db.models import User, Organization, OrgMembership
from shared.auth.jwt import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    org_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: str | None


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    # Check existing user
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
    )
    db.add(user)

    # Create default org
    import re
    slug = re.sub(r"[^a-z0-9-]", "-", req.org_name.lower())[:40]
    org = Organization(name=req.org_name, slug=slug)
    db.add(org)
    await db.flush()

    membership = OrgMembership(org_id=org.id, user_id=user.id, role="owner")
    db.add(membership)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user.id, org.id)
    refresh_token = create_refresh_token(user.id)

    response.set_cookie("refresh_token", refresh_token, httponly=True, samesite="lax", max_age=86400 * 7)

    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.hashed_password or ""):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Get user's first org
    result2 = await db.execute(select(OrgMembership).where(OrgMembership.user_id == user.id).limit(1))
    membership = result2.scalar_one_or_none()
    org_id = membership.org_id if membership else None

    access_token = create_access_token(user.id, org_id)
    refresh_token = create_refresh_token(user.id)
    response.set_cookie("refresh_token", refresh_token, httponly=True, samesite="lax", max_age=86400 * 7)

    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    result2 = await db.execute(select(OrgMembership).where(OrgMembership.user_id == user.id).limit(1))
    membership = result2.scalar_one_or_none()
    org_id = membership.org_id if membership else None

    new_access = create_access_token(user.id, org_id)
    new_refresh = create_refresh_token(user.id)
    response.set_cookie("refresh_token", new_refresh, httponly=True, samesite="lax", max_age=86400 * 7)

    return TokenResponse(access_token=new_access, user_id=user.id, email=user.email, full_name=user.full_name)


@router.get("/me")
async def me(db: AsyncSession = Depends(get_db)):
    # Stub — real implementation uses get_current_user dependency
    return {"message": "Use Authorization header with Bearer token"}
