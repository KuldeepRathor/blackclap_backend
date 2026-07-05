"""
Scheduled sweep for dead refresh_tokens rows.

Deletes rows that are long past their usefulness — either well past their own
expiry, or revoked a while ago (rotated-away or logged-out tokens). A small
retention buffer is kept past the actual cutoff so a row is never deleted
while it might still be useful for debugging a recent incident.

Runs daily via Celery Beat (see app/workers/celery_app.py).
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from sqlalchemy import CursorResult, delete, or_
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config.settings import settings
from app.modules.auth.models import RefreshToken
from app.workers.celery_app import celery_app

_RETENTION_BUFFER_DAYS = 7


async def _cleanup() -> dict[str, int]:
    engine = create_async_engine(settings.DATABASE_URL, future=True)
    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_BUFFER_DAYS)

    try:
        async with session_maker() as db:
            result = await db.execute(
                delete(RefreshToken).where(
                    or_(
                        RefreshToken.expires_at < cutoff,
                        RefreshToken.revoked_at < cutoff,
                    )
                )
            )
            await db.commit()
            deleted = cast(CursorResult[Any], result).rowcount or 0
    finally:
        await engine.dispose()

    return {"refresh_tokens_deleted": deleted}


@celery_app.task(name="auth.cleanup_expired_refresh_tokens")  # type: ignore[untyped-decorator]
def cleanup_expired_refresh_tokens() -> dict[str, int]:
    """Celery entrypoint: run the async cleanup in a fresh event loop."""
    return asyncio.run(_cleanup())
