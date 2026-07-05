import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

from app.core.config.settings import settings


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {"sub": user_id, "type": "access", "iat": now, "exp": expire}
    return jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token(
    user_id: str,
    jti: uuid.UUID,
    family_id: uuid.UUID,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT refresh token. `jti`/`family_id` must match the
    caller's persisted RefreshToken row — see app/modules/auth/service.py."""
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta
        else timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode = {
        "sub": user_id,
        "type": "refresh",
        "jti": str(jti),
        "family_id": str(family_id),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode a JWT access token and return its payload if valid.

    A missing "type" claim is treated as an implicit "access" token for
    backward compatibility with tokens issued before this claim existed.
    # TODO: remove this compat shim once old tokens have expired (they self-
    # expire within ACCESS_TOKEN_EXPIRE_MINUTES of the deploy that adds this).
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        return None

    token_type = payload.get("type")
    if token_type is None and payload.get("refresh") is True:
        return None  # old-format refresh token — never valid as an access token
    if token_type is not None and token_type != "access":
        return None
    return payload


def decode_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode a JWT refresh token and return its payload if valid.

    Unlike decode_access_token, this has no backward-compat path: old-format
    refresh tokens have no jti/family_id and thus no matching DB row, so they
    naturally fail lookup in app/modules/auth/service.py regardless.
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        return None

    if payload.get("type") != "refresh":
        return None
    return payload
