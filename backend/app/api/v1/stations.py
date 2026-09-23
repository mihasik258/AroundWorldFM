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
from app.services.vibe_service import VIBE_LABELS, VibeService

router = APIRouter(prefix="/stations", tags=["Радиостанции и избранное"])


@router.get(
    "/vibe/next",
    response_model=StationRead,
    summary="Получить следующую радиостанцию по выбранному вайбу с исключением языков",
)
async def get_next_vibe_station(
    vibe: str = Query("focus", description="Выбранный вайб (focus, night_drive, coffee, party, sunset, world_odyssey)"),
    exclude_languages: str | None = Query(None, description="Список исключаемых языков через запятую"),
    exclude_ids: str | None = Query(None, description="Список ID недавно прослушанных станций через запятую"),
    db: AsyncSession = Depends(get_db),
):
    clean_exclude_langs = [lang.strip() for lang in exclude_languages.split(",") if lang.strip()] if exclude_languages else None
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
            detail="Не найдено доступных станций для заданного вайба",
        )
    return station


@router.get(
    "/vibe/stations",
    response_model=list[StationRead],
    summary="Все станции выбранного вайба с координатами (для глобуса)",
)
async def get_vibe_stations(
    vibe: str = Query("focus", description="Выбранный вайб (focus, night_drive, coffee, party, sunset, world_odyssey)"),
    exclude_languages: str | None = Query(None, description="Список исключаемых языков через запятую"),
    db: AsyncSession = Depends(get_db),
):
    clean_exclude_langs = [lang.strip() for lang in exclude_languages.split(",") if lang.strip()] if exclude_languages else None
    return await VibeService.get_vibe_stations(
        db=db,
        vibe=vibe,
        exclude_languages=clean_exclude_langs,
    )


@router.get(
    "/vibe/languages",
    summary="Список всех доступных языков вещания с количеством станций",
)
async def get_available_languages(db: AsyncSession = Depends(get_db)):
    return await VibeService.get_available_languages(db)


@router.get(
    "/vibe/list",
    summary="Список поддерживаемых вайбов",
)
async def get_supported_vibes():
    return [
        {"id": k, "label": v} for k, v in VIBE_LABELS.items()
    ]


@router.get(
    "",
    response_model=list[StationRead],
    summary="Получение списка радиостанций с фильтрацией (жанры, языки, страна, поиск)",
)
async def list_stations(
    genres: str | None = Query(None, description="Список жанров через запятую"),
    languages: str | None = Query(None, description="Список языков через запятую"),
    country: str | None = Query(None, description="Страна"),
    search: str | None = Query(None, description="Поисковый запрос"),
    limit: int = Query(50, ge=1, le=3000),
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
    summary="Получение случайной работающей радиостанции по фильтрам",
)
async def get_random_station(
    genres: str | None = Query(None, description="Список жанров через запятую"),
    languages: str | None = Query(None, description="Список языков через запятую"),
    db: AsyncSession = Depends(get_db),
):
    station = await RadioService.get_random_station(db, genres=genres, languages=languages)
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Не найдено доступных работающих радиостанций по заданным критериям",
        )
    return station


@router.get(
    "/genres",
    response_model=list[str],
    summary="Список всех доступных музыкальных жанров",
)
async def list_genres(db: AsyncSession = Depends(get_db)):
    return await RadioService.get_available_genres(db)


@router.get(
    "/languages",
    response_model=list[str],
    summary="Список доступных языков вещания",
)
async def list_languages(db: AsyncSession = Depends(get_db)):
    return await RadioService.get_available_languages(db)


# --- Избранное (Favorites) ---


@router.get(
    "/favorites/my",
    response_model=list[StationRead],
    summary="Получить избранные станции текущего пользователя",
)
async def get_my_favorites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await RadioService.get_user_favorites(db, current_user.id)


@router.post(
    "/favorites/{station_id}",
    summary="Добавить станцию в избранное",
)
async def add_to_favorites(
    station_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    added = await RadioService.add_favorite(db, current_user.id, station_id)
    if not added:
        return {"status": "ok", "message": "Станция уже в избранном"}
    return {"status": "ok", "message": "Станция добавлена в избранное"}


@router.delete(
    "/favorites/{station_id}",
    summary="Удалить станцию из избранного",
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
            detail="Станция не найдена в избранном",
        )
    return {"status": "ok", "message": "Станция удалена из избранного"}


@router.get(
    "/{station_id}/stream",
    summary="Проксирование аудиопотока станции (обход блокировок провайдеров и CORS)",
)
async def proxy_station_stream(station_id: int, db: AsyncSession = Depends(get_db)):
    station = await db.get(Station, station_id)
    if not station or not station.primary_stream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Станция или аудиопоток не найдены",
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
    summary="Получить текущий играющий трек (Now Playing) и прямую ссылку на Spotify",
)
async def get_station_now_playing(station_id: int, db: AsyncSession = Depends(get_db)):
    station = await db.get(Station, station_id)
    if not station or not station.primary_stream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Станция или аудиопоток не найдены",
        )
    return await NowPlayingService.get_now_playing(station_id, station.primary_stream.stream_url)
