from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.auth import get_current_user
from app.modules.notifications.schemas import DeviceResponse, RegisterDeviceRequest
from app.modules.notifications.service import register_device, unregister_device
from app.modules.users.models import User

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post("", response_model=DeviceResponse)
async def register_device_endpoint(
    req: RegisterDeviceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeviceResponse:
    """Register (or refresh) this device's FCM push token for the current user."""
    return await register_device(user_id=current_user.id, req=req, db=db)


@router.delete("/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_device_endpoint(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Unregister this device's push token (called on logout)."""
    await unregister_device(user_id=current_user.id, token=token, db=db)
