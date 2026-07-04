"""
Handlers for inbound WebSocket frames (typing / read receipts).

These delegate to the chat service for persistence and to the Redis publisher
for fan-out, so there is a single source of truth regardless of whether an
action arrives over REST or WS.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket import events
from app.core.websocket.pubsub import pubsub
from app.modules.chat.models import ConversationParticipant
from app.modules.chat.schemas import MarkReadRequest
from app.modules.chat.service import mark_read
from app.modules.users.models import User


async def _other_participant_ids(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[uuid.UUID]:
    result = await db.execute(
        select(ConversationParticipant.user_id).where(
            ConversationParticipant.conversation_id == conversation_id
        )
    )
    ids = list(result.scalars().all())
    if user_id not in ids:
        return []  # not a participant — ignore
    return [i for i in ids if i != user_id]


async def handle_typing(user: User, data: dict[str, Any], db: AsyncSession) -> None:
    raw = data.get("conversation_id")
    try:
        conversation_id = uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return
    is_typing = bool(data.get("is_typing", False))
    others = await _other_participant_ids(conversation_id, user.id, db)
    if not others:
        return
    payload = events.typing(str(conversation_id), str(user.id), is_typing)
    await pubsub.publish_to_users(others, payload)


async def handle_read(user: User, data: dict[str, Any], db: AsyncSession) -> None:
    try:
        conversation_id = uuid.UUID(str(data.get("conversation_id")))
        last_read_message_id = uuid.UUID(str(data.get("last_read_message_id")))
    except (ValueError, TypeError):
        return
    try:
        await mark_read(
            conversation_id,
            user.id,
            MarkReadRequest(last_read_message_id=last_read_message_id),
            db,
        )
    except Exception:
        # Not a participant / invalid — silently ignore on the realtime path.
        return
