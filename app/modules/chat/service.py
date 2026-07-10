import base64
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket import events
from app.core.websocket.pubsub import pubsub
from app.modules.chat.models import Conversation, ConversationParticipant, Message
from app.modules.chat.schemas import (
    ConversationListResponse,
    ConversationResponse,
    MarkReadRequest,
    MarkReadResponse,
    MessageListResponse,
    MessageResponse,
    ParticipantInfo,
    SendMessageRequest,
    UnreadCountResponse,
    UserSnippet,
)
from app.modules.moderation.service import is_blocked_either_way
from app.modules.notifications.dispatch import enqueue_push
from app.modules.users.models import User

# ---------------------------------------------------------------------------
# Cursor helpers — encode (timestamp ISO string, id). Same scheme as comments.
# ---------------------------------------------------------------------------


def _encode_cursor(ts: datetime, row_id: uuid.UUID) -> str:
    raw = f"{ts.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_str, id_str = raw.split("|", 1)
        return datetime.fromisoformat(ts_str), uuid.UUID(id_str)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor"
        )


def _dm_key(a: uuid.UUID, b: uuid.UUID) -> str:
    lo, hi = sorted([str(a), str(b)])
    return f"{lo}:{hi}"


def _preview(req: SendMessageRequest) -> str | None:
    if req.type.value == "text":
        return (req.content or "")[:200]
    if req.type.value == "image":
        return "\U0001f4f7 Photo"
    if req.type.value == "video":
        return "\U0001f3a5 Video"
    return (req.content or "")[:200]


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------


def _build_message_response(msg: Message) -> MessageResponse:
    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        sender_id=msg.sender_id,
        sender=UserSnippet.model_validate(msg.sender)
        if msg.sender is not None
        else None,
        type=msg.type,
        content=msg.content,
        media_url=msg.media_url,
        media_type=msg.media_type,
        thumbnail_url=msg.thumbnail_url,
        client_message_id=msg.client_message_id,
        created_at=msg.created_at,
    )


async def _ensure_participants(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[ConversationParticipant]:
    """Return all participant rows for a conversation, raising 403 if the
    requesting user is not one of them (also covers nonexistent conversations)."""
    result = await db.execute(
        select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id
        )
    )
    participants = list(result.scalars().all())
    if not any(p.user_id == user_id for p in participants):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant of this conversation",
        )
    return participants


async def _load_conversation_response(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> ConversationResponse:
    conv = await db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )

    part_result = await db.execute(
        select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id
        )
    )
    parts = list(part_result.scalars().all())

    participants = [
        ParticipantInfo(
            user=UserSnippet.model_validate(p.user),
            role=p.role,
            last_read_at=p.last_read_at,
        )
        for p in parts
    ]
    me = next((p for p in parts if p.user_id == user_id), None)
    unread = me.unread_count if me else 0

    last_message = None
    if conv.last_message_id is not None:
        last_message_obj = await db.get(Message, conv.last_message_id)
        if last_message_obj is not None:
            last_message = _build_message_response(last_message_obj)

    return ConversationResponse(
        id=conv.id,
        type=conv.type,
        title=conv.title,
        avatar_url=conv.avatar_url,
        participants=participants,
        last_message=last_message,
        last_message_preview=conv.last_message_preview,
        last_message_at=conv.last_message_at,
        last_message_sender_id=conv.last_message_sender_id,
        unread_count=unread,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


# ---------------------------------------------------------------------------
# Get-or-create a 1:1 DM (idempotent, race-safe via partial unique dm_key)
# ---------------------------------------------------------------------------


async def get_or_create_dm(
    user_id: uuid.UUID,
    participant_id: uuid.UUID,
    db: AsyncSession,
) -> ConversationResponse:
    if user_id == participant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot start a conversation with yourself",
        )

    other = await db.get(User, participant_id)
    if other is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if await is_blocked_either_way(user_id, participant_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot message this user.",
        )

    key = _dm_key(user_id, participant_id)

    existing = await db.execute(select(Conversation).where(Conversation.dm_key == key))
    conv = existing.scalar_one_or_none()
    if conv is not None:
        return await _load_conversation_response(conv.id, user_id, db)

    # Insert atomically; ON CONFLICT handles a concurrent first-message-from-both.
    insert_stmt = (
        pg_insert(Conversation)
        .values(type="direct", dm_key=key)
        .on_conflict_do_nothing(
            index_elements=[Conversation.dm_key],
            index_where=text("dm_key IS NOT NULL"),
        )
        .returning(Conversation.id)
    )
    result = await db.execute(insert_stmt)
    new_id = result.scalar_one_or_none()

    if new_id is not None:
        now = datetime.now(timezone.utc)
        db.add_all(
            [
                ConversationParticipant(
                    conversation_id=new_id,
                    user_id=user_id,
                    role="member",
                    joined_at=now,
                ),
                ConversationParticipant(
                    conversation_id=new_id,
                    user_id=participant_id,
                    role="member",
                    joined_at=now,
                ),
            ]
        )
        await db.commit()
        conv_id = new_id
    else:
        # Lost the race — another request created it; commit the no-op and re-read.
        await db.commit()
        res = await db.execute(
            select(Conversation.id).where(Conversation.dm_key == key)
        )
        conv_id = res.scalar_one()

    return await _load_conversation_response(conv_id, user_id, db)


