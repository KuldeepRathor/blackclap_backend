import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import DeviceToken
from app.modules.notifications.schemas import DeviceResponse, RegisterDeviceRequest


async def register_device(
    user_id: uuid.UUID,
    req: RegisterDeviceRequest,
    db: AsyncSession,
) -> DeviceResponse:
    """Upsert a device token for the current user.

    Idempotent on the token string. If the token already exists (even for a
    different user, e.g. a shared device that switched accounts) it is
    re-pointed to the current user and un-soft-deleted, and `last_seen_at` is
    bumped.
    """
    now = datetime.now(timezone.utc)
    existing = await db.scalar(
        select(DeviceToken).where(DeviceToken.token == req.token)
    )

    if existing is not None:
        existing.user_id = user_id
        existing.platform = req.platform
        existing.last_seen_at = now
        existing.deleted_at = None
    else:
        db.add(
            DeviceToken(
                user_id=user_id,
                token=req.token,
                platform=req.platform,
                last_seen_at=now,
            )
        )

    await db.commit()
    return DeviceResponse(token=req.token, platform=req.platform, registered=True)


async def unregister_device(
    user_id: uuid.UUID,
    token: str,
    db: AsyncSession,
) -> None:
    """Soft-delete a token on logout. Scoped to the current user so one user
    can't unregister another's device."""
    await db.execute(
        update(DeviceToken)
        .where(
            DeviceToken.token == token,
            DeviceToken.user_id == user_id,
            DeviceToken.deleted_at.is_(None),
        )
        .values(deleted_at=datetime.now(timezone.utc))
    )
    await db.commit()
