from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings
from app.core.database.session import get_db
from app.core.email.sender import email_sender
from app.core.email.templates import password_reset_email
from app.core.security.auth import get_current_user
from app.core.security.otp import (
    generate_otp,
    register_send,
    store_reset_code,
    verify_reset_code,
)
from app.core.security.password import hash_password, verify_password
from app.modules.account.service import is_within_grace_period, reactivate_account
from app.modules.auth.schemas import (
    AuthResponse,
    ForgotPasswordRequest,
    MessageResponse,
    RefreshRequest,
    ResetPasswordRequest,
    Token,
    TokenPair,
    UserLogin,
    UserRegister,
    UserResponse,
    VerifyResetCodeRequest,
)
from app.modules.auth.service import (
    issue_token_pair,
    revoke_all_user_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.modules.users.models import User


def _client_info(request: Request) -> tuple[Optional[str], Optional[str]]:
    """(user_agent, ip_address) — best-effort, both may be None."""
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    return user_agent, ip_address


# Generic response so we never reveal whether an email is registered.
_GENERIC_RESET_MESSAGE = (
    "If an account exists for that email, a password reset code has been sent."
)


async def _send_reset_email(email: str, code: str) -> None:
    """Background task: build and dispatch the OTP email. Never raises."""
    ttl_minutes = max(1, settings.PASSWORD_RESET_CODE_TTL_SECONDS // 60)
    subject, text, html = password_reset_email(code, ttl_minutes)
    await email_sender.send(to=email, subject=subject, text=text, html=html)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_in: UserRegister, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Register a new user in the system.
    Validates username/email uniqueness, hashes the password, and creates the record.
    Returns the user profile along with access and refresh tokens.
    """
    # Check if user with same email or username already exists
    stmt = select(User).where(
        or_(User.email == user_in.email, User.username == user_in.username)
    )
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        if existing_user.email == user_in.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this username already exists.",
            )

    # Hash the password and create the user object
    hashed = hash_password(user_in.password)
    user = User(
        email=user_in.email,
        username=user_in.username,
        hashed_password=hashed,
        display_name=user_in.username,  # default display name is username
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Automatically generate access & refresh tokens on signup
    user_agent, ip_address = _client_info(request)
    pair = await issue_token_pair(db, user, user_agent, ip_address)

    return {**pair, "user": user}


@router.post("/login", response_model=AuthResponse)
async def login(
    user_in: UserLogin, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Login using email or username and password, returning an access and refresh token.
    Accepts JSON body.
    """
    # Find user by username or email
    stmt = select(User).where(
        or_(
            User.username == user_in.email_or_username,
            User.email == user_in.email_or_username,
        )
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username/email or password",
        )

    if not user.is_active:
        # A soft-deleted account can be recovered by logging in within the grace
        # period; otherwise it stays locked (pending permanent deletion).
        if is_within_grace_period(user):
            await reactivate_account(db, user)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is inactive",
            )

    # Generate JWT tokens
    user_agent, ip_address = _client_info(request)
    pair = await issue_token_pair(db, user, user_agent, ip_address)

    return {**pair, "user": user}


@router.post("/token", response_model=Token)
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    OAuth2 compatible token login, returning an access token and a refresh token.
    Allows authentication using either Username or Email in the username field.
    """
    # Find user by username or email
    stmt = select(User).where(
        or_(
            User.username == form_data.username,
            User.email == form_data.username,
        )
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username/email or password",
        )

    if not user.is_active:
        # Reactivate a soft-deleted account on login within the grace period.
        if is_within_grace_period(user):
            await reactivate_account(db, user)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is inactive",
            )

    # Generate JWT tokens
    user_agent, ip_address = _client_info(request)
    return await issue_token_pair(db, user, user_agent, ip_address)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> Any:
    """Get profile information of the currently authenticated user."""
    return current_user


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Start the password-reset flow: if the email belongs to an account, generate
    a 6-digit code, store its hash in Redis (10-min TTL), and email it.

    Always returns the same generic message regardless of whether the email
    exists, to prevent user-enumeration.
    """
    stmt = select(User).where(User.email == payload.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # Only send if the account exists and is active; otherwise silently no-op.
    if user and user.is_active:
        # Rate-limit sends per email; if exceeded, silently skip sending.
        if await register_send(payload.email):
            code = generate_otp()
            await store_reset_code(payload.email, code)
            background_tasks.add_task(_send_reset_email, payload.email, code)

    return {"message": _GENERIC_RESET_MESSAGE}


@router.post("/verify-reset-code", response_model=MessageResponse)
async def verify_reset_code_endpoint(payload: VerifyResetCodeRequest) -> Any:
    """
    Validate a reset code without consuming it, so the app can gate the
    new-password screen. Returns 400 if the code is invalid or expired.
    """
    valid = await verify_reset_code(payload.email, payload.code, consume=False)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code.",
        )
    return {"message": "Code verified."}


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Consume the reset code and set a new password. Re-validates the code
    (single-use), updates the user's hashed password, and clears the code.
    """
    valid = await verify_reset_code(payload.email, payload.code, consume=True)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code.",
        )

    stmt = select(User).where(User.email == payload.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        # Code was valid but the account vanished — treat as a bad request.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code.",
        )

    user.hashed_password = hash_password(payload.new_password)
    await db.commit()

    return {"message": "Your password has been reset. You can now log in."}


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Exchange a refresh token for a new access/refresh pair. The presented
    refresh token is rotated (revoked and replaced) — reusing it again is
    treated as theft and revokes its entire token family.
    """
    user_agent, ip_address = _client_info(request)
    return await rotate_refresh_token(db, payload.refresh_token, user_agent, ip_address)


@router.post("/logout", response_model=MessageResponse)
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Revoke a single refresh token. Always returns success — logout is
    idempotent and never reveals whether the token was still valid.
    """
    await revoke_refresh_token(db, payload.refresh_token)
    return {"message": "Logged out."}


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Revoke every refresh token for the current user (all devices)."""
    await revoke_all_user_tokens(db, current_user.id)
    return {"message": "Logged out of all devices."}
