"""FastAPI dependencies for JWT authentication."""
import asyncio

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Query, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.jwt import decode_token
from shared.config import get_settings
from shared.db import get_db
from shared.db.models import User

_bearer = HTTPBearer(auto_error=True)


async def _is_token_blacklisted(token: str) -> bool:
    """Return True if the token has been revoked (is in the Redis blacklist)."""
    settings = get_settings()
    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        result = await r.exists(f"bl:{token}")
        await r.aclose()
        return bool(result)
    except Exception:
        # If Redis is unavailable, fail open (don't block all requests)
        return False


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer token and return the authenticated User."""
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong token type",
        )

    if await _is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    return user


async def get_current_org_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str | None:
    """Extract org_id from the JWT payload without an extra DB round-trip."""
    try:
        payload = decode_token(credentials.credentials)
        return payload.get("org")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def ws_get_current_user(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """WebSocket equivalent of get_current_user.

    Clients must pass the access token as a ?token=<jwt> query parameter because
    browser WebSocket APIs do not support custom Authorization headers.
    """
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No token")

    try:
        payload = decode_token(token)
    except JWTError:
        await websocket.close(code=4001, reason="Invalid token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if payload.get("type") != "access":
        await websocket.close(code=4001, reason="Invalid token type")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")

    if await _is_token_blacklisted(token):
        await websocket.close(code=4001, reason="Token revoked")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        await websocket.close(code=4001, reason="User not found or disabled")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user
