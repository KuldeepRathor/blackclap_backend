"""
WebSocket handshake authentication.

The HTTP `OAuth2PasswordBearer` dependency used by `get_current_user` does not
apply to WebSocket routes, so we authenticate the handshake here using the same
JWT (same secret/format issued by app.modules.auth). The token is passed as a
query param (`?token=...`) because browsers/most WS clients cannot set an
Authorization header on the upgrade request.
"""

import uuid
from typing import Optional

from fastapi import WebSocket
from sqlalchemy import select

from app.core.database.session import async_session
from app.core.security.jwt import decode_access_token
from app.modules.users.models import User

# Custom close code for an authentication failure (4000-4999 = application range).
WS_AUTH_FAILED_CODE = 4401


async def authenticate_websocket(websocket: WebSocket) -> Optional[User]:
    """Validate the handshake token and return the User, or None if invalid.

    The caller is responsible for closing the socket with WS_AUTH_FAILED_CODE
    when this returns None (before calling `accept()`).
    """
    token = websocket.query_params.get("token")
    if not token:
        # Fallback: allow an Authorization: Bearer header if the client set one.
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:]
    if not token:
        return None

    payload = decode_access_token(token)
    if payload is None:
        return None

    user_id_str = payload.get("sub")
    if not user_id_str:
        return None
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        return None

    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        return None

    return user
