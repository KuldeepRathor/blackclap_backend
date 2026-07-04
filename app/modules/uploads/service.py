import uuid

from fastapi import HTTPException, status

from app.core.config.settings import settings
from app.core.storage.azure import generate_sas_upload_url
from app.modules.uploads.schemas import (
    ALLOWED_EXTENSIONS,
    CONTENT_TYPE_MAP,
    UploadType,
    UploadUrlRequest,
    UploadUrlResponse,
)

CONTAINER_MAP: dict[UploadType, str] = {
    UploadType.post_image: settings.AZURE_POST_MEDIA_CONTAINER,
    UploadType.post_video: settings.AZURE_POST_MEDIA_CONTAINER,
    UploadType.post_audio: settings.AZURE_POST_MEDIA_CONTAINER,
    UploadType.profile_image: settings.AZURE_PROFILE_CONTAINER,
    UploadType.thumbnail: settings.AZURE_THUMBNAIL_CONTAINER,
}


def get_upload_url(user_id: uuid.UUID, req: UploadUrlRequest) -> UploadUrlResponse:
    ext = req.filename.rsplit(".", 1)[-1]
    allowed = ALLOWED_EXTENSIONS[req.upload_type]

    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Extension .{ext} not allowed for {req.upload_type}. "
                f"Allowed: {allowed}"
            ),
        )

    content_type = CONTENT_TYPE_MAP[ext]
    container = CONTAINER_MAP[req.upload_type]
    blob_name = f"{req.upload_type.value}/{user_id}/{uuid.uuid4()}.{ext}"

    upload_url, blob_url = generate_sas_upload_url(
        container=container,
        blob_name=blob_name,
        content_type=content_type,
    )

    return UploadUrlResponse(
        upload_url=upload_url,
        blob_url=blob_url,
        blob_name=blob_name,
        content_type=content_type,
        expires_in_seconds=settings.AZURE_SAS_EXPIRY_MINUTES * 60,
    )
