import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password_async,
    verify_against_dummy,
    verify_password_async,
)
from app.models.identity import UserIdentity
from app.models.session import UserSession
from app.models.user import User, UserRole
from app.schemas.auth import TokenResponse, UserLogin, UserRegister

UTC = timezone.utc
logger = logging.getLogger(__name__)


def hash_token(token: str) -> str:
    """Computes SHA-256 hash of a token for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def detect_device_name(user_agent: str | None) -> str:
    """Infers friendly device name from user-agent string."""
    if not user_agent:
        return "Unknown Device"
    ua = user_agent.lower()
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


@dataclass
class IssuedTokens:
    """Result of login/refresh.

    `refresh_token` is None when no new cookie must be set (a concurrent
    refresh inside the grace window: the browser already got the new cookie
    from the request that won the race).
    """

    response: TokenResponse
    refresh_token: str | None
    refresh_expires_at: datetime


def _token_response(user: User, session: UserSession) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(
            subject=str(user.id), role=user.role.value, session_id=session.id
        ),
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        username=user.username,
        role=user.role.value,
    )


def _new_refresh_token(user_id: int, expires_at: datetime) -> str:
    # The refresh JWT never outlives its session: rotation keeps the absolute
    # 30-day lifetime from login instead of sliding it forward forever.
    token, _ = create_refresh_token(
        subject=str(user_id), expires_delta=expires_at - datetime.now(UTC)
    )
    return token


_SESSION_GONE = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Сессия была отозвана или истекла",
)


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

        hashed = await hash_password_async(register_data.password)
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
    ) -> IssuedTokens:
        """Authenticates user via password identity, creates a tracked session, issues tokens."""
        # Find user by username or email
        stmt = (
            select(User)
            .options(selectinload(User.identities))
            .where((User.username == login_data.login) | (User.email == login_data.login))
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        pwd_identity = (
            next((i for i in user.identities if i.provider == "password"), None) if user else None
        )

        # Every failure path costs one bcrypt check and returns the same message:
        # an unknown login, an account without a password and a wrong password
        # must be indistinguishable by both response text and response time.
        if not pwd_identity or not pwd_identity.secret_hash:
            await verify_against_dummy(login_data.password)
            password_ok = False
        else:
            password_ok = await verify_password_async(login_data.password, pwd_identity.secret_hash)

        if not password_ok:
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

        # The session row is created first: the access token carries its id (sid)
        expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_token = _new_refresh_token(user.id, expires_at)
        session = UserSession(
            user_id=user.id,
            refresh_token_hash=hash_token(refresh_token),
            device_name=detect_device_name(user_agent),
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
            is_revoked=False,
        )
        db.add(session)
        await db.flush()
        response = _token_response(user, session)
        await db.commit()

        return IssuedTokens(response, refresh_token, expires_at)

    @staticmethod
    async def refresh_access_token(db: AsyncSession, refresh_token: str) -> IssuedTokens:
        """Rotates the refresh token and issues a new access token.

        - current token  -> rotate: new refresh token, the old one is remembered
        - just-rotated token, inside the grace window -> concurrent refresh
          (two tabs): new access token, no rotation, no new cookie
        - just-rotated token, after the grace window -> the token was copied:
          revoke the whole session so both the thief and the victim are cut off
        """
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
        now = datetime.now(UTC)

        # Row lock serialises concurrent refreshes of the same session: the loser
        # of a race sees the already-rotated hash and takes the grace branch
        # instead of overwriting the winner's token.
        stmt = (
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                or_(
                    UserSession.refresh_token_hash == token_hash,
                    UserSession.previous_token_hash == token_hash,
                ),
            )
            .with_for_update()
        )
        session = (await db.execute(stmt)).scalar_one_or_none()

        if not session or session.is_revoked or session.expires_at < now:
            raise _SESSION_GONE

        user = await db.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден или заблокирован",
            )

        if session.refresh_token_hash != token_hash:
            # The presented token is the one that was rotated away
            grace = timedelta(seconds=settings.REFRESH_REUSE_GRACE_SECONDS)
            if session.rotated_at and now - session.rotated_at <= grace:
                session.last_used_at = now
                response = _token_response(user, session)
                await db.commit()
                return IssuedTokens(response, None, session.expires_at)

            session.is_revoked = True
            await db.commit()
            logger.warning(
                f"Refresh token reuse detected for user {user_id}, session {session.id} revoked"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Обнаружено повторное использование refresh-токена. Сессия отозвана, войдите заново.",
            )

        new_refresh = _new_refresh_token(user.id, session.expires_at)
        session.previous_token_hash = token_hash
        session.refresh_token_hash = hash_token(new_refresh)
        session.rotated_at = now
        session.last_used_at = now
        response = _token_response(user, session)
        await db.commit()

        return IssuedTokens(response, new_refresh, session.expires_at)

    @staticmethod
    async def logout(db: AsyncSession, refresh_token: str) -> bool:
        """Revokes the session the refresh token belongs to. Idempotent."""
        token_hash = hash_token(refresh_token)
        stmt = (
            update(UserSession)
            .where(
                or_(
                    UserSession.refresh_token_hash == token_hash,
                    UserSession.previous_token_hash == token_hash,
                ),
                UserSession.is_revoked == False,
            )
            .values(is_revoked=True)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def revoke_session(db: AsyncSession, user_id: int, session_id: int) -> bool:
        """Revokes a single user session by ID."""
        stmt = select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
            UserSession.is_revoked == False,
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        if not session:
            return False

        session.is_revoked = True
        await db.commit()
        return True

    @staticmethod
    async def revoke_all_sessions(
        db: AsyncSession, user_id: int, except_session_id: int | None = None
    ) -> int:
        """Revokes all sessions of a user, optionally keeping one (the current device)."""
        stmt = update(UserSession).where(
            UserSession.user_id == user_id, UserSession.is_revoked == False
        )
        if except_session_id is not None:
            stmt = stmt.where(UserSession.id != except_session_id)
        result = await db.execute(stmt.values(is_revoked=True))
        await db.commit()
        return result.rowcount

    @staticmethod
    async def get_user_sessions(db: AsyncSession, user_id: int) -> list[UserSession]:
        """Returns all live (non-revoked, non-expired) sessions of a user."""
        stmt = (
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.is_revoked == False,
                UserSession.expires_at > datetime.now(UTC),
            )
            .order_by(UserSession.last_used_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def cleanup_sessions(db: AsyncSession) -> int:
        """Deletes expired and revoked sessions, which are never valid again."""
        stmt = delete(UserSession).where(
            or_(UserSession.expires_at < datetime.now(UTC), UserSession.is_revoked == True)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount
