from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    login: str = Field(..., min_length=1, max_length=255, description="Email или имя пользователя")
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Access token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: int
    username: str
    role: str


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(..., min_length=1, max_length=4096)


class TelegramProvider(BaseModel):
    enabled: bool
    bot_username: str | None = None


class ProvidersResponse(BaseModel):
    telegram: TelegramProvider
