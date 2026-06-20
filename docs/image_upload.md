# Image Upload — Architecture & Flow

BlackClap uses **Azure Blob Storage** for all media uploads via a 2-step direct-upload pattern.  
The client never proxies file bytes through the FastAPI server — it uploads directly to Azure.

---

## Why Direct Upload?

- FastAPI doesn't buffer large files in memory or disk.
- Azure Blob Storage handles bandwidth, CDN, and durability.
- Upload speed is limited only by the client's connection to Azure, not the API server.

---

## Upload Types

Defined in `app/modules/uploads/schemas.py`:

| `upload_type` value | Container | Allowed extensions |
|---|---|---|
| `profile_image` | `profile-images` | jpg, jpeg, png, webp |
| `post_image` | `post-media` | jpg, jpeg, png, webp |
| `post_video` | `post-media` | mp4, mov, webm |
| `post_audio` | `post-media` | mp3, m4a, wav, aac |
| `thumbnail` | `thumbnails` | jpg, jpeg, png, webp |

---

## Profile Image Upload — Step by Step

### Step 1 — Request a SAS Upload URL

**POST** `/api/v1/uploads/url`  
Requires: `Authorization: Bearer <token>`

**Request body:**
```json
{
  "filename": "photo.jpg",
  "upload_type": "profile_image"
}
```

**Response:**
```json
{
  "upload_url": "https://blackclapmedia.blob.core.windows.net/profile-images/profile_image/<user_id>/<uuid>.jpg?se=...&sp=cw&sig=...",
  "blob_url":   "https://blackclapmedia.blob.core.windows.net/profile-images/profile_image/<user_id>/<uuid>.jpg?se=...&sp=r&sig=...",
  "blob_name":  "profile_image/<user_id>/<uuid>.jpg",
  "content_type": "image/jpeg",
  "expires_in_seconds": 900
}
```

| Field | Description |
|---|---|
| `upload_url` | Short-lived write-SAS URL. PUT the raw bytes here. Expires in ~15 min. |
| `blob_url` | Long-lived read-SAS URL (5 years). Store this in the DB, use it in `<img>` / `CachedNetworkImage`. |
| `content_type` | MIME type derived from the file extension. Pass as `Content-Type` header on the PUT. |

> **Why two different SAS URLs?**  
> The storage account has public blob access **disabled** (Azure default since 2023).  
> Without a read SAS on the `blob_url`, fetching it returns **409 PublicAccessNotPermitted**.  
> The backend generates a short-lived write SAS for the upload and a long-lived read SAS for display.

---

### Step 2 — PUT File Bytes Directly to Azure

```
PUT <upload_url>
Content-Type: image/jpeg          ← must match what the backend returned
x-ms-blob-type: BlockBlob         ← required by Azure Blob Storage
Body: <raw file bytes>
```

Azure returns **201 Created** on success.

**curl example:**
```bash
curl -X PUT "<upload_url>" \
  -H "Content-Type: image/jpeg" \
  -H "x-ms-blob-type: BlockBlob" \
  --data-binary @photo.jpg
```

Do **not** send an `Authorization` header to Azure — the SAS token in the URL is the auth mechanism.

---

### Step 3 — Save the blob_url to the User Profile

**PATCH** `/api/v1/users/me`  
Requires: `Authorization: Bearer <token>`

```json
{
  "avatar_url": "<blob_url from Step 1>"
}
```

Response is the updated `UserProfileResponse`.

---

## Curl — Full Profile Image Upload Flow

```bash
# 1. Get SAS URL
UPLOAD_RESP=$(curl -s -X POST https://api.blackclap.com/api/v1/uploads/url \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filename":"photo.jpg","upload_type":"profile_image"}')

UPLOAD_URL=$(echo $UPLOAD_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['upload_url'])")
BLOB_URL=$(echo $UPLOAD_RESP    | python3 -c "import sys,json; print(json.load(sys.stdin)['blob_url'])")
CONTENT_TYPE=$(echo $UPLOAD_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['content_type'])")

# 2. Upload to Azure
curl -X PUT "$UPLOAD_URL" \
  -H "Content-Type: $CONTENT_TYPE" \
  -H "x-ms-blob-type: BlockBlob" \
  --data-binary @photo.jpg

# 3. Save blob_url to profile
curl -X PATCH https://api.blackclap.com/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"avatar_url\":\"$BLOB_URL\"}"
```

---

## Flutter Implementation

### Key files

| File | Role |
|---|---|
| `lib/config/app_url.dart` | `AppUrl.uploadUrl` → `/api/v1/uploads/url` |
| `lib/services/api_service.dart` | `uploadProfileImage(File)` — runs all 3 steps |
| `lib/repositories/user_repository.dart` | `uploadAvatar(String filePath)` — calls `ApiService` |
| `lib/views/screens/main/edit_profile_screen.dart` | Picks image, calls `uploadAvatar`, shows result |

### Flow in `api_service.dart`

```dart
Future<String> uploadProfileImage(File file) async {
  // Step 1 — get SAS URLs from backend
  final response = await _sendRequest('POST', Uri.parse(AppUrl.uploadUrl),
    requireAuth: true,
    body: json.encode({'filename': fileName, 'upload_type': 'profile_image'}),
  );
  final uploadUrl   = data['upload_url'];
  final blobUrl     = data['blob_url'];
  final contentType = data['content_type'];

  // Step 2 — PUT bytes directly to Azure (bypass _sendRequest to avoid JSON headers)
  await http.put(Uri.parse(uploadUrl),
    headers: {'Content-Type': contentType, 'x-ms-blob-type': 'BlockBlob'},
    body: await file.readAsBytes(),
  );

  // Step 3 — persist blob_url on user profile
  await updateMe({'avatar_url': blobUrl});
  return blobUrl;
}
```

---

## Backend Implementation

### `app/modules/uploads/router.py`

```
POST /api/v1/uploads/url
  → validates filename + upload_type
  → routes to correct Azure container
  → calls generate_sas_upload_url()
  → returns UploadUrlResponse
```

### `app/core/storage/azure.py`

`generate_sas_upload_url(container, blob_name, content_type)` generates:
- **Write SAS** (`sp=cw`) — short-lived (15 min default, `AZURE_SAS_EXPIRY_MINUTES`)
- **Read SAS** (`sp=r`) — long-lived (5 years, `_READ_SAS_EXPIRY_DAYS`)

---

## Required Environment Variables

```env
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...
AZURE_STORAGE_ACCOUNT_NAME=blackclapmedia
AZURE_POST_MEDIA_CONTAINER=post-media
AZURE_PROFILE_CONTAINER=profile-images
AZURE_THUMBNAIL_CONTAINER=thumbnails
AZURE_SAS_EXPIRY_MINUTES=15
```

---

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| `422 Unprocessable Entity` from `/uploads/url` | File extension not in allowed list | Use jpg/png/webp for images |
| `400` from `/uploads/url` | `filename` has no extension | Always send `"photo.jpg"` not `"photo"` |
| `403` from Azure PUT | SAS token expired | Re-request upload URL (15 min window) |
| `409` from Azure GET | No read SAS on blob_url | Backend must return read-SAS `blob_url` — see `azure.py` |
| `500` from backend | Azure connection string not configured | Set `AZURE_STORAGE_CONNECTION_STRING` env var |
