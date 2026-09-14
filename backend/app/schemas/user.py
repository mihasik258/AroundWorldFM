from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole


class UserRead(BaseModel):
    id: int
    username: str
    email: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime
    auth_providers: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
