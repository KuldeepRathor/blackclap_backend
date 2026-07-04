from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.auth import get_current_user
from app.modules.search.schemas import SearchResponse
from app.modules.search.service import search_all, search_posts, search_users
from app.modules.users.models import User

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("", response_model=SearchResponse)
async def search_endpoint(
    q: str = Query(..., min_length=2, max_length=100, description="Search query"),
    type: Literal["all", "users", "posts"] = Query(
        default="all",
        description=(
            "Result type: all (preview), users (paginated), posts (cursor-paginated)"
        ),
    ),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0, description="Page offset for type=users"),
    cursor: str | None = Query(
        default=None, description="Cursor for type=posts pagination"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    if type == "users":
        users = await search_users(
            query=q,
            requesting_user_id=current_user.id,
            db=db,
            limit=limit,
            offset=offset,
        )
        return SearchResponse(users=users)

    if type == "posts":
        posts, next_cursor = await search_posts(
            query=q,
            requesting_user_id=current_user.id,
            db=db,
            limit=limit,
            cursor=cursor,
        )
        return SearchResponse(posts=posts, next_cursor=next_cursor)

    # type == "all": preview of both
    return await search_all(
        query=q,
        requesting_user_id=current_user.id,
        db=db,
    )
