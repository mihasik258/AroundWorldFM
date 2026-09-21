import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AroundFM API"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"

    # Security: Secret Key for JWT
    SECRET_KEY: str = "aroundfm-default-insecure-jwt-secret-key-change-in-prod"
    # Security: Secret Pepper for Password Hashing (stored in env, never in DB)
    SECRET_PEPPER: str = "aroundfm-secret-pepper-key-for-password-hashing"

    # JWT lifetime
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"

    # Database: PostgreSQL 16 (asyncpg)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/aroundfm"

    # CORS
    CORS_ORIGINS: list[str] | str = ["*"]

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
