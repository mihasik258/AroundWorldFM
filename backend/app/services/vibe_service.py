import random

from sqlalchemy import func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.cache import catalog_cache
from app.models.station import Station, StationStream, StreamHealth
from app.schemas.station import StationRead
from app.services.radio_service import RadioService, csv_key

VIBE_KEYWORDS = {
    "focus": [
        "ambient", "drone", "soundscape", "neoclassical", "piano", "sleep",
        "study", "meditation", "chillout", "zen", "mindfulness", "instrumental", "calm"
    ],
    "night_drive": [
        "synthwave", "retrowave", "darksynth", "cyberpunk", "outrun", "dreamwave",
        "future synth", "synthpop", "darkwave", "melodic techno", "trance", "vaporwave"
    ],
    "coffee": [
        "jazz", "smooth jazz", "acoustic", "indie", "soul", "neo-soul",
        "bossa nova", "folk", "blues", "lo-fi", "mellow"
    ],
    "party": [
        "dance", "club", "house", "electro house", "edm", "disco", "nu-disco",
        "eurodance", "party", "techno", "electronic"
    ],
    "sunset": [
        "chill", "lofi", "lo-fi", "downtempo", "tropical", "balearic",
        "sunset", "lounge", "groove", "dub", "reggae"
    ],
    "world_odyssey": [
        "world", "ethnic", "tango", "flamenco", "bossa nova", "celtic",
        "balkan", "arabic", "oriental", "african", "afrobeat", "greek", "fado", "salsa"
    ],
}

VIBE_EXCLUSIONS = {
    "focus": ["dance", "pop", "party", "edm", "rap", "hip hop", "metal", "techno", "rock"],
    "night_drive": ["classical", "acoustic", "country", "folk", "news", "schlager"],
    "coffee": ["techno", "edm", "heavy metal", "hard rock", "trance", "hardcore"],
    "party": ["ambient", "sleep", "meditation", "classical", "piano solo"],
    "sunset": ["hardstyle", "techno", "metal", "punk", "hard rock", "trance"],
    "world_odyssey": ["eurodance", "edm", "techno", "metal", "house"],
}

CHATTER_KEYWORDS = [
    "news", "talk", "speech", "spoken", "politics", "traffic", "weather",
    "information", "nachrichten", "actualité", "noticias", "notícias",
    "новости", "болтовня", "podcast", "sports", "sport", "debate",
    "interview", "current affairs", "bbc radio 4", "bbc radio 5",
    "npr news", "lbc", "cbs news", "cnn", "fox news",
    "радио россии", "вести фм", "эхо", "радио свобода"
]

VIBE_LABELS = {
    "focus": "Deep Focus",
    "night_drive": "Night Drive",
    "coffee": "Morning Coffee",
    "party": "Energy & Party",
    "sunset": "Sunset Chill",
    "world_odyssey": "World Odyssey",
}


VIBE_PATTERN = "^(" + "|".join(VIBE_KEYWORDS) + ")$"


def is_chatter_station(text: str) -> bool:
    text_low = text.lower()
    for kw in CHATTER_KEYWORDS:
        if kw in text_low:
            return True
    return False


def infer_vibes(tags: str, name: str = "") -> list[str]:
    text = f"{tags.lower()} {name.lower()}"

    if is_chatter_station(text):
        return []

    matched = []
    for vibe, keywords in VIBE_KEYWORDS.items():
        has_positive = any(kw in text for kw in keywords)
        if not has_positive:
            continue

        exclusions = VIBE_EXCLUSIONS.get(vibe, [])
        has_negative = any(ex in text for ex in exclusions)
        if has_negative:
            continue

        matched.append(vibe)

    return matched


class VibeService:
    @staticmethod
    def build_vibe_query(vibe: str, exclude_languages: list[str] | None = None):
        vibe = vibe.lower().strip()
        keywords = VIBE_KEYWORDS.get(vibe, [])
        exclusions = VIBE_EXCLUSIONS.get(vibe, [])

        clean_exclude_langs = [lang.strip().lower() for lang in (exclude_languages or []) if lang.strip()]

        stmt = (
            select(Station)
            .join(Station.streams)
            .join(StationStream.health)
            .options(selectinload(Station.streams).selectinload(StationStream.health))
            .where(StationStream.is_primary == True, StreamHealth.is_active == True)
        )

        if keywords:
            stmt = stmt.where(Station.tags.overlap(keywords))

        if exclusions:
            stmt = stmt.where(not_(Station.tags.overlap(exclusions)))

        stmt = stmt.where(not_(Station.tags.overlap(CHATTER_KEYWORDS)))

        if clean_exclude_langs:
            for el in clean_exclude_langs:
                stmt = stmt.where(
                    or_(
                        Station.language.is_(None),
                        not_(Station.language.ilike(f"%{el}%")),
                    )
                )

        return stmt

    @staticmethod
    async def _vibe_pool(
        db: AsyncSession,
        vibe: str,
        exclude_languages: list[str] | None = None,
    ) -> list[StationRead]:
        langs = csv_key(exclude_languages)

        async def load() -> list[StationRead]:
            result = await db.execute(VibeService.build_vibe_query(vibe, list(langs)))
            return [RadioService._station_to_read(s) for s in result.scalars().all()]

        return await catalog_cache.get_or_set(("vibe", vibe, langs), load)

    @staticmethod
    async def get_vibe_stations(
        db: AsyncSession,
        vibe: str,
        exclude_languages: list[str] | None = None,
    ) -> list[StationRead]:
        pool = await VibeService._vibe_pool(db, vibe, exclude_languages)
        return [s for s in pool if s.latitude is not None and s.longitude is not None]

    @staticmethod
    async def get_next_station(
        db: AsyncSession,
        vibe: str,
        exclude_languages: list[str] | None = None,
        exclude_ids: list[int] | None = None,
    ) -> StationRead | None:
        pool = await VibeService._vibe_pool(db, vibe, exclude_languages)
        recent = set(exclude_ids or [])
        candidates = [s for s in pool if s.id not in recent] or pool
        return random.choice(candidates) if candidates else None

    @staticmethod
    async def get_available_languages(db: AsyncSession) -> list[dict]:
        return await catalog_cache.get_or_set(
            ("vibe_languages",), lambda: VibeService._load_languages(db)
        )

    @staticmethod
    async def _load_languages(db: AsyncSession) -> list[dict]:
        stmt = (
            select(Station.language, func.count(Station.id).label("count"))
            .join(Station.streams)
            .join(StationStream.health)
            .where(
                StationStream.is_primary == True,
                StreamHealth.is_active == True,
                Station.language.isnot(None),
                Station.language != "",
                not_(Station.tags.overlap(CHATTER_KEYWORDS)),
            )
            .group_by(Station.language)
            .order_by(func.count(Station.id).desc())
        )
        result = await db.execute(stmt)
        rows = result.all()

        languages = []
        for lang, count in rows:
            clean = lang.strip().lower()
            if clean in ["unknown", "other", "null", "undefined"]:
                continue
            languages.append({
                "code": clean,
                "name": clean.capitalize(),
                "count": count,
            })
        return languages
