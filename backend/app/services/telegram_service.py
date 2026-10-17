from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import TelegramAuthError, verify_telegram_init_data
from app.models.identity import AuthProvider
from app.models.user import User
from app.schemas.station import StationRead
from app.services import identity_service
from app.services.auth_service import AuthService, IssuedTokens
from app.services.identity_service import FlowPurpose
from app.services.radio_service import RadioService

LINK_PREFIX = "link_"


@dataclass(frozen=True)
class TelegramUser:
    id: int
    username: str | None
    first_name: str | None
    last_name: str | None = None

    @property
    def display_name(self) -> str:
        full = " ".join(p for p in (self.first_name, self.last_name) if p)
        return full or (f"@{self.username}" if self.username else str(self.id))


def _require_enabled() -> str:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telegram не настроен")
    return settings.TELEGRAM_BOT_TOKEN


class TelegramService:
    @staticmethod
    def parse_init_data(init_data: str) -> TelegramUser:
        bot_token = _require_enabled()
        try:
            data = verify_telegram_init_data(
                init_data, bot_token, settings.TELEGRAM_AUTH_MAX_AGE_SECONDS
            )
        except TelegramAuthError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительные данные Telegram",
            ) from exc
        return TelegramUser(
            id=data["id"],
            username=data["username"],
            first_name=data["first_name"],
            last_name=data["last_name"],
        )

    @staticmethod
    async def login(
        db: AsyncSession, init_data: str, ip_address: str | None, user_agent: str | None
    ) -> IssuedTokens:
        tg_user = TelegramService.parse_init_data(init_data)
        user, _ = await identity_service.login_or_register(
            db,
            AuthProvider.TELEGRAM,
            str(tg_user.id),
            tg_user.display_name,
            tg_user.username,
        )
        return await AuthService.start_session(db, user, ip_address, user_agent)

    @staticmethod
    async def create_link_url(db: AsyncSession, user: User) -> tuple[str, int]:
        _require_enabled()
        if not settings.TELEGRAM_BOT_USERNAME:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Telegram не настроен"
            )
        raw = await identity_service.create_flow(
            db,
            AuthProvider.TELEGRAM,
            FlowPurpose.LINK,
            settings.TELEGRAM_LINK_TTL_SECONDS,
            user_id=user.id,
        )
        url = f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={LINK_PREFIX}{raw}"
        return url, settings.TELEGRAM_LINK_TTL_SECONDS

    @staticmethod
    async def complete_link(db: AsyncSession, raw_token: str, tg_user: TelegramUser) -> User:
        flow = await identity_service.consume_flow(db, AuthProvider.TELEGRAM, raw_token)
        if flow is None or flow.purpose != FlowPurpose.LINK or flow.user_id is None:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Ссылка недействительна")
        user = await identity_service.load_user(db, flow.user_id)
        identity_service.ensure_active(user)
        await identity_service.link_identity(
            db, user, AuthProvider.TELEGRAM, str(tg_user.id), tg_user.display_name
        )
        await db.commit()
        return user

    @staticmethod
    async def favorites(db: AsyncSession, telegram_id: int) -> list[StationRead]:
        identity = await identity_service.get_identity(db, AuthProvider.TELEGRAM, str(telegram_id))
        if identity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Аккаунт не привязан")
        user = await identity_service.load_user(db, identity.user_id)
        identity_service.ensure_active(user)
        return await RadioService.get_user_favorites(db, user.id)
