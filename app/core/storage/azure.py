from datetime import datetime, timezone, timedelta
from typing import Tuple

from azure.storage.blob import (
    BlobServiceClient,
    BlobSasPermissions,
    generate_blob_sas,
)

from app.core.config.settings import settings


def _get_client() -> BlobServiceClient:
    if not settings.AZURE_STORAGE_CONNECTION_STRING:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING not configured")
    return BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)


def generate_sas_upload_url(
    container: str,
    blob_name: str,
    content_type: str,
    expiry_minutes: int | None = None,
) -> Tuple[str, str]:
    """
    Returns (sas_upload_url, permanent_blob_url).
    Flutter PUTs bytes directly to sas_upload_url; store blob_url in DB.
    """
    if not settings.AZURE_STORAGE_ACCOUNT_NAME:
        raise RuntimeError("AZURE_STORAGE_ACCOUNT_NAME not configured")

    client = _get_client()
    account_key = client.credential.account_key
    expiry = timedelta(minutes=expiry_minutes or settings.AZURE_SAS_EXPIRY_MINUTES)

    sas_token = generate_blob_sas(
        account_name=settings.AZURE_STORAGE_ACCOUNT_NAME,
        container_name=container,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(create=True, write=True),
        expiry=datetime.now(timezone.utc) + expiry,
        content_type=content_type,
    )

    upload_url = (
        f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
        f"/{container}/{blob_name}?{sas_token}"
    )
    blob_url = (
        f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
        f"/{container}/{blob_name}"
    )
    return upload_url, blob_url
