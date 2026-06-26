import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.auth import get_current_user
from app.modules.likes.schemas import LikeResponse
from app.modules.likes.service import toggle_like
from app.modules.users.models import User

router = APIRouter(prefix="/posts", tags=["Likes"])


@router.post("/{post_id}/like", response_model=LikeResponse)
async def toggle_like_endpoint(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LikeResponse:
    return await toggle_like(post_id=post_id, user_id=current_user.id, db=db)
