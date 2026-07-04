from enum import Enum

from pydantic import BaseModel, field_validator


class UploadType(str, Enum):
    post_image = "post_image"
    post_video = "post_video"
    post_audio = "post_audio"
    profile_image = "profile_image"
    thumbnail = "thumbnail"


ALLOWED_EXTENSIONS: dict[UploadType, list[str]] = {
    UploadType.post_image: ["jpg", "jpeg", "png", "webp"],
    UploadType.post_video: ["mp4", "mov", "webm"],
    UploadType.post_audio: ["mp3", "m4a", "wav", "aac"],
    UploadType.profile_image: ["jpg", "jpeg", "png", "webp"],
    UploadType.thumbnail: ["jpg", "jpeg", "png", "webp"],
}

CONTENT_TYPE_MAP: dict[str, str] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "webm": "video/webm",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "wav": "audio/wav",
    "aac": "audio/aac",
}


class UploadUrlRequest(BaseModel):
    filename: str
    upload_type: UploadType

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        if "." not in v:
            raise ValueError("filename must have extension")
        return v.lower()


class UploadUrlResponse(BaseModel):
    upload_url: str
    blob_url: str
    blob_name: str
    content_type: str
    expires_in_seconds: int
