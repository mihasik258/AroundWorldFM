from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.station import StationRead

VIBE_LABELS = {
    "focus": "Фокус",
    "night_drive": "Ночной драйв",
    "coffee": "Кофе",
    "party": "Вечеринка",
    "sunset": "Закат",
    "world_odyssey": "Мировая одиссея",
}


class VibeService:
    @staticmethod
    async def get_next_station(
        db: AsyncSession,
        vibe: str,
        exclude_languages: list[str] | None = None,
        exclude_ids: list[int] | None = None,
    ) -> StationRead | None:
        return None

    @staticmethod
    async def get_vibe_stations(
        db: AsyncSession,
        vibe: str,
        exclude_languages: list[str] | None = None,
    ) -> list[StationRead]:
        return []

    @staticmethod
    async def get_available_languages(db: AsyncSession) -> list[str]:
        return []
