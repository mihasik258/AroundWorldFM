from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserSessionRead(BaseModel):
    id: int
    ip_address: str | None
    device_name: str | None = None
    user_agent: str | None
    created_at: datetime
    last_used_at: datetime
    is_current: bool = False

    model_config = ConfigDict(from_attributes=True)
