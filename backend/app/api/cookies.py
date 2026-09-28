from datetime import datetime, timezone

from fastapi import Response

from app.core.config import settings

# Sent only to /api/v1/auth/*: the refresh token never travels with ordinary
# API calls or audio stream requests.
REFRESH_COOKIE_PATH = f"{settings.API_V1_STR}/auth"


def set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    max_age = max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=token,
        max_age=max_age,
        path=REFRESH_COOKIE_PATH,
        httponly=True,  # unreadable from JavaScript, so XSS cannot steal it
        secure=settings.COOKIE_SECURE,
        samesite="strict",  # never attached to requests initiated by other sites
    )


def clear_refresh_cookie(response: Response) -> None:
    # Browsers only delete a cookie when path and flags match the original
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
    )
