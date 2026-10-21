import subprocess
import sys
from pathlib import Path

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_password_hashing_with_individual_salt():
    pwd = "SecurePassword123!"
    hash1 = hash_password(pwd)
    hash2 = hash_password(pwd)

    assert hash1 != hash2
    assert verify_password(pwd, hash1) is True
    assert verify_password(pwd, hash2) is True
    assert verify_password("WrongPassword!", hash1) is False


def test_secret_pepper_influence(monkeypatch):
    pwd = "MySecretPassword123!"
    stored_hash = hash_password(pwd)

    monkeypatch.setattr(settings, "SECRET_PEPPER", "different-secret-pepper-12345")
    assert verify_password(pwd, stored_hash) is False


def test_jwt_access_and_refresh_tokens():
    access_tok = create_access_token(subject="42", role="admin", session_id=7)
    payload = decode_token(access_tok)

    assert payload["sub"] == "42"
    assert payload["sid"] == 7
    assert payload["role"] == "admin"
    assert payload["type"] == "access"

    refresh_tok, _jti = create_refresh_token(subject="42", jti="test-jti-uuid")
    refresh_payload = decode_token(refresh_tok)

    assert refresh_payload["sub"] == "42"
    assert refresh_payload["jti"] == "test-jti-uuid"
    assert refresh_payload["type"] == "refresh"


def test_async_hashing_without_web_app_imports():
    # CLI imports only app.core.security; anyio.to_thread must not rely on FastAPI loading it
    code = (
        "import asyncio\n"
        "from app.core.security import hash_password_async, verify_password_async\n"
        "h = asyncio.run(hash_password_async('CliPassword123!'))\n"
        "assert asyncio.run(verify_password_async('CliPassword123!', h))\n"
    )
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-c", code], cwd=BACKEND_DIR, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
