# Profile Flow - Frontend Integration Guide

This guide details the endpoints, request payloads, response models, and headers required for managing and retrieving user profiles in the BlackClap application.

---

## 🔒 Protected Endpoints Requirements

All profile modification and personal profile retrieval routes are protected. You must attach the Bearer token in the headers of these requests:
```http
Authorization: Bearer <your_access_token>
```

---

## 🚀 Endpoints

### 1. Get Logged-In User Profile
Retrieves the detailed profile information of the currently authenticated user. Call this to populate the profile home screen.

- **URL:** `/api/v1/users/me`
- **Method:** `GET`
- **Headers:** `Authorization: Bearer <token>`

#### Response (Success - 200 OK)
Returns full user profile details alongside current posting and social stats.

```json
{
  "id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
  "email": "cooldeep226@gmail.com",
  "username": "Kuldeep",
  "display_name": "Kuldeep",
  "avatar_url": null,
  "bio": "Mobile app developer building social monoliths.",
  "is_active": true,
  "created_at": "2026-05-27T00:15:40.852Z",
  "updated_at": "2026-05-27T00:15:40.852Z",
  "posts_count": 0,
  "followers_count": 0,
  "following_count": 0
}
```

---

### 2. Update Logged-In User Profile (Edit Profile)
Modifies the authenticated user's details. You can send any subset of the fields; fields not included in the payload will remain unchanged.

- **URL:** `/api/v1/users/me`
- **Method:** `PATCH`
- **Content-Type:** `application/json`
- **Headers:** `Authorization: Bearer <token>`

#### Request Payload
- `display_name` (string, max 100 chars, optional): Maps to the "Full name" input.
- `username` (string, 3-50 chars, only letters/numbers/underscores, optional): Maps to the "Username" input.
- `bio` (string, max 150 chars, optional): Maps to the "Bio" text field (strict 150 character limit).
- `email` (string, valid email, optional): Maps to the "Email" input.

```json
{
  "display_name": "Kuldeep Rathor",
  "username": "Kuldeep",
  "bio": "Enthusiastic developer based in Mumbai.",
  "email": "cooldeep226@gmail.com"
}
```

#### Response (Success - 200 OK)
Returns the updated user profile response with updated fields.

```json
{
  "id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
  "email": "cooldeep226@gmail.com",
  "username": "Kuldeep",
  "display_name": "Kuldeep Rathor",
  "avatar_url": null,
  "bio": "Enthusiastic developer based in Mumbai.",
  "is_active": true,
  "created_at": "2026-05-27T00:15:40.852Z",
  "updated_at": "2026-05-27T01:25:00.000Z",
  "posts_count": 0,
  "followers_count": 0,
  "following_count": 0
}
```

#### Response (Error - 400 Bad Request)
- Username is already taken by another user:
  ```json
  {
    "detail": "This username is already taken."
  }
  ```
- Email is already registered to another user:
  ```json
  {
    "detail": "This email is already in use by another account."
  }
  ```

#### Response (Error - 422 Unprocessable Entity)
- Bio exceeds the maximum limit of 150 characters:
  ```json
  {
    "detail": [
      {
        "type": "string_too_long",
        "loc": ["body", "bio"],
        "msg": "String should have at most 150 characters",
        "ctx": {"max_length": 150}
      }
    ]
  }
  ```

---

### 3. Get Public User Profile (User Lookups)
Retrieves the profile of another user by their unique handle. Used when navigating to another user's profile screen.

- **URL:** `/api/v1/users/{username}`
- **Method:** `GET`

*(Authentication token is not required to view public profiles, but if available, can be passed).*

#### Response (Success - 200 OK)
```json
{
  "id": "2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e",
  "email": "anotheruser@gmail.com",
  "username": "superstar",
  "display_name": "Super Star",
  "avatar_url": "https://example.com/avatar.png",
  "bio": "India first creator.",
  "is_active": true,
  "created_at": "2026-05-20T10:00:00.000Z",
  "updated_at": "2026-05-20T10:00:00.000Z",
  "posts_count": 14,
  "followers_count": 4200,
  "following_count": 89
}
```

#### Response (Error - 404 Not Found)
- Username does not exist in the database:
  ```json
  {
    "detail": "User not found"
  }
  ```

---

### 4. Upload Profile Image (2-Step Direct Upload Flow)
To update the user's profile image (photo), follow this direct upload flow (avoiding proxies through backend memory).

#### Step 1: Request an Upload Presigned URL
Call this route to retrieve an upload target ticket (AWS S3 URL or Local Emulator Endpoint).

- **URL:** `/api/v1/media/presigned-url`
- **Method:** `POST`
- **Content-Type:** `application/json`
- **Headers:** `Authorization: Bearer <token>`

##### Request Payload
- `file_name` (string): The filename of the chosen file (e.g. `me.jpg`).
- `file_type` (string): The MIME content-type of the file (e.g. `image/jpeg`).
- `purpose` (string): Must be `"avatar"` for profile photo changes.

```json
{
  "file_name": "me.jpg",
  "file_type": "image/jpeg",
  "purpose": "avatar"
}
```

##### Response (Success - 200 OK)
Returns target URLs for the upload:

```json
{
  "upload_url": "http://localhost:8000/api/v1/media/local-upload?file_key=avatars/1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d.jpg",
  "download_url": "http://localhost:8000/static/uploads/avatars/1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d.jpg",
  "file_key": "avatars/1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d.jpg",
  "is_local": true
}
```
*(In production, `upload_url` will point directly to a temporary secure Amazon S3 endpoint and `is_local` will be `false`).*

---

#### Step 2: Upload File Binary
Make an HTTP `PUT` request directly to the `upload_url` returned in Step 1.
- You must send the raw file binary data directly in the request body (do not send as form-data).
- Set the `Content-Type` header to match the MIME type specified in Step 1.

##### Example using Curl:
```bash
curl -X PUT \
  -H "Content-Type: image/jpeg" \
  --data-binary "@my_avatar.jpg" \
  "http://localhost:8000/api/v1/media/local-upload?file_key=avatars/1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d.jpg"
```

---

#### Step 3: Link the Image to the User Profile
Once the PUT upload completes successfully (HTTP status 200), update the user's profile with the new avatar link. Call the Edit Profile endpoint (`PATCH /api/v1/users/me`), setting `avatar_url` to the value of `download_url` returned in Step 1:

- **URL:** `/api/v1/users/me`
- **Method:** `PATCH`
- **Content-Type:** `application/json`
- **Headers:** `Authorization: Bearer <token>`

```json
{
  "avatar_url": "http://localhost:8000/static/uploads/avatars/1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d.jpg"
}
```
*(Once saved, all public profile queries will return this avatar URL).*
