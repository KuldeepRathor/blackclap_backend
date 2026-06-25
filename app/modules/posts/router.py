from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.auth import get_current_user
from app.modules.posts.schemas import CreatePostRequest, PostResponse
from app.modules.posts.service import create_post, get_user_posts
from app.modules.users.models import User

router = APIRouter(prefix="/posts", tags=["Posts"])


@router.get("/me", response_model=list[PostResponse])
async def get_my_posts_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PostResponse]:
    return await get_user_posts(user_id=current_user.id, db=db)


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post_endpoint(
    req: CreatePostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostResponse:
    return await create_post(user_id=current_user.id, req=req, db=db)
