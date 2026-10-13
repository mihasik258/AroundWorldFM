import json
from enum import StrEnum
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    PROJECT_NAME: str = "AroundFM API"
    VERSION: str = "2.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT

    PUBLIC_URL: str = "http://localhost:3000"

    SECRET_KEY: str
    SECRET_PEPPER: str

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(15, ge=1, le=60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(30, ge=1, le=90)
    ALGORITHM: str = "HS256"

    REFRESH_COOKIE_NAME: str = "refresh_token"
    COOKIE_SECURE: bool = True
    REFRESH_REUSE_GRACE_SECONDS: int = 30

    SESSION_CLEANUP_INTERVAL_SECONDS: int = 3600
    CATALOG_CACHE_TTL_SECONDS: int = 60
    NOW_PLAYING_CACHE_TTL_SECONDS: int = 20

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/aroundfm"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    RATE_LIMIT_LOGIN: str = "10/minute"
    RATE_LIMIT_REGISTER: str = "5/minute"
    RATE_LIMIT_LINK: str = "20/minute"

    STREAM_CHECK_ENABLED: bool = True
    STREAM_CHECK_TIMEOUT_SECONDS: float = 10.0
    STREAM_CHECK_INTERVAL_SECONDS: int = 300
    STREAM_CHECK_BATCH_SIZE: int = 200
    STREAM_RECHECK_ACTIVE_HOURS: int = 6
    STREAM_RECHECK_INACTIVE_HOURS: int = 24
    STREAM_CHECK_CONCURRENCY: int = 10
    ALLOW_PRIVATE_STREAM_HOSTS: bool = False

    SEED_DEMO_USERS: bool = False

    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_BOT_USERNAME: str | None = None
    TELEGRAM_AUTH_MAX_AGE_SECONDS: int = 3600
    BOT_API_SECRET: str | None = None

    TELEGRAM_LINK_TTL_SECONDS: int = 600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("SECRET_KEY", "SECRET_PEPPER")
    @classmethod
    def secret_long_enough(cls, v: str) -> str:
        if len(v.encode("utf-8")) < 32:
            raise ValueError("must be at least 32 bytes")
        return v

    @field_validator("BOT_API_SECRET")
    @classmethod
    def optional_secret_long_enough(cls, v: str | None) -> str | None:
        if v is not None and v != "" and len(v.encode("utf-8")) < 32:
            raise ValueError("must be at least 32 bytes")
        return v or None

    @field_validator("TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_USERNAME")
    @classmethod
    def empty_to_none(cls, v: str | None) -> str | None:
        return v or None

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                return list(json.loads(stripped))
            return [i.strip() for i in stripped.split(",") if i.strip()]
        return v

    @field_validator("PUBLIC_URL")
    @classmethod
    def public_url_is_origin(cls, v: str) -> str:
        parts = urlsplit(v)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("must be an absolute http(s) URL")
        return f"{parts.scheme}://{parts.netloc}"

    @model_validator(mode="after")
    def production_guards(self) -> "Settings":
        if self.ENVIRONMENT == Environment.PRODUCTION:
            if not self.PUBLIC_URL.startswith("https://"):
                raise ValueError("PUBLIC_URL must use https in production")
            if not self.COOKIE_SECURE:
                raise ValueError("COOKIE_SECURE must be enabled in production")
            if self.SEED_DEMO_USERS:
                raise ValueError("SEED_DEMO_USERS must be disabled in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == Environment.PRODUCTION

    @property
    def telegram_enabled(self) -> bool:
        return self.TELEGRAM_BOT_TOKEN is not None


settings = Settings()
