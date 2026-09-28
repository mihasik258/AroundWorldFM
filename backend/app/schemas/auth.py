from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    login: str = Field(..., description="Email or Username")
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Only the short-lived access token goes into the body.

    The refresh token is delivered as an httpOnly cookie and never appears in
    JSON, so page scripts cannot read it.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: int
    username: str
    role: str
