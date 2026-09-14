from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.favorite import Favorite

UTC = timezone.utc


class Station(Base):
    """Radio station entity with geo-location and canonical metadata."""

    __tablename__ = "stations"
    __table_args__ = (
        Index("idx_stations_tags_gin", "tags", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    station_uuid: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    homepage_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Geo-location & Language
    country: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    language: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Normalized musical tags as PostgreSQL array with GIN index
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, nullable=False, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    streams: Mapped[list["StationStream"]] = relationship(
        "StationStream", back_populates="station", cascade="all, delete-orphan", lazy="selectin"
    )
    favorites: Mapped[list["Favorite"]] = relationship(
        "Favorite", back_populates="station", cascade="all, delete-orphan"
    )

    @property
    def primary_stream(self) -> "StationStream | None":
        for s in self.streams:
            if s.is_primary:
                return s
        return self.streams[0] if self.streams else None


class StationStream(Base):
    """Stream URL and encoding for a station."""

    __tablename__ = "station_streams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stream_url: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    codec: Mapped[str] = mapped_column(String(32), default="MP3", nullable=False)
    bitrate: Mapped[int] = mapped_column(Integer, default=128, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    station: Mapped["Station"] = relationship("Station", back_populates="streams")
    health: Mapped["StreamHealth | None"] = relationship(
        "StreamHealth", back_populates="stream", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )


class StreamHealth(Base):
    """Live health status and uptime telemetry for a station stream."""

    __tablename__ = "stream_health"

    stream_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("station_streams.id", ondelete="CASCADE"), primary_key=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    check_fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    stream: Mapped["StationStream"] = relationship("StationStream", back_populates="health")

