import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.auth import get_current_user
from app.modules.chat.schemas import (
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
    MarkReadRequest,
    MarkReadResponse,
    MessageListResponse,
    MessageResponse,
    SendMessageRequest,
    UnreadCountResponse,
)
from app.modules.chat.service import (
    get_messages,
    get_or_create_dm,
    list_conversations,
    mark_read,
    send_message,
    total_unread,
)
from app.modules.users.models import User

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations_endpoint(
    limit: int = Query(30, ge=1, le=50),
    after_cursor: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    return await list_conversations(
        user_id=current_user.id, db=db, limit=limit, after_cursor=after_cursor
    )


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
)
async def create_conversation_endpoint(
    req: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Get-or-create a 1:1 DM. Idempotent: returns the existing DM if one exists."""
    return await get_or_create_dm(
        user_id=current_user.id, participant_id=req.participant_id, db=db
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    return await total_unread(user_id=current_user.id, db=db)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
)
async def list_messages_endpoint(
    conversation_id: uuid.UUID,
    limit: int = Query(30, ge=1, le=50),
    after_cursor: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageListResponse:
    return await get_messages(
        conversation_id=conversation_id,
        user_id=current_user.id,
        db=db,
        limit=limit,
        after_cursor=after_cursor,
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message_endpoint(
    conversation_id: uuid.UUID,
    req: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    return await send_message(
        conversation_id=conversation_id, sender_id=current_user.id, req=req, db=db
    )


@router.post(
    "/conversations/{conversation_id}/read",
    response_model=MarkReadResponse,
)
async def mark_read_endpoint(
    conversation_id: uuid.UUID,
    req: MarkReadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MarkReadResponse:
    return await mark_read(
        conversation_id=conversation_id, user_id=current_user.id, req=req, db=db
    )
