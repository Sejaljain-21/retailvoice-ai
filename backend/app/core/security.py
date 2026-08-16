"""Password hashing and JWT issuing / verification."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

ALGO = settings.JWT_ALGORITHM


# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------
def _create_token(subject: str, minutes: int, token_type: str, claims: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        "jti": str(uuid.uuid4()),
        "type": token_type,
        **claims,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGO)


def create_access_token(subject: str, **claims: Any) -> str:
    return _create_token(subject, settings.ACCESS_TOKEN_EXPIRE_MINUTES, "access", claims)


def create_refresh_token(subject: str, **claims: Any) -> str:
    return _create_token(subject, settings.REFRESH_TOKEN_EXPIRE_MINUTES, "refresh", claims)


def decode_token(token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError subclasses on failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])