# ---------------------------------------------------------------------------
# List conversations (most recent activity first, cursor-paginated)
# ---------------------------------------------------------------------------


async def list_conversations(
    user_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 30,
    after_cursor: str | None = None,
) -> ConversationListResponse:
    # Effective activity timestamp: last message time, or creation time if no
    # messages yet (keeps brand-new DMs visible and avoids NULL cursor handling).
    activity = func.coalesce(Conversation.last_message_at, Conversation.created_at)

    stmt = (
        select(Conversation)
        .join(
            ConversationParticipant,
            ConversationParticipant.conversation_id == Conversation.id,
        )
        .where(
            ConversationParticipant.user_id == user_id,
            ConversationParticipant.left_at.is_(None),
            Conversation.deleted_at.is_(None),
        )
        .order_by(activity.desc(), Conversation.id.desc())
    )

    if after_cursor:
        cursor_dt, cursor_id = _decode_cursor(after_cursor)
        stmt = stmt.where(
            or_(
                activity < cursor_dt,
                and_(activity == cursor_dt, Conversation.id < cursor_id),
            )
        )

    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    convs = list(result.scalars().all())

    has_more = len(convs) > limit
    convs = convs[:limit]

    responses = [await _load_conversation_response(c.id, user_id, db) for c in convs]

    next_cursor = None
    if has_more and convs:
        last = convs[-1]
        next_cursor = _encode_cursor(last.last_message_at or last.created_at, last.id)

    return ConversationListResponse(conversations=responses, next_cursor=next_cursor)


# ---------------------------------------------------------------------------
# Message history (newest first, cursor-paginated)
# ---------------------------------------------------------------------------


async def get_messages(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 30,
    after_cursor: str | None = None,
) -> MessageListResponse:
    await _ensure_participants(conversation_id, user_id, db)

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.deleted_at.is_(None))
        .order_by(Message.created_at.desc(), Message.id.desc())
    )

    if after_cursor:
        cursor_dt, cursor_id = _decode_cursor(after_cursor)
        stmt = stmt.where(
            or_(
                Message.created_at < cursor_dt,
                and_(Message.created_at == cursor_dt, Message.id < cursor_id),
            )
        )

    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    rows = rows[:limit]

    responses = [_build_message_response(m) for m in rows]
    next_cursor = (
        _encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    )

    return MessageListResponse(messages=responses, next_cursor=next_cursor)


# ---------------------------------------------------------------------------
# Send a message (single write path: persist + denormalize + unread + publish)
# ---------------------------------------------------------------------------


