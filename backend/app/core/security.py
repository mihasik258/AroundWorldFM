import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

UTC = timezone.utc


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


def create_access_token(
    subject: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Generates a short-lived JWT access token."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),
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

