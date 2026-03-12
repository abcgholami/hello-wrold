"""JWT token creation, validation, and revocation utilities."""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_BLACKLIST_PREFIX = "bl:"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str, org_id: Optional[str] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "org": org_id, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": user_id, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Raises JWTError if invalid or expired."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def blacklist_token(token: str, exp: int) -> None:
    """Store token in Redis with TTL equal to its remaining lifetime.

    Fails silently so a Redis outage does not break the logout endpoint.
    """
    ttl = max(1, exp - int(datetime.now(timezone.utc).timestamp()))
    try:
        import redis as sync_redis
        r = sync_redis.from_url(settings.redis_url, decode_responses=True)
        r.setex(f"{_BLACKLIST_PREFIX}{token}", ttl, "1")
        r.close()
    except Exception as exc:
        logger.warning("Could not blacklist token in Redis: %s", exc)


def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, key_hash, key_prefix)."""
    raw = "vf_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    key_prefix = raw[:8]
    return raw, key_hash, key_prefix


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()
