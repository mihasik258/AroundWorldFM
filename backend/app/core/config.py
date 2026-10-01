import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AroundFM API"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str
    SECRET_PEPPER: str

    @field_validator("SECRET_KEY", "SECRET_PEPPER")
    @classmethod
    def secret_long_enough(cls, v: str) -> str:
        if len(v.encode("utf-8")) < 32:
            raise ValueError("must be at least 32 bytes")
        return v

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"

    REFRESH_COOKIE_NAME: str = "refresh_token"
    COOKIE_SECURE: bool = True
    REFRESH_REUSE_GRACE_SECONDS: int = 30

    SESSION_CLEANUP_INTERVAL_SECONDS: int = 3600

    CATALOG_CACHE_TTL_SECONDS: int = 60

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/aroundfm"

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

    RATE_LIMIT_LOGIN: str = "10/minute"
    RATE_LIMIT_REGISTER: str = "5/minute"

    STREAM_CHECK_TIMEOUT_SECONDS: float = 10.0
    STREAM_CHECK_INTERVAL_SECONDS: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
