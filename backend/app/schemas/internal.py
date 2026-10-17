from pydantic import BaseModel, Field


class TelegramLinkRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=128)
    telegram_id: int = Field(..., gt=0)
    username: str | None = Field(None, max_length=64)
    first_name: str | None = Field(None, max_length=128)
    last_name: str | None = Field(None, max_length=128)


class TelegramLinkResult(BaseModel):
    username: str
