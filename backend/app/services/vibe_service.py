import random

from sqlalchemy import func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.station import Station, StationStream, StreamHealth
from app.schemas.station import StationRead
from app.services.radio_service import RadioService

# Strict, curated positive keywords for each Vibe
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

# Negative keywords to prevent vibe contamination
VIBE_EXCLUSIONS = {
    "focus": ["dance", "pop", "party", "edm", "rap", "hip hop", "metal", "techno", "rock"],
    "night_drive": ["classical", "acoustic", "country", "folk", "news", "schlager"],
    "coffee": ["techno", "edm", "heavy metal", "hard rock", "trance", "hardcore"],
    "party": ["ambient", "sleep", "meditation", "classical", "piano solo"],
    "sunset": ["hardstyle", "techno", "metal", "punk", "hard rock", "trance"],
    "world_odyssey": ["eurodance", "edm", "techno", "metal", "house"],
}

# Unwanted chatter keywords (news, talk, politics, traffic, sports)
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


def is_chatter_station(text: str) -> bool:
    """Returns True if the station is news, talk, sports, or spoken chatter."""
    text_low = text.lower()
    for kw in CHATTER_KEYWORDS:
        if kw in text_low:
            return True
    return False


def infer_vibes(tags: str, name: str = "") -> list[str]:
    """Infers strict, unadulterated musical vibes based on station tags and name."""
    text = f"{tags.lower()} {name.lower()}"

    # Instantly reject chatter/news from any vibe
    if is_chatter_station(text):
        return []

    matched = []
    for vibe, keywords in VIBE_KEYWORDS.items():
        # Check if positive keyword matches
        has_positive = any(kw in text for kw in keywords)
        if not has_positive:
            continue

        # Check if negative exclusions match
        exclusions = VIBE_EXCLUSIONS.get(vibe, [])
        has_negative = any(ex in text for ex in exclusions)
        if has_negative:
            continue

        matched.append(vibe)

    # DO NOT use generic fallback vibes! If no pure vibe matches, return empty.
    return matched


class VibeService:
    @staticmethod
    def build_vibe_query(vibe: str, exclude_languages: list[str] | None = None):
        """Builds optimized PostgreSQL query for stations of a given vibe."""
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

        # Positive keywords via GIN index array overlap
        if keywords:
            stmt = stmt.where(Station.tags.overlap(keywords))

        # Negative exclusions
        if exclusions:
            stmt = stmt.where(not_(Station.tags.overlap(exclusions)))

        # Chatter exclusions
        stmt = stmt.where(not_(Station.tags.overlap(CHATTER_KEYWORDS)))

        # Language Blacklist
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
    async def get_vibe_stations(
        db: AsyncSession,
        vibe: str,
        exclude_languages: list[str] | None = None,
    ) -> list[StationRead]:
        """Every station of a vibe that can be placed on the globe."""
        stmt = VibeService.build_vibe_query(vibe, exclude_languages).where(
            Station.latitude.isnot(None),
            Station.longitude.isnot(None),
        )
        result = await db.execute(stmt)
        return [RadioService._station_to_read(s) for s in result.scalars().all()]

    @staticmethod
    async def get_next_station(
        db: AsyncSession,
        vibe: str,
        exclude_languages: list[str] | None = None,
        exclude_ids: list[int] | None = None,
    ) -> StationRead | None:
        """Finds the next optimal station strictly adhering to the selected vibe."""
        clean_exclude_ids = [int(i) for i in (exclude_ids or []) if str(i).isdigit()]

        stmt = VibeService.build_vibe_query(vibe, exclude_languages)

        # Recent station IDs exclusion
        filtered_stmt = stmt
        if clean_exclude_ids:
            filtered_stmt = stmt.where(Station.id.notin_(clean_exclude_ids))

        result = await db.execute(filtered_stmt)
        candidates = result.scalars().all()

        if not candidates and clean_exclude_ids:
            # Fall back to full vibe pool if all were recently heard
            result = await db.execute(stmt)
            candidates = result.scalars().all()

        if not candidates:
            return None

        chosen = random.choice(candidates)
        return RadioService._station_to_read(chosen)

    @staticmethod
    async def get_available_languages(db: AsyncSession) -> list[dict]:
        """Aggregates active station languages with station counts."""
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
