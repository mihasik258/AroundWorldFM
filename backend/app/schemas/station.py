from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_tags(v: list[str] | str | None) -> list[str]:
    """Accepts either a comma-separated string or a list and returns a clean list[str]."""
    if v is None:
        return []
    if isinstance(v, str):
        return [t.strip().lower() for t in v.split(",") if t.strip()]
    return [str(t).strip().lower() for t in v if str(t).strip()]


class StationBase(BaseModel):
    name: str = Field(..., max_length=255)
    stream_url: str = Field(..., max_length=1024)
    homepage_url: str | None = None
    favicon_url: str | None = None
    country: str = Field(..., max_length=100)
    country_code: str | None = Field(None, max_length=8)
    latitude: float | None = None
    longitude: float | None = None
    language: str | None = Field(None, max_length=100)
    tags: list[str] = []
    codec: str = "MP3"
    bitrate: int = 128

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: list[str] | str | None) -> list[str]:
        return _normalize_tags(v)


class StationCreate(StationBase):
    pass


class StationUpdate(BaseModel):
    name: str | None = None
    stream_url: str | None = None
    homepage_url: str | None = None
    favicon_url: str | None = None
    country: str | None = None
    country_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    language: str | None = None
    tags: list[str] | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: list[str] | str | None) -> list[str] | None:
        return None if v is None else _normalize_tags(v)


class StationStreamRead(BaseModel):
    id: int
    stream_url: str
    codec: str = "MP3"
    bitrate: int = 128
    is_primary: bool = True
    is_active: bool = True
    response_time_ms: int | None = None

    model_config = ConfigDict(from_attributes=True)


class StationRead(StationBase):
    id: int
    station_uuid: str | None = None
    is_active: bool = True
    last_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    streams: list[StationStreamRead] = []

    model_config = ConfigDict(from_attributes=True)


class StationQuery(BaseModel):
    genres: str | None = Field(None, description="Comma-separated genres, e.g. jazz,rock")
    languages: str | None = Field(None, description="Comma-separated allowed languages")
    country: str | None = None
    search: str | None = None
    limit: int = Field(50, ge=1, le=3000)
    offset: int = Field(0, ge=0)
