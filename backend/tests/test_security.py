from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hashing_with_individual_salt():
    """Verify that hashing the same password twice results in different hashes due to unique salts."""
    pwd = "SecurePassword123!"
    hash1 = hash_password(pwd)
    hash2 = hash_password(pwd)

    assert hash1 != hash2, "Unique salts must generate different hashes"
    assert verify_password(pwd, hash1) is True
    assert verify_password(pwd, hash2) is True
    assert verify_password("WrongPassword!", hash1) is False


def test_secret_pepper_influence(monkeypatch):
    """Verify that verification fails if the secret pepper is changed/missing."""
    pwd = "MySecretPassword123!"
    stored_hash = hash_password(pwd)

    # Change secret pepper in settings
    monkeypatch.setattr(settings, "SECRET_PEPPER", "different-secret-pepper-12345")
    assert verify_password(pwd, stored_hash) is False, (
        "Password verification must fail with wrong pepper"
    )


def test_jwt_access_and_refresh_tokens():
    """Verify JWT access and refresh token generation and decoding."""
    access_tok = create_access_token(subject="42", role="admin")
    payload = decode_token(access_tok)

    assert payload["sub"] == "42"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"

    refresh_tok, jti = create_refresh_token(subject="42", jti="test-jti-uuid")
    refresh_payload = decode_token(refresh_tok)

    assert refresh_payload["sub"] == "42"
    assert refresh_payload["jti"] == "test-jti-uuid"
    assert refresh_payload["type"] == "refresh"
