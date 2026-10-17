from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    PUBLIC_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://backend:8000"
    BOT_API_SECRET: str | None = None
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    @field_validator("PUBLIC_URL", "BACKEND_URL")
    @classmethod
    def origin_only(cls, v: str) -> str:
        parts = urlsplit(v)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("must be an absolute http(s) URL")
        return f"{parts.scheme}://{parts.netloc}"

    @field_validator("TELEGRAM_BOT_TOKEN")
    @classmethod
    def token_present(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        return v

    @field_validator("BOT_API_SECRET")
    @classmethod
    def empty_to_none(cls, v: str | None) -> str | None:
        return v or None

    @property
    def mini_app_supported(self) -> bool:
        return self.PUBLIC_URL.startswith("https://")
