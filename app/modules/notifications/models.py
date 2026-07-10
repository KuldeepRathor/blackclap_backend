import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models.base import BaseModel


class DeviceToken(BaseModel):
    """A push (FCM) registration token for one of a user's devices.

    A single physical device produces one token; a user may have several
    (multiple devices). Tokens are globally unique — if the same token shows
    up for a new user (e.g. a shared device that logged in as someone else),
    the registration endpoint re-points the row to the current user rather
    than creating a duplicate. Invalid tokens (reported UNREGISTERED by FCM)
    are soft-deleted by the send_push worker.
    """

    __tablename__ = "device_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The FCM registration token. Long, opaque, unique per device.
    token: Mapped[str] = mapped_column(
        String(512), unique=True, nullable=False, index=True
    )
    # "android" | "ios"
    platform: Mapped[str] = mapped_column(String(10), nullable=False, default="android")
    # Refreshed on every re-registration so stale tokens can be aged out later.
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<DeviceToken id={self.id} user_id={self.user_id} "
            f"platform={self.platform}>"
        )
