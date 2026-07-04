"""
Scheduled permanent-deletion job for accounts past the soft-delete grace period.

For each user with `is_active=False` and `deleted_at` older than
GRACE_PERIOD_DAYS, this task:
  * hard-deletes the user's OWN content & actions — posts (cascading to media,
    likes, saves, tags and comments on those posts), the user's own likes/saves,
    and their follow edges (both directions);
  * keeps but anonymizes CROSS-user content — chat messages and comments the
    user left on other people's posts stay (so the other party's history/threads
    remain intact) and simply attribute to "Deleted User"; media on the user's
    messages is stripped;
  * scrubs PII on the user row, keeping it as a tombstone so the kept messages /
    comments still resolve to a valid (anonymized) user;
  * deletes the user's uploaded blobs from Azure.

Runs daily via Celery Beat (see app/workers/celery_app.py). Idempotent:
already-anonymized users are skipped on subsequent runs.
"""

import asyncio
import uuid

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config.settings import settings
from app.core.security.password import hash_password
from app.core.storage.azure import delete_blobs_by_prefix
from app.modules.account.service import GRACE_PERIOD_DAYS
from app.modules.chat.models import Message
from app.modules.follows.models import Follow
from app.modules.likes.models import PostLike
from app.modules.posts.models import Post
from app.modules.saves.models import PostSave
from app.modules.users.models import User
from app.workers.celery_app import celery_app

# Email domain stamped on anonymized accounts; also used to skip them on re-runs.
_ANON_EMAIL_DOMAIN = "deleted.invalid"


def _user_blob_prefixes(user_id: uuid.UUID) -> list[tuple[str, str]]:
    """(container, name-prefix) pairs covering every blob a user can own.

    Blobs are stored as `f"{upload_type}/{user_id}/..."` (see
    app/modules/uploads/service.py), so a per-user prefix scopes the delete.
    """
    uid = str(user_id)
    return [
        (settings.AZURE_POST_MEDIA_CONTAINER, f"post_image/{uid}/"),
        (settings.AZURE_POST_MEDIA_CONTAINER, f"post_video/{uid}/"),
        (settings.AZURE_POST_MEDIA_CONTAINER, f"post_audio/{uid}/"),
        (settings.AZURE_PROFILE_CONTAINER, f"profile_image/{uid}/"),
        (settings.AZURE_THUMBNAIL_CONTAINER, f"thumbnail/{uid}/"),
    ]


async def _purge() -> dict[str, int]:
    from datetime import datetime, timedelta, timezone

    engine = create_async_engine(settings.DATABASE_URL, future=True)
    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=GRACE_PERIOD_DAYS)
    purged_ids: list[uuid.UUID] = []

    try:
        async with session_maker() as db:
            result = await db.execute(
                select(User).where(
                    User.is_active.is_(False),
                    User.deleted_at.is_not(None),
                    User.deleted_at < cutoff,
                    ~User.email.like(f"%@{_ANON_EMAIL_DOMAIN}"),
                )
            )
            users = result.scalars().all()

            for user in users:
                uid = user.id

                # --- Hard-delete the user's own content & actions ---
                # Deleting posts cascades to their media, likes, saves, tags and
                # comments (including other users' comments on those posts).
                await db.execute(delete(Post).where(Post.user_id == uid))
                await db.execute(delete(PostLike).where(PostLike.user_id == uid))
                await db.execute(delete(PostSave).where(PostSave.user_id == uid))
                await db.execute(
                    delete(Follow).where(
                        or_(Follow.follower_id == uid, Follow.followed_id == uid)
                    )
                )

                # --- Anonymize & keep cross-user content ---
                # Messages stay (attribution follows the scrubbed user row); strip
                # their media so nothing personal survives and no blob dangles.
                await db.execute(
                    update(Message)
                    .where(Message.sender_id == uid)
                    .values(media_url=None, thumbnail_url=None, media_metadata=None)
                )

                # --- Scrub PII, keep the row as an anonymized tombstone ---
                short = uid.hex[:12]
                user.email = f"deleted+{uid}@{_ANON_EMAIL_DOMAIN}"
                user.username = f"deleted_user_{short}"
                user.display_name = "Deleted User"
                user.avatar_url = None
                user.bio = None
                # Unusable, but a valid bcrypt hash so verify_password never throws.
                user.hashed_password = hash_password(uuid.uuid4().hex)
                db.add(user)
                purged_ids.append(uid)

            await db.commit()
    finally:
        await engine.dispose()

    # Delete blobs AFTER the DB commit — best-effort, outside the transaction.
    blobs_deleted = 0
    for uid in purged_ids:
        for container, prefix in _user_blob_prefixes(uid):
            try:
                blobs_deleted += delete_blobs_by_prefix(container, prefix)
            except Exception:
                # Storage not configured / transient error: don't fail the purge.
                continue

    return {"users_purged": len(purged_ids), "blobs_deleted": blobs_deleted}


@celery_app.task(name="account.purge_deleted_accounts")  # type: ignore[untyped-decorator]
def purge_deleted_accounts() -> dict[str, int]:
    """Celery entrypoint: run the async purge in a fresh event loop."""
    return asyncio.run(_purge())
