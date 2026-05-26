# Auth Flow - Frontend Integration Guide

This guide details the endpoints, request payloads, response models, and headers required for authentication in the BlackClap application.

---

## 🔑 Authentication Mechanism

BlackClap uses JSON Web Tokens (JWT) for authentication.
- Upon successful registration or login, the API returns an `access_token` and a `refresh_token`.
- You must save both tokens securely on the client side (e.g., in secure storage).
- For all protected endpoints, append the access token as a header:
  `Authorization: Bearer <your_access_token>`

---

## 🚀 Endpoints

### 1. User Registration (Sign Up)
Registers a new user in the system and automatically logs them in by returning tokens.

- **URL:** `/api/v1/auth/register`
- **Method:** `POST`
- **Content-Type:** `application/json`

#### Request Payload
- `email` (string, valid email): User's registration email.
- `username` (string, 3-50 chars, only letters, numbers, and underscores): Chosen unique handle.
- `password` (string, 6-100 chars): Account password.

```json
{
  "email": "cooldeep226@gmail.com",
  "username": "Kuldeep",
  "password": "strongpassword123"
}
```

#### Response (Success - 201 Created)
Returns tokens along with the user details.

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
    "email": "cooldeep226@gmail.com",
    "username": "Kuldeep",
    "display_name": "Kuldeep",
    "avatar_url": null,
    "bio": null,
    "is_active": true,
    "created_at": "2026-05-27T00:15:40.852Z",
    "updated_at": "2026-05-27T00:15:40.852Z"
  }
}
```

#### Response (Error - 400 Bad Request)
- Username already taken:
  ```json
  {
    "detail": "A user with this username already exists."
  }
  ```
- Email already registered:
  ```json
  {
    "detail": "A user with this email already exists."
  }
  ```

---

### 2. User Login (Sign In via JSON)
Authenticates a user via JSON payload.

- **URL:** `/api/v1/auth/login`
- **Method:** `POST`
- **Content-Type:** `application/json`

#### Request Payload
- `email_or_username` (string): The user's registered username OR email address.
- `password` (string): The account password.

```json
{
  "email_or_username": "cooldeep226@gmail.com",
  "password": "strongpassword123"
}
```

#### Response (Success - 200 OK)
Returns tokens along with the user details.

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
    "email": "cooldeep226@gmail.com",
    "username": "Kuldeep",
    "display_name": "Kuldeep",
    "avatar_url": null,
    "bio": null,
    "is_active": true,
    "created_at": "2026-05-27T00:15:40.852Z",
    "updated_at": "2026-05-27T00:15:40.852Z"
  }
}
```

#### Response (Error - 400 Bad Request)
- Wrong credentials:
  ```json
  {
    "detail": "Incorrect username/email or password"
  }
  ```

---

### 3. OAuth2 Token Exchange (Sign In via Form-Data)
Authenticates a user via Form-Data parameters (used by Swagger UI / Standard OAuth2 tools).

- **URL:** `/api/v1/auth/token`
- **Method:** `POST`
- **Content-Type:** `application/x-www-form-urlencoded`

#### Request Parameters
- `username` (string): Username or email.
- `password` (string): Password.

#### Response (Success - 200 OK)
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```
