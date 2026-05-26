from pydantic import BaseModel, Field


class PresignedUrlRequest(BaseModel):
    """Schema for validating media presigned URL requests."""

    file_name: str = Field(
        ..., description="Original name of the file (e.g. 'photo.jpg')"
    )
    file_type: str = Field(..., description="Mime type of the file (e.g. 'image/jpeg')")
    purpose: str = Field(
        ...,
        description="Purpose of the upload, e.g. 'avatar' (profile image) or 'post'",
    )


class PresignedUrlResponse(BaseModel):
    """Schema for returning generated direct-upload and download URLs."""

    upload_url: str = Field(
        ..., description="HTTP URL to which the client should PUT the file binary"
    )
    download_url: str = Field(
        ..., description="HTTP URL from which the file can be read/downloaded"
    )
    file_key: str = Field(
        ...,
        description="The unique key representing the file in S3 or local directory",
    )
    is_local: bool = Field(
        ...,
        description="Flag indicating if the upload is handled by the local dev server",
    )
