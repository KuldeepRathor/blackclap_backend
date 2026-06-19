import os
import uuid
from typing import Any

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config.settings import settings
from app.core.security.auth import get_current_user
from app.modules.media.schemas import PresignedUrlRequest, PresignedUrlResponse
from app.modules.users.models import User

router = APIRouter(prefix="/media", tags=["Media"])


@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def get_presigned_url(
    request: Request,
    payload: PresignedUrlRequest,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Generate a direct-upload URL.
    If AWS S3 configuration is present, returns an S3 PUT presigned URL.
    Otherwise, returns a local emulator upload URL.
    """
    # 1. Determine the target S3/local file key based on purpose
    file_ext = os.path.splitext(payload.file_name)[1].lower()
    if not file_ext:
        # Fallback based on mime type
        if "jpeg" in payload.file_type or "jpg" in payload.file_type:
            file_ext = ".jpg"
        elif "png" in payload.file_type:
            file_ext = ".png"
        elif "mp4" in payload.file_type:
            file_ext = ".mp4"
        else:
            file_ext = ".bin"

    if payload.purpose == "avatar":
        # Avatars are stored as avatars/user_id.ext
        file_key = f"avatars/{current_user.id}{file_ext}"
    else:
        # Posts are stored as posts/user_id/random_uuid.ext
        file_key = f"posts/{current_user.id}/{uuid.uuid4()}{file_ext}"

    # 2. Check if S3 environment configurations are active
    aws_configured = all(
        [
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY,
            settings.S3_BUCKET_NAME,
        ]
    )

    if aws_configured:
        # AWS S3 Flow
        try:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
            )
            upload_url = s3_client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": settings.S3_BUCKET_NAME,
                    "Key": file_key,
                    "ContentType": payload.file_type,
                },
                ExpiresIn=3600,  # URL valid for 1 hour
            )
            # Build download URL (CloudFront or default S3 public endpoint)
            if settings.CLOUDFRONT_DOMAIN:
                download_url = f"https://{settings.CLOUDFRONT_DOMAIN}/{file_key}"
            else:
                download_url = (
                    f"https://{settings.S3_BUCKET_NAME}.s3.amazonaws.com/{file_key}"
                )

            return {
                "upload_url": upload_url,
                "download_url": download_url,
                "file_key": file_key,
                "is_local": False,
            }
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"S3 generation failed: {e}",
            )
    else:
        # Local Emulator Fallback Flow
        base_url_str = str(request.base_url)
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
    """
    Direct upload emulator for local testing.
    Accepts raw binary files in the request body.
    """
    # Clean the file key to prevent directory traversal attacks
    clean_key = os.path.normpath(file_key).lstrip("/")
    if clean_key.startswith("..") or ".." in clean_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file key path.",
        )

    # Compute static uploads destination directory
    current_dir = os.path.dirname(os.path.abspath(__file__))  # app/modules/media
    app_dir = os.path.dirname(os.path.dirname(current_dir))  # blackclap_backend/
    static_uploads_dir = os.path.join(app_dir, "static", "uploads")

    dest_path = os.path.abspath(os.path.join(static_uploads_dir, clean_key))

    # Verify target path is strictly within static_uploads_dir
    if not dest_path.startswith(os.path.abspath(static_uploads_dir)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid destination path.",
        )

    # Read the raw body data and write it to disk
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
