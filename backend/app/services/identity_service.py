import re
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import random_token, sha256_hex
from app.db.session import affected_rows
from app.models.identity import AuthFlow, AuthProvider, UserIdentity
from app.models.user import User, UserRole

_USERNAME_CLEAN_RE = re.compile(r"[^a-zA-Z0-9_-]+")


class FlowPurpose:
    LINK = "link"


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


async def _username_taken(db: AsyncSession, username: str) -> bool:
    stmt = select(User.id).where(func.lower(User.username) == username.lower())
    return (await db.execute(stmt)).first() is not None


async def generate_username(db: AsyncSession, preferred: str | None, fallback: str) -> str:
    base = _USERNAME_CLEAN_RE.sub("", preferred or "")[:24]
    if len(base) < 3:
        base = fallback[:24]
    if not await _username_taken(db, base):
        return base
    for _ in range(10):
        candidate = f"{base}-{secrets.randbelow(10_000):04d}"
        if not await _username_taken(db, candidate):
            return candidate
    return f"{fallback[:20]}-{secrets.token_hex(4)}"


async def get_identity(db: AsyncSession, provider: str, provider_uid: str) -> UserIdentity | None:
    stmt = select(UserIdentity).where(
        UserIdentity.provider == provider, UserIdentity.provider_uid == provider_uid
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_identity(db: AsyncSession, user_id: int, provider: str) -> UserIdentity | None:
    stmt = select(UserIdentity).where(
        UserIdentity.user_id == user_id, UserIdentity.provider == provider
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def load_user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден"
        )
    return user


def ensure_active(user: User) -> None:
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Учетная запись отключена"
        )


async def login_or_register(
    db: AsyncSession,
    provider: str,
    provider_uid: str,
    display_name: str | None,
    preferred_username: str | None,
) -> tuple[User, UserIdentity]:
    identity = await get_identity(db, provider, provider_uid)
    if identity is not None:
        user = await load_user(db, identity.user_id)
        ensure_active(user)
        if display_name and identity.display_name != display_name:
            identity.display_name = display_name
        return user, identity

    username = await generate_username(db, preferred_username, f"{provider}-{provider_uid}")
    user = User(username=username, email=None, role=UserRole.USER, is_active=True)
    identity = UserIdentity(provider=provider, provider_uid=provider_uid, display_name=display_name)
    user.identities.append(identity)
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        identity = await get_identity(db, provider, provider_uid)
        if identity is None:
            raise
        user = await load_user(db, identity.user_id)
        ensure_active(user)
    return user, identity


async def link_identity(
    db: AsyncSession,
    user: User,
    provider: str,
    provider_uid: str,
    display_name: str | None,
) -> UserIdentity:
    existing = await get_identity(db, provider, provider_uid)
    if existing is not None:
        if existing.user_id != user.id:
            raise _conflict("Аккаунт уже привязан к другому пользователю")
        existing.display_name = display_name or existing.display_name
        return existing
    if await get_user_identity(db, user.id, provider) is not None:
        raise _conflict("Другой аккаунт этого сервиса уже привязан")
    identity = UserIdentity(provider=provider, provider_uid=provider_uid, display_name=display_name)
    user.identities.append(identity)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict("Аккаунт уже привязан") from exc
    return identity


async def unlink_identity(db: AsyncSession, user: User, provider: str) -> None:
    if provider not in AuthProvider.ALL:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Способ входа не найден")
    identities = (
        (await db.execute(select(UserIdentity).where(UserIdentity.user_id == user.id)))
        .scalars()
        .all()
    )
    target = next((i for i in identities if i.provider == provider), None)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Способ входа не найден")
    if len(identities) == 1:
        raise _conflict("Нельзя отвязать единственный способ входа")
    if target in user.identities:
        user.identities.remove(target)
    await db.delete(target)
    await db.commit()


async def create_flow(
    db: AsyncSession,
    provider: str,
    purpose: str,
    ttl_seconds: int,
    user_id: int | None = None,
) -> str:
    raw = random_token(32)
    now = datetime.now(UTC)
    db.add(
        AuthFlow(
            token_hash=sha256_hex(raw),
            provider=provider,
            purpose=purpose,
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
    )
    await db.commit()
    return raw


async def consume_flow(db: AsyncSession, provider: str, raw: str) -> AuthFlow | None:
    if not raw or len(raw) > 128:
        return None
    stmt = (
        delete(AuthFlow)
        .where(AuthFlow.token_hash == sha256_hex(raw), AuthFlow.provider == provider)
        .returning(AuthFlow)
    )
    flow = (await db.execute(stmt)).scalar_one_or_none()
    await db.commit()
    if flow is None or flow.expires_at < datetime.now(UTC):
        return None
    return flow


async def cleanup_flows(db: AsyncSession) -> int:
    result = await db.execute(delete(AuthFlow).where(AuthFlow.expires_at < datetime.now(UTC)))
    await db.commit()
    return affected_rows(result)
