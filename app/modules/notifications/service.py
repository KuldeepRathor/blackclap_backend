import uuid
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
    bumped. Uses a single atomic INSERT .. ON CONFLICT so two near-simultaneous
    registrations of the same token (e.g. the app firing the call twice on
    login) can't race a SELECT-then-write and hit the unique constraint.
    """
    now = datetime.now(timezone.utc)
    insert_stmt = pg_insert(DeviceToken).values(
        user_id=user_id,
        token=req.token,
        platform=req.platform,
        last_seen_at=now,
    )
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[DeviceToken.token],
        set_={
            "user_id": user_id,
            "platform": req.platform,
            "last_seen_at": now,
            "deleted_at": None,
        },
    )
    await db.execute(upsert_stmt)
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
