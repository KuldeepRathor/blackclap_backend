"""
Account-deletion logic shared by the public web flow and the login-time
reactivation path.

Deletion is a *soft* delete with a grace period (see GRACE_PERIOD_DAYS):
  1. A delete request sets `is_active=False` + `deleted_at=now()`. The account is
     immediately inaccessible (`get_current_user` rejects inactive users).
  2. Logging back in within the grace period reactivates the account.
  3. After the grace period, the Celery purge task scrubs PII and content.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.password import verify_password
from app.modules.users.models import User

# How long a soft-deleted account can be recovered by simply logging in before
# it is permanently purged/anonymized.
GRACE_PERIOD_DAYS = 30


def is_within_grace_period(user: User) -> bool:
    """True if a soft-deleted user is still inside the recoverable window."""
    if user.deleted_at is None:
        return False
    deadline = user.deleted_at + timedelta(days=GRACE_PERIOD_DAYS)
    return datetime.now(timezone.utc) <= deadline


async def reactivate_account(db: AsyncSession, user: User) -> None:
    """Cancel a pending deletion: restore access and clear the delete marker."""
    user.is_active = True
    user.deleted_at = None
    db.add(user)
    await db.commit()


async def request_account_deletion(
    db: AsyncSession, email: str, password: str
) -> bool:
    """
    Verify credentials and soft-delete the matching account.

    Returns True on success, False if the email is unknown, the password is
    wrong, or the account is already inactive. Callers should show the SAME
    message regardless of the result to avoid account enumeration.
    """
    result = await db.execute(select(User).where(User.email == email))
    user: Optional[User] = result.scalar_one_or_none()

    if not user or not user.is_active:
        return False
    if not verify_password(password, user.hashed_password):
        return False

    user.is_active = False
    user.deleted_at = datetime.now(timezone.utc)
    db.add(user)
    await db.commit()
    return True
