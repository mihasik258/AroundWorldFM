from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.flight import (
    FlightRouteRead,
    FlightTuningResponse,
    PointTuningResponse,
)
from app.services.flight_service import FlightService

router = APIRouter(prefix="/flights", tags=["Полёты"])


@router.get("/routes", response_model=list[FlightRouteRead])
async def list_flight_routes(
    featured_only: bool = Query(False, description="Только избранные"),
    db: AsyncSession = Depends(get_db),
):
    routes = await FlightService.get_routes(db, featured_only=featured_only)
    return routes


@router.get("/routes/{route_id}", response_model=FlightRouteRead)
async def get_flight_route(
    route_id: int,
    db: AsyncSession = Depends(get_db),
):
    route = await FlightService.get_route(db, route_id)
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Маршрут не найден",
        )
    return route


@router.get("/routes/{route_id}/tuning", response_model=FlightTuningResponse)
async def get_flight_tuning(
    route_id: int,
    progress: float = Query(
        0.0,
        ge=0.0,
        le=100.0,
        description="Прогресс, %",
    ),
    current_station_id: int | None = Query(None, description="Текущая станция"),
    db: AsyncSession = Depends(get_db),
):
    tuning = await FlightService.get_flight_tuning(
        db, route_id, progress, current_station_id=current_station_id
    )
    if not tuning:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Маршрут не найден",
        )
    return tuning


@router.get("/tuning/point", response_model=PointTuningResponse)
async def get_point_tuning(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    current_station_id: int | None = Query(None, description="Текущая станция"),
    db: AsyncSession = Depends(get_db),
):
    return await FlightService.get_point_tuning(db, lat, lon, current_station_id=current_station_id)
