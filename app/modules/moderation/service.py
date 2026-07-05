import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.comments.models import Comment
from app.modules.follows.models import Follow
from app.modules.moderation.models import Block, Report
from app.modules.moderation.schemas import ReportCreate, ReportTargetType
from app.modules.posts.models import Post
from app.modules.users.models import User


async def is_blocked_either_way(
    user_a_id: uuid.UUID, user_b_id: uuid.UUID, db: AsyncSession
) -> bool:
    """True if either user has blocked the other."""
    result = await db.execute(
        select(Block.id).where(
            or_(
                (Block.blocker_id == user_a_id) & (Block.blocked_id == user_b_id),
                (Block.blocker_id == user_b_id) & (Block.blocked_id == user_a_id),
            )
        )
    )
    return result.first() is not None


async def get_blocked_user_ids(user_id: uuid.UUID, db: AsyncSession) -> set[uuid.UUID]:
    """All user ids that are blocked from `user_id`'s perspective, in either direction —
    used to filter feeds/search so blocked content never surfaces for either party."""
    result = await db.execute(
        select(Block.blocker_id, Block.blocked_id).where(
            or_(Block.blocker_id == user_id, Block.blocked_id == user_id)
        )
    )
    ids: set[uuid.UUID] = set()
    for row in result:
        ids.add(row.blocker_id)
        ids.add(row.blocked_id)
    ids.discard(user_id)
    return ids


async def block_user(blocker_id: uuid.UUID, username: str, db: AsyncSession) -> None:
    result = await db.execute(select(User).where(User.username == username))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    if target.id == blocker_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot block yourself."
        )

    existing = await db.execute(
        select(Block).where(
            Block.blocker_id == blocker_id, Block.blocked_id == target.id
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(Block(blocker_id=blocker_id, blocked_id=target.id))

    # Blocking severs any existing follow relationship in both directions.
    follows = await db.execute(
        select(Follow).where(
            or_(
                (Follow.follower_id == blocker_id) & (Follow.followed_id == target.id),
                (Follow.follower_id == target.id) & (Follow.followed_id == blocker_id),
            )
        )
    )
    for follow in follows.scalars().all():
        await db.delete(follow)

    await db.commit()


async def unblock_user(blocker_id: uuid.UUID, username: str, db: AsyncSession) -> None:
    result = await db.execute(select(User).where(User.username == username))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    existing = await db.execute(
        select(Block).where(
            Block.blocker_id == blocker_id, Block.blocked_id == target.id
        )
    )
    block = existing.scalar_one_or_none()
    if block:
        await db.delete(block)
        await db.commit()


async def list_blocked_users(
    blocker_id: uuid.UUID, db: AsyncSession
) -> list[dict[str, object]]:
    result = await db.execute(
        select(User, Block.created_at)
        .join(Block, Block.blocked_id == User.id)
        .where(Block.blocker_id == blocker_id)
        .order_by(Block.created_at.desc())
    )
    return [
        {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "blocked_at": blocked_at,
        }
        for user, blocked_at in result.all()
    ]


async def create_report(
    reporter_id: uuid.UUID, req: ReportCreate, db: AsyncSession
) -> Report:
    exists: object | None
    if req.target_type == ReportTargetType.user:
        if req.target_id == reporter_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot report yourself.",
            )
        exists = await db.get(User, req.target_id)
    elif req.target_type == ReportTargetType.post:
        exists = await db.get(Post, req.target_id)
    else:
        exists = await db.get(Comment, req.target_id)

    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reported content not found."
        )

    report = Report(
        reporter_id=reporter_id,
        target_type=req.target_type.value,
        target_id=req.target_id,
        reason=req.reason.value,
        details=req.details,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report
