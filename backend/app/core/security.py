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

_bcrypt_limiter = anyio.CapacityLimiter(max(1, (os.cpu_count() or 2) // 2))

_TIMING_DUMMY_HASH = "$2b$12$pX94XpfKEXnYH4E3JQi75OwYHfVzVIhU0Kpwa1IYSZUF1tIGeyovK"


def _apply_pepper(password: str) -> bytes:
    return hmac.new(
        key=settings.SECRET_PEPPER.encode("utf-8"),
        msg=password.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()


def hash_password(password: str) -> str:
    peppered = _apply_pepper(password)
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(peppered, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        peppered = _apply_pepper(plain_password)
        return bcrypt.checkpw(peppered, hashed_password.encode("utf-8"))
    except Exception:
        return False


async def hash_password_async(password: str) -> str:
    return await anyio.to_thread.run_sync(hash_password, password, limiter=_bcrypt_limiter)


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    return await anyio.to_thread.run_sync(
        verify_password, plain_password, hashed_password, limiter=_bcrypt_limiter
    )


async def verify_against_dummy(plain_password: str) -> None:
    await verify_password_async(plain_password, _TIMING_DUMMY_HASH)


def create_access_token(
    subject: str,
    role: str,
    session_id: int,
    expires_delta: timedelta | None = None,
) -> str:
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
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
