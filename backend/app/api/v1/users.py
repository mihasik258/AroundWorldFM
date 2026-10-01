from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cookies import clear_refresh_cookie
from app.api.deps import get_current_user, get_db
from app.core.security import hash_password_async, verify_password_async
from app.models.identity import UserIdentity
from app.models.user import User
from app.schemas.user import PasswordChange, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["Пользователи"])


@router.get("/me", response_model=UserRead, summary="Профиль")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/me/change-password", summary="Смена пароля")
async def change_password(
    password_data: PasswordChange,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(UserIdentity).where(
        UserIdentity.user_id == current_user.id,
        UserIdentity.provider == "password",
    )
    identity = (await db.execute(stmt)).scalar_one_or_none()
    if not identity or not identity.secret_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пароль не установлен",
        )

    if not await verify_password_async(password_data.old_password, identity.secret_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный пароль",
        )

    identity.secret_hash = await hash_password_async(password_data.new_password)
    await AuthService.revoke_all_sessions(db, current_user.id)
    await db.commit()
    clear_refresh_cookie(response)

    return {"status": "ok", "message": "Пароль изменён"}
