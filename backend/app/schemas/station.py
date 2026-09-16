from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StationBase(BaseModel):
    name: str = Field(..., max_length=255)
    homepage_url: str | None = None
    favicon_url: str | None = None
    country: str = Field(..., max_length=100)
    country_code: str | None = Field(None, max_length=8)
    latitude: float | None = None
    longitude: float | None = None
    language: str | None = Field(None, max_length=100)
    tags: list[str] = []


class StationStreamCreate(BaseModel):
    stream_url: str = Field(..., max_length=1024)
    codec: str = "MP3"
    bitrate: int = 128
    is_primary: bool = True


class StationCreate(StationBase):
    streams: list[StationStreamCreate] = []


class StationUpdate(BaseModel):
    name: str | None = None
    homepage_url: str | None = None
    favicon_url: str | None = None
    country: str | None = None
    country_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    language: str | None = None
    tags: list[str] | None = None


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
    created_at: datetime
    updated_at: datetime
    streams: list[StationStreamRead] = []

    model_config = ConfigDict(from_attributes=True)


class StationQuery(BaseModel):
    genres: str | None = Field(None, description="Comma-separated genres, e.g. jazz,rock")
    languages: str | None = Field(None, description="Comma-separated allowed languages")
    country: str | None = None
    search: str | None = None
    limit: int = Field(50, ge=1, le=3000)
    offset: int = Field(0, ge=0)
