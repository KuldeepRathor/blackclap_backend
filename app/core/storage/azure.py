from datetime import datetime, timezone, timedelta
from typing import Tuple

from azure.storage.blob import (
    BlobServiceClient,
    BlobSasPermissions,
    generate_blob_sas,
)

from app.core.config.settings import settings

# How long a stored read URL stays valid. Profile images are long-lived so 5
# years is practical; regenerate by re-uploading if needed before expiry.
_READ_SAS_EXPIRY_DAYS = 365 * 5


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
    Returns (write_sas_url, read_sas_url).

    - write_sas_url: short-lived URL the client PUTs the file bytes to directly.
    - read_sas_url:  long-lived URL to store in the DB and use for display.

    A read SAS is required because the storage account has public access
    disabled (Azure default). Without it, fetching the raw blob URL returns 409.
    """
    if not settings.AZURE_STORAGE_ACCOUNT_NAME:
        raise RuntimeError("AZURE_STORAGE_ACCOUNT_NAME not configured")

    client = _get_client()
    account_key = client.credential.account_key
    now = datetime.now(timezone.utc)

    write_sas_token = generate_blob_sas(
        account_name=settings.AZURE_STORAGE_ACCOUNT_NAME,
        container_name=container,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(create=True, write=True),
        expiry=now + timedelta(minutes=expiry_minutes or settings.AZURE_SAS_EXPIRY_MINUTES),
        content_type=content_type,
    )

    read_sas_token = generate_blob_sas(
        account_name=settings.AZURE_STORAGE_ACCOUNT_NAME,
        container_name=container,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=now + timedelta(days=_READ_SAS_EXPIRY_DAYS),
    )

    base = (
        f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
        f"/{container}/{blob_name}"
    )
    upload_url = f"{base}?{write_sas_token}"
    blob_url = f"{base}?{read_sas_token}"

    return upload_url, blob_url
