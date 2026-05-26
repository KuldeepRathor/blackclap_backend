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
