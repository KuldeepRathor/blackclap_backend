# Image Upload

Azure Blob Storage — 2-step direct upload. Files never pass through the API server.

## Flow

```
Flutter → POST /api/v1/uploads/url   → get write SAS + read SAS
Flutter → PUT <write_sas_url>        → upload bytes directly to Azure
Flutter → PATCH /api/v1/users/me     → save read_sas blob_url to profile
```

---

## Step 1 — Get SAS URL

```bash
curl -X POST https://api.blackclap.com/api/v1/uploads/url \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filename":"photo.jpg","upload_type":"profile_image"}'
```

Response:

```json
{
  "upload_url": "https://blackclapmedia.blob.core.windows.net/...?sp=cw&sig=...",
  "blob_url":   "https://blackclapmedia.blob.core.windows.net/...?sp=r&sig=...",
  "blob_name":  "profile_image/<user_id>/<uuid>.jpg",
  "content_type": "image/jpeg",
  "expires_in_seconds": 900
}
```

`upload_url` → write-only, 15 min expiry — PUT your file here  
`blob_url` → read-only, 5 year expiry — store this in DB / display in app

---

## Step 2 — Upload to Azure

```bash
curl -X PUT "$UPLOAD_URL" \
  -H "Content-Type: image/jpeg" \
  -H "x-ms-blob-type: BlockBlob" \
  --data-binary @photo.jpg
```

`x-ms-blob-type: BlockBlob` is required by Azure. No `Authorization` header needed — SAS token is in the URL.

Azure returns `201 Created` on success.

---

## Step 3 — Save to Profile

```bash
curl -X PATCH https://api.blackclap.com/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"avatar_url\":\"$BLOB_URL\"}"
```

---

## Upload Types

| `upload_type` | Container | Allowed extensions |
|---|---|---|
| `profile_image` | `profile-images` | jpg, jpeg, png, webp |
| `post_image` | `post-media` | jpg, jpeg, png, webp |
| `post_video` | `post-media` | mp4, mov, webm |
| `post_audio` | `post-media` | mp3, m4a, wav, aac |
| `thumbnail` | `thumbnails` | jpg, jpeg, png, webp |

---

## Common Errors

| Error | Cause |
|---|---|
| `422` from `/uploads/url` | Extension not in allowed list |
| `403` from Azure PUT | SAS token expired (re-request URL) |
| `409` from Azure GET | `blob_url` has no read SAS — backend must return read-SAS URL |
| `500` from backend | `AZURE_STORAGE_CONNECTION_STRING` not set |

---

## Required Env Vars

```env
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...
AZURE_STORAGE_ACCOUNT_NAME=blackclapmedia
AZURE_SAS_EXPIRY_MINUTES=15
```
