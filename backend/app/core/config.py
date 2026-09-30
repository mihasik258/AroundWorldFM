import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AroundFM API"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"

    # Security: Secret Key for JWT — no default on purpose: the app must refuse to
    # start rather than silently sign tokens with a key visible in the public repo.
    SECRET_KEY: str
    # Security: Secret Pepper for Password Hashing (stored in env, never in DB)
    SECRET_PEPPER: str

    @field_validator("SECRET_KEY", "SECRET_PEPPER")
    @classmethod
    def secret_long_enough(cls, v: str) -> str:
        # RFC 7518 §3.2: an HMAC-SHA256 key must be at least as long as the hash
        # output. Applies to the pepper too — it is the HMAC key for passwords.
        if len(v.encode("utf-8")) < 32:
            raise ValueError("must be at least 32 bytes, generate with: openssl rand -hex 32")
        return v

    # JWT lifetime
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"

    # Refresh token lives in an httpOnly cookie scoped to the auth endpoints only,
    # so JavaScript (and therefore XSS) can never read it.
    REFRESH_COOKIE_NAME: str = "refresh_token"
    # Browsers accept Secure cookies on http://localhost; set to false only for
    # plain-HTTP access through a non-localhost host during development.
    COOKIE_SECURE: bool = True
    # A rotated refresh token is still accepted for this long, to absorb
    # legitimate races (two tabs refreshing at once). Reuse after that is
    # treated as theft and revokes the whole session.
    REFRESH_REUSE_GRACE_SECONDS: int = 30

    # Periodic purge of expired and revoked sessions
    SESSION_CLEANUP_INTERVAL_SECONDS: int = 3600

    # Public station catalogue responses are cached this long (and dropped
    # immediately on admin edits and after stream health checks)
    CATALOG_CACHE_TTL_SECONDS: int = 60

    # Database: PostgreSQL 16 (asyncpg)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/aroundfm"

    # CORS — no wildcard by default: "*" + allow_credentials=True is too permissive
    # for a JWT-authenticated API, override via env for other deployments.
    CORS_ORIGINS: list[str] | str = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # Rate Limiting
    RATE_LIMIT_LOGIN: str = "10/minute"
    RATE_LIMIT_REGISTER: str = "5/minute"

    # Stream health checker
    STREAM_CHECK_TIMEOUT_SECONDS: float = 10.0
    STREAM_CHECK_INTERVAL_SECONDS: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
