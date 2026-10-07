import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_optional_current_user
from app.models.user import User
from app.schemas.flight import (
    FlightRouteRead,
    FlightTuningResponse,
    PointTuningResponse,
    UserFlightSessionCreate,
    UserFlightSessionRead,
)
from app.services.flight_service import FlightService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/flights", tags=["flights"])


@router.get("/routes", response_model=list[FlightRouteRead])
async def list_flight_routes(
    featured_only: bool = Query(False, description="Filter only featured routes"),
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
            detail=f"Flight route with ID {route_id} not found",
        )
    return route


@router.get("/routes/{route_id}/tuning", response_model=FlightTuningResponse)
async def get_flight_tuning(
    route_id: int,
    progress: float = Query(
        0.0,
        ge=0.0,
        le=100.0,
        description="Flight progress percentage from 0.0 to 100.0",
    ),
    current_station_id: int | None = Query(None, description="Currently playing station ID for hysteresis handover"),
    db: AsyncSession = Depends(get_db),
):
    tuning = await FlightService.get_flight_tuning(
        db, route_id, progress, current_station_id=current_station_id
    )
    if not tuning:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flight route with ID {route_id} not found",
        )
    return tuning


@router.get("/tuning/point", response_model=PointTuningResponse)
async def get_point_tuning(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    current_station_id: int | None = Query(None, description="Currently playing station ID for hysteresis handover"),
    db: AsyncSession = Depends(get_db),
):
    return await FlightService.get_point_tuning(db, lat, lon, current_station_id=current_station_id)


@router.post("/session", response_model=UserFlightSessionRead)
async def create_or_resume_session(
    payload: UserFlightSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotated[User | None, Depends(get_optional_current_user)] = None,
):
    user_id = current_user.id if current_user else None
    session = await FlightService.get_or_create_session(
        db,
        route_id=payload.route_id,
        session_token=payload.session_token,
        user_id=user_id,
    )
    return session


@router.patch("/session/{session_id}", response_model=UserFlightSessionRead)
async def update_session_progress(
    session_id: int,
    progress_percent: float = Query(..., ge=0.0, le=100.0),
    playback_speed: float = Query(1.0, ge=0.1, le=120.0),
    is_paused: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    updated = await FlightService.update_session(
        db,
        session_id=session_id,
        progress_percent=progress_percent,
        playback_speed=playback_speed,
        is_paused=is_paused,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found",
        )
    return updated
