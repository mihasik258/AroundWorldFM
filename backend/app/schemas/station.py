from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StationBase(BaseModel):
    name: str = Field(..., max_length=512)
    stream_url: str = Field(..., max_length=1024)
    homepage_url: str | None = None
    favicon_url: str | None = None
    country: str = Field(..., max_length=100)
    country_code: str | None = Field(None, max_length=8)
    latitude: float | None = None
    longitude: float | None = None
    language: str | None = Field(None, max_length=100)
    tags: str = Field("", description="Comma-separated tags, e.g. jazz,chillout")
    codec: str = "MP3"
    bitrate: int = 128


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
    tags: str | None = None
    codec: str | None = None
    bitrate: int | None = None
    is_active: bool | None = None


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
    tag_list: list[str] = []
    streams: list[StationStreamRead] = []

    model_config = ConfigDict(from_attributes=True)


class StationQuery(BaseModel):
    genres: str | None = Field(None, description="Comma-separated genres, e.g. jazz,rock")
    languages: str | None = Field(None, description="Comma-separated allowed languages")
    country: str | None = None
    search: str | None = None
    limit: int = Field(50, ge=1, le=3000)
    offset: int = Field(0, ge=0)
