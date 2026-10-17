from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cookies import clear_refresh_cookie
from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import hash_password_async, verify_password_async
from app.models.identity import AuthProvider, UserIdentity
from app.models.user import User, UserRole
from app.schemas.user import AccountDelete, LinkUrlResponse, PasswordChange, UserRead
from app.services import identity_service
from app.services.auth_service import AuthService
from app.services.telegram_service import TelegramService

router = APIRouter(prefix="/users", tags=["Пользователи"])


@router.get("/me", response_model=UserRead, summary="Профиль")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/me/change-password", summary="Смена или установка пароля")
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def change_password(
    request: Request,
    password_data: PasswordChange,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    identity = await identity_service.get_user_identity(db, current_user.id, AuthProvider.PASSWORD)
    new_hash = await hash_password_async(password_data.new_password)

    if identity is not None and identity.secret_hash:
        if not password_data.old_password or not await verify_password_async(
            password_data.old_password, identity.secret_hash
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный пароль")
        identity.secret_hash = new_hash
    else:
        current_user.identities.append(
            UserIdentity(
                provider=AuthProvider.PASSWORD,
                provider_uid=current_user.username,
                secret_hash=new_hash,
            )
        )

    await AuthService.revoke_all_sessions(db, current_user.id)
    await db.commit()
    clear_refresh_cookie(response)
    return {"status": "ok", "message": "Пароль сохранён"}


@router.post(
    "/me/identities/telegram/link",
    response_model=LinkUrlResponse,
    summary="Ссылка для привязки Telegram",
)
@limiter.limit(settings.RATE_LIMIT_LINK)
async def telegram_link(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    url, expires_in = await TelegramService.create_link_url(db, current_user)
    return LinkUrlResponse(url=url, expires_in=expires_in)


@router.delete("/me/identities/{provider}", summary="Отвязать способ входа")
async def unlink_provider(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await identity_service.unlink_identity(db, current_user, provider)
    return {"status": "ok", "message": "Отвязано"}


@router.delete("/me", summary="Удалить аккаунт")
async def delete_account(
    payload: AccountDelete,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.confirm_username != current_user.username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Имя не совпадает")
    if current_user.role == UserRole.ADMIN:
        admins = await db.scalar(
            select(func.count(User.id)).where(User.role == UserRole.ADMIN, User.is_active)
        )
        if (admins or 0) <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Нельзя удалить последнего администратора",
            )
    await db.delete(current_user)
    await db.commit()
    clear_refresh_cookie(response)
    return {"status": "ok", "message": "Аккаунт удалён"}
