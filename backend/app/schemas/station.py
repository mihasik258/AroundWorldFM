from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.core.net import UnsafeURLError, validate_http_url
from app.services.catalog_normalize import normalize_language


def _http_url(value: str) -> str:
    try:
        return validate_http_url(value)
    except UnsafeURLError as exc:
        raise ValueError("must be an http(s) URL") from exc


HttpUrlStr = Annotated[str, Field(max_length=1024), AfterValidator(_http_url)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
Tags = Annotated[list[str], Field(max_length=50)]


def _normalize_tags(v: list[str] | str | None) -> list[str]:
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


def _language(value: str | None) -> str | None:
    language = normalize_language(value)
    if language is None and value and value.strip():
        raise ValueError("unknown language")
    return language


Language = Annotated[str | None, Field(max_length=100), AfterValidator(_language)]


class StationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    stream_url: HttpUrlStr
    homepage_url: HttpUrlStr | None = None
    favicon_url: HttpUrlStr | None = None
    country: str = Field(..., min_length=1, max_length=100)
    country_code: str | None = Field(None, max_length=8)
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    language: Language = None
    tags: Tags = []
    codec: str = Field("MP3", max_length=32)
    bitrate: int = Field(128, ge=8, le=1536)

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: list[str] | str | None) -> list[str]:
        return _normalize_tags(v)


class StationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    stream_url: HttpUrlStr | None = None
    homepage_url: HttpUrlStr | None = None
    favicon_url: HttpUrlStr | None = None
    country: str | None = Field(None, min_length=1, max_length=100)
    country_code: str | None = Field(None, max_length=8)
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    language: Language = None
    tags: Tags | None = None

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
    location_precision: str = "exact"
    is_active: bool = True
    last_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    streams: list[StationStreamRead] = []

    model_config = ConfigDict(from_attributes=True)


class StationMap(BaseModel):
    stations: list[tuple[int, float, float]]


class StationQuery(BaseModel):
    genres: str | None = Field(None, description="Genres")
    languages: str | None = Field(None, description="Languages")
    country: str | None = None
    search: str | None = None
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
