import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.station import Station
from app.models.user import User
from app.schemas.station import StationQuery, StationRead
from app.services.now_playing_service import NowPlayingService
from app.services.radio_service import RadioService
from app.services.vibe_service import VIBE_LABELS, VIBE_PATTERN, VibeService

router = APIRouter(prefix="/stations", tags=["Станции"])

MAX_EXCLUDED_LANGUAGES = 200


def parse_excluded_languages(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    langs = [lang.strip() for lang in raw.split(",") if lang.strip()]
    if len(langs) > MAX_EXCLUDED_LANGUAGES:
        raise HTTPException(
            status_code=422,
            detail="Слишком много языков",
        )
    return langs


@router.get(
    "/vibe/next",
    response_model=StationRead,
    summary="Следующая станция",
)
async def get_next_vibe_station(
    vibe: str = Query("focus", pattern=VIBE_PATTERN, description="Вайб"),
    exclude_languages: str | None = Query(None, description="Исключаемые языки"),
    exclude_ids: str | None = Query(None, description="Исключаемые ID"),
    db: AsyncSession = Depends(get_db),
):
    clean_exclude_langs = parse_excluded_languages(exclude_languages)
    clean_exclude_ids = [int(i.strip()) for i in exclude_ids.split(",") if i.strip().isdigit()] if exclude_ids else None

    station = await VibeService.get_next_station(
        db=db,
        vibe=vibe,
        exclude_languages=clean_exclude_langs,
        exclude_ids=clean_exclude_ids,
    )
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Станции не найдены",
        )
    return station


@router.get(
    "/vibe/stations",
    response_model=list[StationRead],
    summary="Станции вайба",
)
async def get_vibe_stations(
    vibe: str = Query("focus", pattern=VIBE_PATTERN, description="Вайб"),
    exclude_languages: str | None = Query(None, description="Исключаемые языки"),
    db: AsyncSession = Depends(get_db),
):
    clean_exclude_langs = parse_excluded_languages(exclude_languages)
    return await VibeService.get_vibe_stations(
        db=db,
        vibe=vibe,
        exclude_languages=clean_exclude_langs,
    )


@router.get(
    "/vibe/languages",
    summary="Языки с числом станций",
)
async def get_available_languages(db: AsyncSession = Depends(get_db)):
    return await VibeService.get_available_languages(db)


@router.get(
    "/vibe/list",
    summary="Вайбы",
)
async def get_supported_vibes():
    return [
        {"id": k, "label": v} for k, v in VIBE_LABELS.items()
    ]


@router.get(
    "",
    response_model=list[StationRead],
    summary="Станции",
)
async def list_stations(
    genres: str | None = Query(None, description="Жанры"),
    languages: str | None = Query(None, description="Языки"),
    country: str | None = Query(None, description="Страна"),
    search: str | None = Query(None, description="Поиск"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query_params = StationQuery(
        genres=genres,
        languages=languages,
        country=country,
        search=search,
        limit=limit,
        offset=offset,
    )
    return await RadioService.get_stations(db, query_params)


@router.get(
    "/random",
    response_model=StationRead,
    summary="Случайная станция",
)
async def get_random_station(
    genres: str | None = Query(None, description="Жанры"),
    languages: str | None = Query(None, description="Языки"),
    db: AsyncSession = Depends(get_db),
):
    station = await RadioService.get_random_station(db, genres=genres, languages=languages)
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Станции не найдены",
        )
    return station


@router.get(
    "/genres",
    response_model=list[str],
    summary="Жанры",
)
async def list_genres(db: AsyncSession = Depends(get_db)):
    return await RadioService.get_available_genres(db)


@router.get(
    "/languages",
    response_model=list[str],
    summary="Языки",
)
async def list_languages(db: AsyncSession = Depends(get_db)):
    return await RadioService.get_available_languages(db)


@router.get(
    "/favorites/my",
    response_model=list[StationRead],
    summary="Избранное",
)
async def get_my_favorites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await RadioService.get_user_favorites(db, current_user.id)


@router.post(
    "/favorites/{station_id}",
    summary="Добавить в избранное",
)
async def add_to_favorites(
    station_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    added = await RadioService.add_favorite(db, current_user.id, station_id)
    if not added:
        return {"status": "ok", "message": "Уже в избранном"}
    return {"status": "ok", "message": "Добавлено"}


@router.delete(
    "/favorites/{station_id}",
    summary="Удалить из избранного",
)
async def remove_from_favorites(
    station_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    removed = await RadioService.remove_favorite(db, current_user.id, station_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Нет в избранном",
        )
    return {"status": "ok", "message": "Удалено"}


@router.get(
    "/{station_id}/stream",
    summary="Аудиопоток",
)
async def proxy_station_stream(station_id: int, db: AsyncSession = Depends(get_db)):
    station = await db.get(Station, station_id)
    if not station or not station.primary_stream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поток не найден",
        )

    stream_url = station.primary_stream.stream_url
    client = httpx.AsyncClient(timeout=15.0, follow_redirects=True, trust_env=False)

    async def stream_generator():
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Icy-MetaData": "0",
            }
            async with client.stream("GET", stream_url, headers=headers) as resp:
                if resp.status_code not in (200, 206):
                    yield b""
                    return
                async for chunk in resp.aiter_bytes(chunk_size=4096):
                    yield chunk
        except Exception:
            yield b""
        finally:
            await client.aclose()

    return StreamingResponse(
        stream_generator(),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Accept-Ranges": "bytes",
        },
    )


@router.get(
    "/{station_id}/now-playing",
    summary="Текущий трек",
)
async def get_station_now_playing(station_id: int, db: AsyncSession = Depends(get_db)):
    station = await db.get(Station, station_id)
    if not station or not station.primary_stream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поток не найден",
        )
    return await NowPlayingService.get_now_playing(station_id, station.primary_stream.stream_url)
