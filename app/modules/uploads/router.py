from fastapi import APIRouter, Depends

from app.core.security.auth import get_current_user
from app.modules.uploads.schemas import UploadUrlRequest, UploadUrlResponse
from app.modules.uploads.service import get_upload_url

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/url", response_model=UploadUrlResponse)
async def request_upload_url(
    req: UploadUrlRequest,
    current_user=Depends(get_current_user),
) -> UploadUrlResponse:
    return get_upload_url(user_id=current_user.id, req=req)
