"""Fire-and-forget helper to enqueue a push notification from the service layer.

Dispatches the `notifications.send_push` Celery task by name so callers don't
import the task module (or firebase-admin) directly — keeps the request path
decoupled and avoids import cycles. Enqueue failures (e.g. broker down) are
swallowed and logged: a missed push must never break the underlying action
(sending a message, liking a post, etc.).
"""

import logging
import uuid
from typing import Optional

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def enqueue_push(
    recipient_id: uuid.UUID,
    title: str,
    body: str,
    data: Optional[dict[str, str]] = None,
) -> None:
    try:
        celery_app.send_task(
            "notifications.send_push",
            args=[str(recipient_id), title, body, data or {}],
        )
    except Exception:  # pragma: no cover - broker/transport errors
        logger.exception("Failed to enqueue push for recipient %s", recipient_id)
