import json
import logging
from pathlib import Path

import anyio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.net import UnsafeURLError, validate_http_url
from app.core.security import hash_password_async
from app.models.identity import AuthProvider, UserIdentity
from app.models.station import Station, StationStream, StreamHealth
from app.models.user import User, UserRole
from app.services.catalog_normalize import normalize_language, resolve_coordinates

logger = logging.getLogger(__name__)

CATALOG_FILE = Path(__file__).resolve().parent.parent / "data" / "stations_curated.json"

DEMO_USERS = (
    ("admin", "admin@aroundfm.local", "Admin12345!", UserRole.ADMIN),
    ("listener", "listener@aroundfm.local", "User12345!", UserRole.USER),
)


def _tags(raw: object) -> list[str]:
    items = raw.split(",") if isinstance(raw, str) else raw if isinstance(raw, list) else []
    return sorted({str(t).strip().lower() for t in items if str(t).strip()})


def _optional_url(value: object) -> str | None:
    if not value:
        return None
    try:
        return validate_http_url(str(value))
    except UnsafeURLError:
        return None


def build_station(item: dict) -> Station | None:
    try:
        stream_url = validate_http_url(str(item.get("stream_url", "")))
    except UnsafeURLError:
        return None
    country = str(item.get("country") or "Unknown")[:100]
    lat, lon = item.get("latitude"), item.get("longitude")
    if (lat is not None and not -90 <= lat <= 90) or (lon is not None and not -180 <= lon <= 180):
        lat = lon = None
    lat, lon = resolve_coordinates(country, lat, lon)
    return Station(
        station_uuid=item.get("station_uuid"),
        name=str(item.get("name") or "Unknown")[:255],
        homepage_url=_optional_url(item.get("homepage_url")),
        favicon_url=_optional_url(item.get("favicon_url")),
        country=country,
        country_code=item.get("country_code"),
        latitude=lat,
        longitude=lon,
        language=normalize_language(item.get("language")),
        tags=_tags(item.get("tags")),
        streams=[
            StationStream(
                stream_url=stream_url,
                codec=item.get("codec") or "MP3",
                bitrate=item.get("bitrate") or 128,
                is_primary=True,
                health=StreamHealth(
                    is_active=bool(item.get("is_active", True)), check_fail_count=0
                ),
            )
        ],
    )


async def seed_catalog(db: AsyncSession, catalog_file: Path = CATALOG_FILE) -> int:
    if (await db.execute(select(func.count(Station.id)))).scalar_one():
        return 0
    items = json.loads(await anyio.Path(catalog_file).read_text(encoding="utf-8"))
    seen: set[str] = set()
    stations = []
    for item in items:
        station = build_station(item)
        if station is None or station.streams[0].stream_url in seen:
            continue
        seen.add(station.streams[0].stream_url)
        stations.append(station)
    db.add_all(stations)
    await db.commit()
    logger.info("Seeded %d stations", len(stations))
    return len(stations)


async def create_user(
    db: AsyncSession, username: str, email: str | None, password: str, role: UserRole
) -> User:
    user = User(username=username, email=email, role=role, is_active=True)
    user.identities.append(
        UserIdentity(
            provider=AuthProvider.PASSWORD,
            provider_uid=username,
            secret_hash=await hash_password_async(password),
        )
    )
    db.add(user)
    await db.commit()
    return user


async def seed_demo_users(db: AsyncSession) -> int:
    created = 0
    for username, email, password, role in DEMO_USERS:
        exists = (await db.execute(select(User.id).where(User.username == username))).first()
        if exists:
            continue
        await create_user(db, username, email, password, role)
        created += 1
    if created:
        logger.warning("Created %d demo users with public passwords", created)
    return created
