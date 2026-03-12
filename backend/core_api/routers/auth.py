"""Authentication endpoints: register, login, refresh, logout, /me."""
import re

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.db.models import OrgMembership, Organization, User
from shared.auth.jwt import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from shared.auth.deps import get_current_user

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)
_SLUG_RE = re.compile(r"[^a-z0-9-]")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    org_name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: str | None
    org_id: str | None = None


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
    )
    db.add(user)

    # Build a unique org slug, appending a suffix on collision
    base_slug = _SLUG_RE.sub("-", req.org_name.lower())[:40]
    slug = base_slug
    suffix = 1
    while True:
        existing = await db.execute(select(Organization).where(Organization.slug == slug))
        if not existing.scalar_one_or_none():
            break
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    org = Organization(name=req.org_name, slug=slug)
    db.add(org)
    await db.flush()

    membership = OrgMembership(org_id=org.id, user_id=user.id, role="owner")
    db.add(membership)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user.id, org.id)
    refresh_token = create_refresh_token(user.id)
    response.set_cookie(
        "refresh_token", refresh_token,
        httponly=True, samesite="lax", max_age=86400 * 7, secure=False,
    )

    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        org_id=org.id,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    # Unified error message to prevent user enumeration
    if not user or not verify_password(req.password, user.hashed_password or ""):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    result2 = await db.execute(
        select(OrgMembership).where(OrgMembership.user_id == user.id).limit(1)
    )
    membership = result2.scalar_one_or_none()
    org_id = membership.org_id if membership else None

    access_token = create_access_token(user.id, org_id)
    refresh_token = create_refresh_token(user.id)
    response.set_cookie(
        "refresh_token", refresh_token,
        httponly=True, samesite="lax", max_age=86400 * 7, secure=False,
    )

    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        org_id=org_id,
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
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    result2 = await db.execute(
        select(OrgMembership).where(OrgMembership.user_id == user.id).limit(1)
    )
    membership = result2.scalar_one_or_none()
    org_id = membership.org_id if membership else None

    new_access = create_access_token(user.id, org_id)
    new_refresh = create_refresh_token(user.id)
    response.set_cookie(
        "refresh_token", new_refresh,
        httponly=True, samesite="lax", max_age=86400 * 7, secure=False,
    )

    return TokenResponse(
        access_token=new_access,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        org_id=org_id,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    refresh_token: str | None = Cookie(default=None),
):
    """Revoke the current access token and clear the refresh cookie."""
    if credentials:
        try:
            payload = decode_token(credentials.credentials)
            blacklist_token(credentials.credentials, payload.get("exp", 0))
        except Exception:
            pass  # Already expired tokens need no blacklisting
    response.delete_cookie("refresh_token")


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "avatar_url": current_user.avatar_url,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }
