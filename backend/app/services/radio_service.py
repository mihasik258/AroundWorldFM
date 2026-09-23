import random

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.favorite import Favorite
from app.models.station import Station, StationStream, StreamHealth
from app.schemas.station import StationQuery, StationRead, StationStreamRead


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
        """Fetches stations matching filters (genres, languages, country, search)."""
        stmt = (
            select(Station)
            .join(Station.streams)
            .join(StationStream.health)
            .options(selectinload(Station.streams).selectinload(StationStream.health))
            .distinct()
        )

        if only_active:
            stmt = stmt.where(StationStream.is_primary == True, StreamHealth.is_active == True)

        # Country filter
        if query_params.country:
            stmt = stmt.where(Station.country.ilike(f"%{query_params.country}%"))

        # Language filter (supports comma-separated list of allowed languages)
        if query_params.languages:
            langs = [
                item.strip().lower() for item in query_params.languages.split(",") if item.strip()
            ]
            if langs:
                lang_conditions = [Station.language.ilike(f"%{lang}%") for lang in langs]
                stmt = stmt.where(or_(*lang_conditions))

        # Genre filter: array overlap using GIN index
        if query_params.genres and query_params.genres.lower() != "any":
            genres = [g.strip().lower() for g in query_params.genres.split(",") if g.strip()]
            if genres:
                stmt = stmt.where(Station.tags.overlap(genres))

        # Text search (in name or country)
        if query_params.search:
            s = f"%{query_params.search.strip()}%"
            stmt = stmt.where(or_(Station.name.ilike(s), Station.country.ilike(s)))

        stmt = (
            stmt.order_by(Station.name.asc()).offset(query_params.offset).limit(query_params.limit)
        )
        result = await db.execute(stmt)
        stations = result.scalars().all()
        return [cls._station_to_read(st) for st in stations]

    @classmethod
    async def get_random_station(
        cls,
        db: AsyncSession,
        genres: str | None = None,
        languages: str | None = None,
    ) -> StationRead | None:
        """Returns a single random active station matching criteria."""
        stmt = (
            select(Station.id)
            .join(Station.streams)
            .join(StationStream.health)
            .where(StationStream.is_primary == True, StreamHealth.is_active == True)
        )

        if languages:
            langs = [item.strip().lower() for item in languages.split(",") if item.strip()]
            if langs:
                lang_conditions = [Station.language.ilike(f"%{lang}%") for lang in langs]
                stmt = stmt.where(or_(*lang_conditions))

        if genres and genres.lower() != "any":
            genre_list = [g.strip().lower() for g in genres.split(",") if g.strip()]
            if genre_list:
                stmt = stmt.where(Station.tags.overlap(genre_list))

        ids_res = await db.execute(stmt)
        all_ids = ids_res.scalars().all()

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

    @staticmethod
    async def get_available_genres(db: AsyncSession) -> list[str]:
        """Returns distinct sorted genres/tags from stations using PostgreSQL unnest."""
        stmt = select(func.unnest(Station.tags)).distinct()
        res = await db.execute(stmt)
        tags = [t.lower() for t in res.scalars().all() if t]
        return sorted(list(set(tags)))

    @staticmethod
    async def get_available_languages(db: AsyncSession) -> list[str]:
        """Returns distinct sorted languages from active stations."""
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
        langs = [item.lower() for item in res.scalars().all() if item]
        return sorted(set(langs))

    @classmethod
    async def get_user_favorites(cls, db: AsyncSession, user_id: int) -> list[StationRead]:
        """Returns list of stations favorited by a user."""
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
    async def add_favorite(cls, db: AsyncSession, user_id: int, station_id: int) -> bool:
        """Adds station to user's favorites if not already present."""
        stmt = select(Favorite).where(
            Favorite.user_id == user_id, Favorite.station_id == station_id
        )
        exists = (await db.execute(stmt)).scalar_one_or_none()
        if exists:
            return False

        fav = Favorite(user_id=user_id, station_id=station_id)
        db.add(fav)
        await db.commit()
        return True

    @classmethod
    async def remove_favorite(cls, db: AsyncSession, user_id: int, station_id: int) -> bool:
        """Removes station from user's favorites."""
        stmt = select(Favorite).where(
            Favorite.user_id == user_id, Favorite.station_id == station_id
        )
        fav = (await db.execute(stmt)).scalar_one_or_none()
        if not fav:
            return False
        await db.delete(fav)
        await db.commit()
        return True
