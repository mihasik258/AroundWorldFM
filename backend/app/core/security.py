import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import anyio
import bcrypt
import jwt

from app.core.config import settings

UTC = timezone.utc

# bcrypt takes ~350 ms of CPU and releases the GIL. Called directly inside an
# async handler it froze the whole event loop: ~3 failed logins per second
# stalled every other request. It now runs in worker threads, and the limiter
# caps how many cores a login flood can take, leaving the rest for the site.
_bcrypt_limiter = anyio.CapacityLimiter(max(1, (os.cpu_count() or 2) // 2))

# A cost-12 bcrypt hash of random bytes, matching nothing. Login checks
# against it when the account does not exist, so that case costs the same
# bcrypt time as a wrong password and response time does not reveal which
# usernames exist. Keep its cost equal to the rounds in hash_password().
_TIMING_DUMMY_HASH = "$2b$12$pX94XpfKEXnYH4E3JQi75OwYHfVzVIhU0Kpwa1IYSZUF1tIGeyovK"


def _apply_pepper(password: str) -> bytes:
    """Combines password with secret pepper using HMAC-SHA256.

    This ensures:
    1. Passwords are fortified with a server-side secret pepper that is never stored in DB.
    2. Overcomes bcrypt's 72-byte truncation limit cleanly.
    """
    return hmac.new(
        key=settings.SECRET_PEPPER.encode("utf-8"),
        msg=password.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()


def hash_password(password: str) -> str:
    """Hashes a password using secret pepper + individual bcrypt salt.

    Bcrypt automatically generates a unique 128-bit cryptographically secure salt per hash.
    """
    peppered = _apply_pepper(password)
    # gensalt generates a cryptographically random unique salt for each hash
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(peppered, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored bcrypt hash using secret pepper."""
    try:
        peppered = _apply_pepper(plain_password)
        return bcrypt.checkpw(peppered, hashed_password.encode("utf-8"))
    except Exception:
        return False


async def hash_password_async(password: str) -> str:
    """hash_password() off the event loop; use this from request handlers."""
    return await anyio.to_thread.run_sync(hash_password, password, limiter=_bcrypt_limiter)


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """verify_password() off the event loop; use this from request handlers."""
    return await anyio.to_thread.run_sync(
        verify_password, plain_password, hashed_password, limiter=_bcrypt_limiter
    )


async def verify_against_dummy(plain_password: str) -> None:
    """Spends one real bcrypt check on a hash that matches nothing."""
    await verify_password_async(plain_password, _TIMING_DUMMY_HASH)


def create_access_token(
    subject: str,
    role: str,
    session_id: int,
    expires_delta: timedelta | None = None,
) -> str:
    """Generates a short-lived JWT access token bound to a user session.

    The `sid` claim lets every request check that the session is still alive,
    so revoking a session takes effect immediately instead of after the token
    expires.
    """
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "sid": session_id,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    subject: str,
    jti: str | None = None,
    expires_delta: timedelta | None = None,
) -> tuple[str, str]:
    """Generates a long-lived JWT refresh token with unique jti for revocation tracking.

    Returns (token_string, jti).
    """
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    token_jti = jti or str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": str(subject),
        "jti": token_jti,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    encoded = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded, token_jti


def decode_token(token: str) -> dict[str, Any]:
    """Decodes and validates a JWT token signature and expiration."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

