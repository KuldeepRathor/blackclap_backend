import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config.settings import settings
from app.core.security.auth import get_current_user
from app.core.storage.azure import generate_sas_upload_url
from app.modules.media.schemas import PresignedUrlRequest, PresignedUrlResponse
from app.modules.users.models import User

router = APIRouter(prefix="/media", tags=["Media"])


@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def get_presigned_url(
    request: Request,
    payload: PresignedUrlRequest,
    current_user: User = Depends(get_current_user),
) -> Any:
    file_ext = os.path.splitext(payload.file_name)[1].lower()
    if not file_ext:
        if "jpeg" in payload.file_type or "jpg" in payload.file_type:
            file_ext = ".jpg"
        elif "png" in payload.file_type:
            file_ext = ".png"
        elif "mp4" in payload.file_type:
            file_ext = ".mp4"
        else:
            file_ext = ".bin"

    if payload.purpose == "avatar":
        file_key = f"avatars/{current_user.id}{file_ext}"
        container = settings.AZURE_PROFILE_CONTAINER
    else:
        file_key = f"posts/{current_user.id}/{uuid.uuid4()}{file_ext}"
        container = settings.AZURE_POST_MEDIA_CONTAINER

    azure_configured = bool(settings.AZURE_STORAGE_CONNECTION_STRING)

    if azure_configured:
        try:
            upload_url, download_url = generate_sas_upload_url(
                container=container,
                blob_name=file_key,
                content_type=payload.file_type,
            )
            return {
                "upload_url": upload_url,
                "download_url": download_url,
                "file_key": file_key,
                "is_local": False,
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Azure SAS generation failed: {e}",
            )
    else:
        if not settings.DEBUG:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Media storage is not configured.",
            )
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        base_url_str = f"{scheme}://{request.url.netloc}/"
        upload_url = f"{base_url_str}api/v1/media/local-upload?file_key={file_key}"
        download_url = f"{base_url_str}static/uploads/{file_key}"
        return {
            "upload_url": upload_url,
            "download_url": download_url,
            "file_key": file_key,
            "is_local": True,
        }


@router.put("/local-upload")
async def local_upload_emulator(
    request: Request,
    file_key: str,
) -> Any:
    # Dev-only Azure emulator — an unauthenticated write endpoint has no place
    # in production, where real Azure SAS uploads are used instead.
    if not settings.DEBUG:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")

    clean_key = os.path.normpath(file_key).lstrip("/")
    if clean_key.startswith("..") or ".." in clean_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file key path.",
        )

    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(os.path.dirname(current_dir))
    static_uploads_dir = os.path.join(app_dir, "static", "uploads")

    dest_path = os.path.abspath(os.path.join(static_uploads_dir, clean_key))

    if not dest_path.startswith(os.path.abspath(static_uploads_dir)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid destination path.",
        )

    try:
        body_data = await request.body()
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(body_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write file locally: {e}",
        )

    return {"status": "success", "file_key": clean_key}