async def send_message(
    conversation_id: uuid.UUID,
    sender_id: uuid.UUID,
    req: SendMessageRequest,
    db: AsyncSession,
) -> MessageResponse:
    participants = await _ensure_participants(conversation_id, sender_id, db)
    participant_ids = [p.user_id for p in participants]

    for other_id in participant_ids:
        if other_id != sender_id and await is_blocked_either_way(
            sender_id, other_id, db
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot message this user.",
            )

    insert_stmt = pg_insert(Message).values(
        conversation_id=conversation_id,
        sender_id=sender_id,
        type=req.type.value,
        content=req.content,
        media_url=req.media_url,
        media_type=req.media_type,
        thumbnail_url=req.thumbnail_url,
        client_message_id=req.client_message_id,
    )
    if req.client_message_id is not None:
        insert_stmt = insert_stmt.on_conflict_do_nothing(
            index_elements=[Message.conversation_id, Message.client_message_id],
            index_where=text("client_message_id IS NOT NULL"),
        )

    result = await db.execute(insert_stmt.returning(Message.id, Message.created_at))
    row = result.first()

    if row is None:
        # Idempotent retry: this client_message_id was already persisted. Return
        # the existing message without re-incrementing unread or re-publishing.
        await db.commit()
        existing = await db.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.client_message_id == req.client_message_id,
            )
        )
        msg = existing.scalar_one()
        return _build_message_response(msg)

    new_id, created_at = row

    # Denormalize last-message onto the conversation.
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(
            last_message_id=new_id,
            last_message_at=created_at,
            last_message_preview=_preview(req),
            last_message_sender_id=sender_id,
        )
    )
    # Bump unread for every recipient (not the sender).
    await db.execute(
        update(ConversationParticipant)
        .where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id != sender_id,
        )
        .values(unread_count=ConversationParticipant.unread_count + 1)
    )
    await db.commit()

    # Reload with sender for the response (sender relationship is lazy="joined").
    reloaded = await db.execute(select(Message).where(Message.id == new_id))
    msg = reloaded.scalar_one()
    response = _build_message_response(msg)

    # Fan out live to every participant (including the sender's other devices).
    payload = events.message_new(response.model_dump(mode="json"))
    await pubsub.publish_to_users(participant_ids, payload)

    # Enqueue a push for each recipient. Delivery always goes out via FCM; the
    # client suppresses it locally if that recipient is foregrounded on this
    # chat (it already got the live WebSocket update). Muted participants are
    # skipped here so a muted DM never pushes.
    sender_name = next(
        (
            p.user.display_name or p.user.username
            for p in participants
            if p.user_id == sender_id
        ),
        "New message",
    )
    preview = _preview(req) or "Sent you a message"
    for p in participants:
        if p.user_id == sender_id or p.is_muted:
            continue
        enqueue_push(
            recipient_id=p.user_id,
            title=sender_name,
            body=preview,
            data={"type": "chat", "conversation_id": str(conversation_id)},
        )

    return response


# ---------------------------------------------------------------------------
# Mark a conversation read up to a message
# ---------------------------------------------------------------------------


async def mark_read(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    req: MarkReadRequest,
    db: AsyncSession,
) -> MarkReadResponse:
    participants = await _ensure_participants(conversation_id, user_id, db)
    now = datetime.now(timezone.utc)

    await db.execute(
        update(ConversationParticipant)
        .where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id,
        )
        .values(
            last_read_message_id=req.last_read_message_id,
            last_read_at=now,
            unread_count=0,
        )
    )
    await db.commit()

    # Publish to ALL participants, including the reader. The other side needs
    # it for the "read" tick; the reader needs their own echo so the
    # conversation-list unread badge clears in real time (and other devices of
    # the reader stay in sync).
    all_ids = [p.user_id for p in participants]
    payload = events.message_read(
        str(conversation_id),
        str(user_id),
        str(req.last_read_message_id),
        now.isoformat(),
    )
    await pubsub.publish_to_users(all_ids, payload)

    return MarkReadResponse(unread_count=0, last_read_at=now)


# ---------------------------------------------------------------------------
# Total unread across all conversations (app badge)
# ---------------------------------------------------------------------------


async def total_unread(user_id: uuid.UUID, db: AsyncSession) -> UnreadCountResponse:
    total = await db.scalar(
        select(func.coalesce(func.sum(ConversationParticipant.unread_count), 0)).where(
            ConversationParticipant.user_id == user_id,
            ConversationParticipant.left_at.is_(None),
        )
    )
    return UnreadCountResponse(total_unread=int(total or 0))
