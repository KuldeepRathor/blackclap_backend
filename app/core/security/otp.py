"""Password-reset OTP helpers.

Reset state lives entirely in Redis (via the existing `cache` client) — no DB
table. We store a SHA-256 hash of the code (not the raw code) so a Redis dump
never exposes usable codes, alongside an attempt counter and a per-email send
counter for rate limiting.
"""
import hashlib
import secrets

from app.core.cache.redis_cache import cache
from app.core.config.settings import settings


def _norm(email: str) -> str:
    return email.strip().lower()


def _code_key(email: str) -> str:
    return f"pwreset:code:{_norm(email)}"


def _attempts_key(email: str) -> str:
    return f"pwreset:attempts:{_norm(email)}"


def _sends_key(email: str) -> str:
    return f"pwreset:sends:{_norm(email)}"


def generate_otp() -> str:
    """Return a random zero-padded 6-digit code."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


async def store_reset_code(email: str, code: str) -> None:
    """Persist the hashed code with a TTL and reset the attempt counter."""
    ttl = settings.PASSWORD_RESET_CODE_TTL_SECONDS
    await cache.setex(_code_key(email), ttl, hash_otp(code))
    await cache.delete(_attempts_key(email))


async def register_send(email: str) -> bool:
    """Increment the per-email send counter. Returns True if the send is allowed
    (i.e. within the rate limit), False if the limit is exceeded."""
    key = _sends_key(email)
    count = await cache.incr(key)
    if count == 1:
        await cache.expire(key, settings.PASSWORD_RESET_SEND_WINDOW_SECONDS)
    return count <= settings.PASSWORD_RESET_MAX_SENDS


async def verify_reset_code(email: str, code: str, *, consume: bool) -> bool:
    """Validate a submitted code against the stored hash.

    Increments the attempt counter on every failed attempt and invalidates the
    code once max attempts are exceeded. When `consume` is True, a successful
    match clears the code (single-use); when False (the pre-check on the code
    screen) the code is left in place for the final reset step.
    """
    stored = await cache.get(_code_key(email))
    if not stored:
        return False

    # Enforce max-attempts before checking, so a burned code can't be brute-forced.
    attempts = await cache.incr(_attempts_key(email))
    if attempts == 1:
        await cache.expire(
            _attempts_key(email), settings.PASSWORD_RESET_CODE_TTL_SECONDS
        )
    if attempts > settings.PASSWORD_RESET_MAX_ATTEMPTS:
        await _clear(email)
        return False

    if not secrets.compare_digest(stored, hash_otp(code)):
        return False

    if consume:
        await _clear(email)
    return True


async def _clear(email: str) -> None:
    await cache.delete(_code_key(email))
    await cache.delete(_attempts_key(email))
