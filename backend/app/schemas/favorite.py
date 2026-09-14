from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.station import StationRead


class FavoriteRead(BaseModel):
    id: int
    station_id: int
    station: StationRead
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FavoriteCreate(BaseModel):
    station_id: int
