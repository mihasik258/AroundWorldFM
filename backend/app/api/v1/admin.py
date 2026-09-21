from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.models.session import UserSession
from app.models.station import Station, StationStream, StreamHealth
from app.models.user import User, UserRole
from app.schemas.station import StationCreate, StationRead, StationUpdate
from app.services.radio_service import RadioService
from app.services.stream_checker import run_stream_health_check

router = APIRouter(
    prefix="/admin",
    tags=["Панель администратора (RBAC)"],
    dependencies=[Depends(require_role([UserRole.ADMIN]))],
)


@router.get("/stats", summary="Системная статистика сервиса (только для роли ADMIN)")
async def get_system_stats(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_stations = (await db.execute(select(func.count(Station.id)))).scalar() or 0
    active_stations = (
        await db.execute(
            select(func.count(StationStream.id))
            .join(StationStream.health)
            .where(StationStream.is_primary == True, StreamHealth.is_active == True)
        )
    ).scalar() or 0
    active_sessions = (
        await db.execute(select(func.count(UserSession.id)).where(UserSession.is_revoked == False))
    ).scalar() or 0

    availability_pct = (
        round((active_stations / total_stations * 100), 1) if total_stations > 0 else 0.0
    )

    return {
        "total_users": total_users,
        "total_stations": total_stations,
        "active_stations": active_stations,
        "stream_availability_percentage": availability_pct,
        "active_sessions": active_sessions,
    }


@router.post(
    "/stations",
    response_model=StationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить новую радиостанцию",
)
async def create_station(
    station_in: StationCreate,
    db: AsyncSession = Depends(get_db),
):
    # Check if stream_url already exists in station_streams
    stmt = select(StationStream).where(StationStream.stream_url == station_in.stream_url)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Станция с таким URL потока уже существует",
        )

    tag_list = [t.strip().lower() for t in station_in.tags.split(",") if t.strip()] if station_in.tags else []

    station = Station(
        name=station_in.name,
        homepage_url=station_in.homepage_url,
        favicon_url=station_in.favicon_url,
        country=station_in.country,
        country_code=station_in.country_code,
        latitude=station_in.latitude,
        longitude=station_in.longitude,
        language=station_in.language,
        tags=tag_list,
    )
    db.add(station)
    await db.flush()

    stream = StationStream(
        station_id=station.id,
        stream_url=station_in.stream_url,
        codec=station_in.codec,
        bitrate=station_in.bitrate,
        is_primary=True,
    )
    db.add(stream)
    await db.flush()

    health = StreamHealth(stream_id=stream.id, is_active=True)
    db.add(health)
    await db.commit()
    await db.refresh(station)
    return RadioService._station_to_read(station)


@router.patch(
    "/stations/{station_id}", response_model=StationRead, summary="Обновить параметры радиостанции"
)
async def update_station(
    station_id: int,
    station_in: StationUpdate,
    db: AsyncSession = Depends(get_db),
):
    station = await db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Станция не найдена")

    update_data = station_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(station, field, value)

    await db.commit()
    await db.refresh(station)
    return RadioService._station_to_read(station)


@router.delete("/stations/{station_id}", summary="Удалить радиостанцию")
async def delete_station(station_id: int, db: AsyncSession = Depends(get_db)):
    station = await db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Станция не найдена")

    await db.delete(station)
    await db.commit()
    return {"status": "ok", "message": f"Станция '{station.name}' успешно удалена"}


@router.post("/trigger-stream-check", summary="Принудительный запуск проверки доступности потоков")
async def trigger_stream_check(db: AsyncSession = Depends(get_db)):
    await run_stream_health_check(db)
    return {"status": "ok", "message": "Проверка доступности потоков успешно завершена"}
