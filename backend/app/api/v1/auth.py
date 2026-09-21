from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.rate_limit import limiter
from app.models.user import User
from app.schemas.auth import RefreshTokenRequest, TokenResponse, UserLogin, UserRegister
from app.schemas.session import UserSessionRead
from app.schemas.user import UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Аутентификация и безопасность"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация пользователя (хэширование солью и секретным перцем)",
)
@limiter.limit(settings.RATE_LIMIT_REGISTER)
async def register(
    request: Request,
    register_data: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """Регистрирует нового пользователя с защитой от перебора (rate limiting) и солью + перцем."""
    user = await AuthService.register_user(db, register_data)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход пользователя (с защитой от брутфорса и отслеживанием сессии)",
)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(
    request: Request,
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db),
    user_agent: str | None = Header(None),
):
    """Аутентифицирует пользователя, выдает пару JWT (access + refresh) и сохраняет сессию."""
    ip_address = request.client.host if request.client else None
    return await AuthService.authenticate_user(
        db=db,
        login_data=login_data,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Обновление access токена по refresh токену (проверка отзыва сессии)",
)
async def refresh_token(
    request_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Проверяет валидность и статус отзыва сессии, выдает новый access-токен."""
    return await AuthService.refresh_access_token(db, request_data.refresh_token)


@router.get(
    "/sessions",
    response_model=list[UserSessionRead],
    summary="Просмотр активных сеансов пользователя (направление безопасности)",
)
async def get_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Возвращает список всех активных устройств/сессий пользователя."""
    return await AuthService.get_user_sessions(db, current_user.id)


@router.delete(
    "/sessions/{session_id}",
    summary="Завершение конкретной пользовательской сессии (отзыв доступа)",
)
async def revoke_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Отзывает конкретную сессию по ее ID."""
    success = await AuthService.revoke_session(db, current_user.id, session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сессия не найдена или уже отозвана",
        )
    return {"status": "ok", "message": "Сессия успешно отозвана"}


@router.post(
    "/sessions/revoke-all",
    summary="Выход на всех устройствах (отзыв всех активных сессий)",
)
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Завершает все сеансы текущего пользователя."""
    count = await AuthService.revoke_all_sessions(db, current_user.id)
    return {"status": "ok", "message": f"Отозвано сессий: {count}"}


class TelegramAuthRequest(BaseModel):
    init_data: str


@router.post(
    "/telegram",
    response_model=TokenResponse,
    summary="Бесшовный вход через Telegram Mini App (SSO)",
)
async def telegram_auth(
    request: Request,
    data: TelegramAuthRequest,
    db: AsyncSession = Depends(get_db),
    user_agent: str | None = Header(None),
):
    """Аутентифицирует пользователя внутри Telegram WebApp по криптографической подписи initData."""
    ip_address = request.client.host if request.client else None
    return await AuthService.authenticate_telegram(
        db=db,
        init_data=data.init_data,
        ip_address=ip_address,
        user_agent=user_agent,
    )
