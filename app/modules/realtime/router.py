"""
WebSocket endpoint for realtime chat delivery.

GET (upgrade) /api/v1/ws/chat?token=<jwt>

The connection is authenticated with the same JWT used by REST. The server
pushes `message.new` / `message.read` / `typing` / `presence` frames; the client
may send `ping`, `typing`, and `message.read` frames.
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.database.session import async_session
from app.core.websocket import events
from app.core.websocket.auth import WS_AUTH_FAILED_CODE, authenticate_websocket
from app.core.websocket.manager import manager
from app.core.websocket.pubsub import pubsub
from app.modules.realtime.service import handle_read, handle_typing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["Realtime"])


@router.websocket("/chat")
async def chat_ws(websocket: WebSocket) -> None:
    user = await authenticate_websocket(websocket)
    if user is None:
        await websocket.close(code=WS_AUTH_FAILED_CODE)
        return

    await websocket.accept()
    is_first = await manager.add(user.id, websocket)
    if is_first:
        await pubsub.subscribe_user(user.id)
        await pubsub.mark_online(user.id)

    try:
        while True:
            try:
                frame = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except (json.JSONDecodeError, ValueError, TypeError):
                continue  # tolerate malformed frames

            if not isinstance(frame, dict):
                continue
            ftype = frame.get("type")
            data = frame.get("data") or {}

            if ftype == events.EVENT_PING:
                await pubsub.refresh_presence(user.id)
                await websocket.send_json(events.pong())
            elif ftype == events.EVENT_TYPING:
                async with async_session() as db:
                    await handle_typing(user, data, db)
            elif ftype == events.EVENT_MESSAGE_READ:
                async with async_session() as db:
                    await handle_read(user, data, db)
            # Unknown frame types are ignored (forward-compatible).
    except WebSocketDisconnect:
        pass
    except Exception:  # pragma: no cover
        logger.exception("WebSocket error for user %s", user.id)
    finally:
        is_last = await manager.remove(user.id, websocket)
        if is_last:
            await pubsub.unsubscribe_user(user.id)
            await pubsub.mark_offline(user.id)
