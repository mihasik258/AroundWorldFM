from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole


class IdentityRead(BaseModel):
    provider: str
    display_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserRead(BaseModel):
    id: int
    username: str
    email: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime
    auth_providers: list[str] = []
    identities: list[IdentityRead] = []

    model_config = ConfigDict(from_attributes=True)


class PasswordChange(BaseModel):
    old_password: str | None = Field(None, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class LinkUrlResponse(BaseModel):
    url: str
    expires_in: int


class AccountDelete(BaseModel):
    confirm_username: str = Field(..., min_length=1, max_length=64)
