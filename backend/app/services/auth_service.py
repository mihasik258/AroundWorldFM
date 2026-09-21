import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_telegram_init_data,
)
from app.models.identity import UserIdentity
from app.models.session import UserSession
from app.models.user import User, UserRole
from app.schemas.auth import TokenResponse, UserLogin, UserRegister

UTC = timezone.utc


def hash_token(token: str) -> str:
    """Computes SHA-256 hash of a token for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def detect_device_name(user_agent: str | None) -> str:
    """Infers friendly device name from user-agent string."""
    if not user_agent:
        return "Unknown Device"
    ua = user_agent.lower()
    if "telegram" in ua:
        return "Telegram Mini App"
    if "iphone" in ua or "ipad" in ua:
        return "Apple iOS Device"
    if "android" in ua:
        return "Android Device"
    if "macintosh" in ua or "mac os" in ua:
        return "macOS Browser"
    if "windows" in ua:
        return "Windows PC"
    if "linux" in ua:
        return "Linux PC"
    return "Web Browser"


class AuthService:
    @staticmethod
    async def register_user(db: AsyncSession, register_data: UserRegister) -> User:
        """Registers a new user with salt + pepper password hashing and UserIdentity."""
        # Check if email or username already exists
        stmt = select(User).where(
            (User.email == register_data.email) | (User.username == register_data.username)
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            if existing.email == register_data.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Пользователь с таким email уже зарегистрирован",
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Имя пользователя уже занято",
            )

        hashed = hash_password(register_data.password)
        new_user = User(
            email=register_data.email,
            username=register_data.username,
            role=UserRole.USER,
            is_active=True,
        )
        db.add(new_user)
        await db.flush()

        identity = UserIdentity(
            user_id=new_user.id,
            provider="password",
            provider_uid=new_user.username,
            secret_hash=hashed,
        )
        db.add(identity)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        login_data: UserLogin,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """Authenticates user via password identity, creates a tracked session, and returns JWT tokens."""
        # Find user by username or email
        stmt = (
            select(User)
            .options(selectinload(User.identities))
            .where((User.username == login_data.login) | (User.email == login_data.login))
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный логин или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Look up password identity
        pwd_identity = next(
            (i for i in user.identities if i.provider == "password"),
            None,
        )
        if not pwd_identity or not pwd_identity.secret_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Для данной учетной записи пароль не задан. Используйте внешний вход.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not verify_password(login_data.password, pwd_identity.secret_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный логин или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Учетная запись деактивирована",
            )

        # Generate tokens
        access_token = create_access_token(subject=str(user.id), role=user.role.value)
        refresh_token, _ = create_refresh_token(subject=str(user.id))
        token_hash = hash_token(refresh_token)

        # Create tracked session with token hash
        expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        session = UserSession(
            user_id=user.id,
            refresh_token_hash=token_hash,
            device_name=detect_device_name(user_agent),
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
            is_revoked=False,
        )
        db.add(session)
        await db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=user.id,
            username=user.username,
            role=user.role.value,
        )

    @staticmethod
    async def refresh_access_token(
        db: AsyncSession,
        refresh_token: str,
    ) -> TokenResponse:
        """Validates refresh token hash against user sessions and issues new access token."""
        try:
            payload = decode_token(refresh_token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный или истекший refresh токен",
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Токен не является refresh токеном",
            )

        user_id = int(payload["sub"])
        token_hash = hash_token(refresh_token)

        # Check session status in database via token hash
        stmt = select(UserSession).where(
            UserSession.refresh_token_hash == token_hash,
            UserSession.user_id == user_id,
            UserSession.is_revoked == False,
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session or session.expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Сессия была отозвана или истекла",
            )

        # Check user
        user = await db.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден или заблокирован",
            )

        # Update session activity
        session.last_used_at = datetime.now(UTC)
        await db.commit()

        # Issue fresh access token
        new_access_token = create_access_token(subject=str(user.id), role=user.role.value)

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=user.id,
            username=user.username,
            role=user.role.value,
        )

    @staticmethod
    async def revoke_session(db: AsyncSession, user_id: int, session_id: int) -> bool:
        """Revokes a single user session by ID."""
        stmt = select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        if not session:
            return False

        session.is_revoked = True
        await db.commit()
        return True

    @staticmethod
    async def revoke_all_sessions(db: AsyncSession, user_id: int) -> int:
        """Revokes all sessions for a user (logout from all devices)."""
        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.is_revoked == False)
            .values(is_revoked=True)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount

    @staticmethod
    async def get_user_sessions(db: AsyncSession, user_id: int) -> list[UserSession]:
        """Returns all non-revoked sessions of a user."""
        stmt = (
            select(UserSession)
            .where(UserSession.user_id == user_id, UserSession.is_revoked == False)
            .order_by(UserSession.last_used_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def authenticate_telegram(
        cls,
        db: AsyncSession,
        init_data: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """Authenticates user via Telegram WebApp initData with UserIdentity."""
        bot_token = settings.TELEGRAM_BOT_TOKEN
        tg_user = None
        if bot_token:
            tg_user = verify_telegram_init_data(init_data, bot_token)
        else:
            try:
                import json
                from urllib.parse import parse_qsl
                p = dict(parse_qsl(init_data, keep_blank_values=True))
                if "user" in p:
                    tg_user = json.loads(p["user"])
            except Exception:
                pass

        if not tg_user or "id" not in tg_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительные данные авторизации Telegram",
            )

        telegram_id = int(tg_user["id"])
        username = tg_user.get("username") or f"tg_{telegram_id}"
        email = f"tg_{telegram_id}@telegram.aroundfm.internal"

        # Check if telegram identity exists
        stmt = select(UserIdentity).where(
            UserIdentity.provider == "telegram",
            UserIdentity.provider_uid == str(telegram_id),
        )
        result = await db.execute(stmt)
        identity = result.scalar_one_or_none()

        if identity:
            user = await db.get(User, identity.user_id)
        else:
            # Check if user with this username exists
            u_stmt = select(User).where(User.username == username)
            u_res = await db.execute(u_stmt)
            user = u_res.scalar_one_or_none()

            if not user:
                user = User(
                    username=username,
                    email=email,
                    role=UserRole.USER,
                    is_active=True,
                )
                db.add(user)
                await db.flush()

            identity = UserIdentity(
                user_id=user.id,
                provider="telegram",
                provider_uid=str(telegram_id),
            )
            db.add(identity)
            await db.commit()
            await db.refresh(user)

        # Generate tokens and track session
        access_token = create_access_token(subject=str(user.id), role=user.role.value)
        refresh_token, _ = create_refresh_token(subject=str(user.id))
        token_hash = hash_token(refresh_token)

        expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        session = UserSession(
            user_id=user.id,
            refresh_token_hash=token_hash,
            device_name="Telegram Mini App",
            ip_address=ip_address,
            user_agent=user_agent or "Telegram-Mini-App",
            expires_at=expires_at,
        )
        db.add(session)
        await db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=user.id,
            username=user.username,
            role=user.role.value,
        )
