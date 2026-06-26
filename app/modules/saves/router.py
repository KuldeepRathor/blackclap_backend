import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.auth import get_current_user
from app.modules.posts.schemas import FeedPostResponse
from app.modules.posts.service import get_saved_posts_feed
from app.modules.saves import service
from app.modules.saves.schemas import SaveResponse
from app.modules.users.models import User

router = APIRouter(tags=["saves"])


@router.post("/posts/{post_id}/save", response_model=SaveResponse)
async def toggle_save(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SaveResponse:
    return await service.toggle_save(post_id, current_user.id, db)


@router.get("/users/me/saved-posts", response_model=list[FeedPostResponse])
async def get_saved_posts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FeedPostResponse]:
    return await get_saved_posts_feed(current_user.id, db)
