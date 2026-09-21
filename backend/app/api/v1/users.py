from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.security import hash_password, verify_password
from app.models.identity import UserIdentity
from app.models.user import User
from app.schemas.user import PasswordChange, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["Пользователи"])


@router.get("/me", response_model=UserRead, summary="Получить профиль текущего пользователя")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/me/change-password", summary="Смена пароля с проверкой старого пароля")
async def change_password(
    password_data: PasswordChange,
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
            detail="У данной учетной записи не установлен пароль",
        )

    if not verify_password(password_data.old_password, identity.secret_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Текущий пароль указан неверно",
        )

    identity.secret_hash = hash_password(password_data.new_password)
    # Revoke other sessions after password change for security
    await AuthService.revoke_all_sessions(db, current_user.id)
    await db.commit()

    return {"status": "ok", "message": "Пароль успешно изменен. Все активные сессии завершены."}
