import random
from datetime import UTC, datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.cache import catalog_cache
from app.db.session import affected_rows
from app.models.favorite import Favorite
from app.models.station import Station, StationStream, StreamHealth
from app.schemas.station import StationQuery, StationRead, StationStreamRead


def csv_key(value: str | list[str] | None) -> tuple[str, ...]:
    items = value.split(",") if isinstance(value, str) else (value or [])
    return tuple(sorted({i.strip().lower() for i in items if i and i.strip()}))


class RadioService:
    @staticmethod
    def _station_to_read(station: Station) -> StationRead:
        primary = station.primary_stream
        is_active = primary.health.is_active if (primary and primary.health) else True
        last_checked = primary.health.last_checked_at if (primary and primary.health) else None

        streams_read = []
        for s in station.streams:
            s_active = s.health.is_active if s.health else True
            s_res_time = s.health.response_time_ms if s.health else None
            streams_read.append(
                StationStreamRead(
                    id=s.id,
                    stream_url=s.stream_url,
                    codec=s.codec,
                    bitrate=s.bitrate,
                    is_primary=s.is_primary,
                    is_active=s_active,
                    response_time_ms=s_res_time,
                )
            )

        return StationRead(
            id=station.id,
            station_uuid=station.station_uuid,
            name=station.name,
            stream_url=primary.stream_url if primary else "",
            homepage_url=station.homepage_url,
            favicon_url=station.favicon_url,
            country=station.country,
            country_code=station.country_code,
            latitude=station.latitude,
            longitude=station.longitude,
            language=station.language,
            location_precision=station.location_precision,
            tags=station.tags if isinstance(station.tags, list) else [],
            codec=primary.codec if primary else "MP3",
            bitrate=primary.bitrate if primary else 128,
            is_active=is_active,
            last_checked_at=last_checked,
            created_at=station.created_at,
            updated_at=station.updated_at,
            streams=streams_read,
        )

    @classmethod
    async def get_stations(
        cls,
        db: AsyncSession,
        query_params: StationQuery,
        only_active: bool = True,
    ) -> list[StationRead]:
        genres = (
            ()
            if (query_params.genres or "").strip().lower() == "any"
            else csv_key(query_params.genres)
        )
        languages = csv_key(query_params.languages)
        country = (query_params.country or "").strip().lower()
        search = (query_params.search or "").strip().lower()
        key = (
            "stations",
            only_active,
            genres,
            languages,
            country,
            search,
            query_params.limit,
            query_params.offset,
        )

        async def load() -> list[StationRead]:
            stmt = (
                select(Station)
                .join(Station.streams)
                .join(StationStream.health)
                .options(selectinload(Station.streams).selectinload(StationStream.health))
                .distinct()
            )
            if only_active:
                stmt = stmt.where(StationStream.is_primary == True, StreamHealth.is_active == True)
            if country:
                stmt = stmt.where(Station.country.ilike(f"%{country}%"))
            if languages:
                stmt = stmt.where(or_(*[Station.language.ilike(f"%{lang}%") for lang in languages]))
            if genres:
                stmt = stmt.where(Station.tags.overlap(list(genres)))
            if search:
                pattern = f"%{search}%"
                stmt = stmt.where(or_(Station.name.ilike(pattern), Station.country.ilike(pattern)))
            stmt = (
                stmt.order_by(Station.name.asc())
                .offset(query_params.offset)
                .limit(query_params.limit)
            )
            result = await db.execute(stmt)
            return [cls._station_to_read(st) for st in result.scalars().all()]

        return await catalog_cache.get_or_set(key, load)

    @classmethod
    async def get_random_station(
        cls,
        db: AsyncSession,
        genres: str | None = None,
        languages: str | None = None,
    ) -> StationRead | None:
        genre_list = () if (genres or "").strip().lower() == "any" else csv_key(genres)
        lang_list = csv_key(languages)

        async def load_ids() -> list[int]:
            stmt = (
                select(Station.id)
                .join(Station.streams)
                .join(StationStream.health)
                .where(StationStream.is_primary == True, StreamHealth.is_active == True)
            )
            if lang_list:
                stmt = stmt.where(or_(*[Station.language.ilike(f"%{lang}%") for lang in lang_list]))
            if genre_list:
                stmt = stmt.where(Station.tags.overlap(list(genre_list)))
            return list((await db.execute(stmt)).scalars().all())

        all_ids = await catalog_cache.get_or_set(("random_ids", genre_list, lang_list), load_ids)
        if not all_ids:
            return None

        chosen_id = random.choice(all_ids)
        st_stmt = (
            select(Station)
            .options(selectinload(Station.streams).selectinload(StationStream.health))
            .where(Station.id == chosen_id)
        )
        station = (await db.execute(st_stmt)).scalar_one_or_none()
        return cls._station_to_read(station) if station else None

    @classmethod
    async def get_station(cls, db: AsyncSession, station_id: int) -> StationRead | None:
        stmt = (
            select(Station)
            .options(selectinload(Station.streams).selectinload(StationStream.health))
            .where(Station.id == station_id)
        )
        station = (await db.execute(stmt)).scalar_one_or_none()
        return cls._station_to_read(station) if station else None

    @staticmethod
    async def get_available_genres(db: AsyncSession) -> list[str]:
        async def load() -> list[str]:
            res = await db.execute(select(func.unnest(Station.tags)).distinct())
            return sorted({t.lower() for t in res.scalars().all() if t})

        return await catalog_cache.get_or_set(("genres",), load)

    @staticmethod
    async def get_available_languages(db: AsyncSession) -> list[str]:
        async def load() -> list[str]:
            stmt = (
                select(Station.language)
                .join(Station.streams)
                .join(StationStream.health)
                .where(
                    StationStream.is_primary == True,
                    StreamHealth.is_active == True,
                    Station.language.isnot(None),
                )
                .distinct()
            )
            res = await db.execute(stmt)
            return sorted({item.lower() for item in res.scalars().all() if item})

        return await catalog_cache.get_or_set(("languages",), load)

    @classmethod
    async def get_user_favorites(cls, db: AsyncSession, user_id: int) -> list[StationRead]:
        stmt = (
            select(Favorite)
            .options(
                selectinload(Favorite.station)
                .selectinload(Station.streams)
                .selectinload(StationStream.health)
            )
            .where(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc())
        )
        res = await db.execute(stmt)
        favorites = res.scalars().all()
        return [cls._station_to_read(fav.station) for fav in favorites if fav.station]

    @classmethod
    async def add_favorite(cls, db: AsyncSession, user_id: int, station_id: int) -> bool | None:
        if await db.get(Station, station_id) is None:
            return None
        stmt = (
            pg_insert(Favorite)
            .values(user_id=user_id, station_id=station_id, created_at=datetime.now(UTC))
            .on_conflict_do_nothing(constraint="uq_favorites_user_station")
            .returning(Favorite.id)
        )
        inserted = (await db.execute(stmt)).scalar_one_or_none()
        await db.commit()
        return inserted is not None

    @classmethod
    async def remove_favorite(cls, db: AsyncSession, user_id: int, station_id: int) -> bool:
        stmt = delete(Favorite).where(
            Favorite.user_id == user_id, Favorite.station_id == station_id
        )
        result = await db.execute(stmt)
        await db.commit()
        return affected_rows(result) > 0
