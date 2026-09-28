from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cookies import clear_refresh_cookie, set_refresh_cookie
from app.api.deps import AuthContext, get_auth_context, get_db
from app.core.config import settings
from app.core.rate_limit import limiter
from app.schemas.auth import TokenResponse, UserLogin, UserRegister
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
    summary="Вход: access-токен в ответе, refresh-токен в httpOnly cookie",
)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(
    request: Request,
    response: Response,
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db),
    user_agent: str | None = Header(None),
):
    """Аутентифицирует пользователя, создаёт сессию, выдаёт access-токен и ставит refresh-cookie."""
    ip_address = request.client.host if request.client else None
    issued = await AuthService.authenticate_user(
        db=db,
        login_data=login_data,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    set_refresh_cookie(response, issued.refresh_token, issued.refresh_expires_at)
    return issued.response


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Новый access-токен по refresh-cookie (с ротацией refresh-токена)",
)
async def refresh_token(
    response: Response,
    db: AsyncSession = Depends(get_db),
    # read from the httpOnly cookie, never from the body
    refresh_token: str | None = Cookie(None, alias=settings.REFRESH_COOKIE_NAME),
):
    """Выдаёт новый access-токен и заменяет refresh-cookie на новую (ротация).

    Повторное предъявление уже заменённого refresh-токена вне короткого окна
    считается кражей: сессия отзывается целиком.
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh-токен отсутствует, требуется вход",
        )
    issued = await AuthService.refresh_access_token(db, refresh_token)
    if issued.refresh_token:
        set_refresh_cookie(response, issued.refresh_token, issued.refresh_expires_at)
    return issued.response


@router.post(
    "/logout",
    summary="Выход с текущего устройства (отзыв сессии и удаление refresh-cookie)",
)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    # read from the httpOnly cookie, never from the body
    refresh_token: str | None = Cookie(None, alias=settings.REFRESH_COOKIE_NAME),
):
    """Отзывает сессию по refresh-cookie. Не требует access-токена, чтобы выход работал и после его истечения."""
    if refresh_token:
        await AuthService.logout(db, refresh_token)
    clear_refresh_cookie(response)
    return {"status": "ok", "message": "Вы вышли из аккаунта"}


@router.get(
    "/sessions",
    response_model=list[UserSessionRead],
    summary="Просмотр активных сеансов пользователя (текущий помечен is_current)",
)
async def get_sessions(
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """Возвращает список всех активных устройств/сессий пользователя."""
    sessions = await AuthService.get_user_sessions(db, ctx.user.id)
    result = []
    for s in sessions:
        item = UserSessionRead.model_validate(s)
        item.is_current = s.id == ctx.session.id
        result.append(item)
    return result


@router.delete(
    "/sessions/{session_id}",
    summary="Завершение конкретной пользовательской сессии (отзыв доступа)",
)
async def revoke_session(
    session_id: int,
    response: Response,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """Отзывает конкретную сессию по ее ID. Отзыв текущей сессии равносилен выходу."""
    success = await AuthService.revoke_session(db, ctx.user.id, session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сессия не найдена или уже отозвана",
        )
    if session_id == ctx.session.id:
        clear_refresh_cookie(response)
    return {"status": "ok", "message": "Сессия успешно отозвана"}


@router.post(
    "/sessions/revoke-all",
    summary="Выход на всех остальных устройствах (текущая сессия сохраняется)",
)
async def revoke_all_sessions(
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """Завершает все сеансы пользователя, кроме текущего."""
    count = await AuthService.revoke_all_sessions(
        db, ctx.user.id, except_session_id=ctx.session.id
    )
    return {"status": "ok", "message": f"Отозвано сессий на других устройствах: {count}"}
