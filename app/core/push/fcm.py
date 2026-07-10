"""Firebase Cloud Messaging (FCM) sender.

Data-only push delivery. We deliberately do NOT attach an FCM `notification`
block — the client (see push_notification_service.dart) decides whether and how
to display each message so it can respect per-conversation mute and suppress
duplicates while the recipient is looking at the chat. Title/body/type/target
ids all travel in the `data` map.

The Firebase app is initialized lazily on first send from
`settings.FIREBASE_SERVICE_ACCOUNT_PATH`. If Firebase isn't configured (no
service-account file), sends become no-ops so the rest of the app keeps working
in local/dev environments without credentials.
"""

import logging
import threading
from typing import Optional

from app.core.config.settings import settings

logger = logging.getLogger(__name__)

_init_lock = threading.Lock()
_firebase_app: object | None = None  # firebase_admin.App | None
_init_failed = False


def _get_app() -> Optional[object]:
    """Lazily initialize (once) and return the firebase_admin app, or None if
    Firebase is not configured / failed to initialize."""
    global _firebase_app, _init_failed

    if _firebase_app is not None:
        return _firebase_app
    if _init_failed:
        return None

    with _init_lock:
        if _firebase_app is not None:
            return _firebase_app
        if _init_failed:
            return None

        path = settings.FIREBASE_SERVICE_ACCOUNT_PATH
        if not path:
            logger.warning(
                "FCM disabled: FIREBASE_SERVICE_ACCOUNT_PATH is not set. "
                "Push notifications will be skipped."
            )
            _init_failed = True
            return None

        try:
            import firebase_admin
            from firebase_admin import credentials

            cred = credentials.Certificate(path)
            options = (
                {"projectId": settings.FIREBASE_PROJECT_ID}
                if settings.FIREBASE_PROJECT_ID
                else None
            )
            _firebase_app = firebase_admin.initialize_app(cred, options)
            logger.info("Firebase Admin initialized for FCM push delivery.")
        except Exception:  # pragma: no cover - config/credential errors
            logger.exception("Failed to initialize Firebase Admin; FCM disabled.")
            _init_failed = True
            return None

    return _firebase_app


def send_to_tokens(
    tokens: list[str],
    title: str,
    body: str,
    data: Optional[dict[str, str]] = None,
) -> list[str]:
    """Send a data-only push to every token. Returns the subset of tokens that
    FCM reported as permanently invalid (unregistered / bad token) so the caller
    can soft-delete them. On any hard failure returns an empty list (nothing to
    prune)."""
    if not tokens:
        return []

    app = _get_app()
    if app is None:
        return []

    from firebase_admin import messaging

    # Everything travels in `data` (all values must be strings for FCM).
    payload: dict[str, str] = {
        "title": title,
        "body": body,
    }
    if data:
        payload.update({k: str(v) for k, v in data.items()})

    message = messaging.MulticastMessage(
        tokens=tokens,
        data=payload,
        android=messaging.AndroidConfig(priority="high"),
    )

    dead_tokens: list[str] = []
    try:
        response = messaging.send_each_for_multicast(message, app=app)
    except Exception:  # pragma: no cover - network/credential errors
        logger.exception("FCM multicast send failed for %d tokens", len(tokens))
        return []

    for token, resp in zip(tokens, response.responses):
        if resp.success:
            continue
        exc = resp.exception
        if isinstance(
            exc,
            (
                messaging.UnregisteredError,
                messaging.SenderIdMismatchError,
            ),
        ):
            dead_tokens.append(token)
        else:
            logger.warning("FCM send error for a token: %s", exc)

    if dead_tokens:
        logger.info("FCM reported %d dead tokens (will be pruned)", len(dead_tokens))

    return dead_tokens
