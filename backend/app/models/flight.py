from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

UTC = timezone.utc


class Airport(Base):

    __tablename__ = "airports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    iata_code: Mapped[str] = mapped_column(String(3), unique=True, index=True, nullable=False)
    icao_code: Mapped[str | None] = mapped_column(String(4), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    country: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    country_code: Mapped[str] = mapped_column(String(4), index=True, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    altitude_m: Mapped[float] = mapped_column(Float, default=0.0)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class FlightRoute(Base):

    __tablename__ = "flight_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flight_number: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    airline: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    origin_airport_id: Mapped[int] = mapped_column(
        ForeignKey("airports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    destination_airport_id: Mapped[int] = mapped_column(
        ForeignKey("airports.id", ondelete="CASCADE"), nullable=False, index=True
    )

    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    real_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    cruising_altitude_m: Mapped[float] = mapped_column(Float, default=10600.0)
    cruising_speed_kmh: Mapped[float] = mapped_column(Float, default=890.0)

    recommended_vibe: Mapped[str] = mapped_column(String(64), default="world_odyssey")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    waypoints: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    origin: Mapped["Airport"] = relationship("Airport", foreign_keys=[origin_airport_id], lazy="joined")
    destination: Mapped["Airport"] = relationship("Airport", foreign_keys=[destination_airport_id], lazy="joined")


class UserFlightSession(Base):

    __tablename__ = "user_flight_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    session_token: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    route_id: Mapped[int] = mapped_column(
        ForeignKey("flight_routes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    playback_speed: Mapped[float] = mapped_column(Float, default=1.0)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    route: Mapped["FlightRoute"] = relationship("FlightRoute", lazy="joined")
