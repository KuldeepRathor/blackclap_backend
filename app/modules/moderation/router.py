from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.auth import get_current_user
from app.modules.moderation.schemas import (
    BlockActionResponse,
    BlockedUserResponse,
    ReportCreate,
    ReportResponse,
)
from app.modules.moderation.service import (
    block_user,
    create_report,
    list_blocked_users,
    unblock_user,
)
from app.modules.users.models import User

router = APIRouter(tags=["Moderation"])


@router.post("/block/{username}", response_model=BlockActionResponse)
async def block_user_endpoint(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BlockActionResponse:
    """Block a user: hides their content from your feed/search, unfollows in
    both directions, and prevents future DMs between the two accounts."""
    await block_user(current_user.id, username, db)
    return BlockActionResponse(is_blocked=True)


@router.delete("/block/{username}", response_model=BlockActionResponse)
async def unblock_user_endpoint(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BlockActionResponse:
    await unblock_user(current_user.id, username, db)
    return BlockActionResponse(is_blocked=False)


@router.get("/block", response_model=list[BlockedUserResponse])
async def list_blocked_users_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BlockedUserResponse]:
    rows = await list_blocked_users(current_user.id, db)
    return [BlockedUserResponse.model_validate(row) for row in rows]


@router.post(
    "/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED
)
async def create_report_endpoint(
    req: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """Report a user, post, or comment for moderation review."""
    report = await create_report(current_user.id, req, db)
    return ReportResponse.model_validate(report)
