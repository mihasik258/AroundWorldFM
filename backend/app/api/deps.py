from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.session import UserSession
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


@dataclass
class AuthContext:
    user: User
    session: UserSession


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _resolve_access_token(db: AsyncSession, token: str | None) -> AuthContext:
    if not token:
        raise _unauthorized("Требуется аутентификация")

    try:
        payload = decode_token(token)
    except Exception:
        raise _unauthorized("Недействительный токен")

    if payload.get("type") != "access":
        raise _unauthorized("Неверный тип токена")

    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if not user_id or not isinstance(session_id, int):
        raise _unauthorized("Недействительный токен")

    session = await db.get(UserSession, session_id)
    if (
        not session
        or session.user_id != int(user_id)
        or session.is_revoked
        or session.expires_at < datetime.now(timezone.utc)
    ):
        raise _unauthorized("Сессия отозвана")

    user = await db.get(User, int(user_id))
    if not user:
        raise _unauthorized("Пользователь не найден")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Учетная запись отключена",
        )

    return AuthContext(user=user, session=session)


async def get_auth_context(
    db: AsyncSession = Depends(get_db),
    token: str | None = Depends(oauth2_scheme),
) -> AuthContext:
    return await _resolve_access_token(db, token)


async def get_current_user(ctx: AuthContext = Depends(get_auth_context)) -> User:
    return ctx.user


async def get_optional_current_user(
    db: AsyncSession = Depends(get_db),
    token: str | None = Depends(oauth2_scheme),
) -> User | None:
    if not token:
        return None
    try:
        return (await _resolve_access_token(db, token)).user
    except HTTPException:
        return None


def require_role(allowed_roles: list[UserRole]) -> Callable:
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав",
            )
        return current_user

    return role_checker
