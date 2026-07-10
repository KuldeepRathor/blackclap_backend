"""Celery task: deliver a push notification to one user's devices via FCM.

Enqueued from the service layer at each event source (new chat message, like,
comment, follow). The task loads the recipient's active device tokens, sends a
data-only FCM message, and soft-deletes any tokens FCM reports as dead.

Follows the pattern in app/workers/tasks/refresh_token_cleanup.py: a sync
Celery entrypoint that runs an async body in a fresh event loop + engine.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config.settings import settings
from app.core.push import fcm
from app.modules.notifications.models import DeviceToken
from app.workers.celery_app import celery_app


async def _send(
    recipient_id: str,
    title: str,
    body: str,
    data: Optional[dict[str, str]],
) -> dict[str, int]:
    engine = create_async_engine(settings.DATABASE_URL, future=True)
    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with session_maker() as db:
            rows = await db.execute(
                select(DeviceToken.token).where(
                    DeviceToken.user_id == uuid.UUID(recipient_id),
                    DeviceToken.deleted_at.is_(None),
                )
            )
            tokens = [r[0] for r in rows]
            if not tokens:
                return {"tokens": 0, "pruned": 0}

            # fcm.send_to_tokens is blocking (firebase-admin is sync); run it off
            # the event loop so we don't stall other async work in this worker.
            dead = await asyncio.to_thread(
                fcm.send_to_tokens, tokens, title, body, data
            )

            if dead:
                await db.execute(
                    update(DeviceToken)
                    .where(DeviceToken.token.in_(dead))
                    .values(deleted_at=datetime.now(timezone.utc))
                )
                await db.commit()

            return {"tokens": len(tokens), "pruned": len(dead)}
    finally:
        await engine.dispose()


@celery_app.task(name="notifications.send_push")  # type: ignore[untyped-decorator]
def send_push(
    recipient_id: str,
    title: str,
    body: str,
    data: Optional[dict[str, str]] = None,
) -> dict[str, int]:
    """Celery entrypoint: run the async send in a fresh event loop."""
    return asyncio.run(_send(recipient_id, title, body, data))
