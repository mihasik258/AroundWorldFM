from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.station import StationRead


class AirportBase(BaseModel):
    iata_code: str = Field(..., max_length=3, description="IATA code, e.g. BER, JFK")
    icao_code: str | None = Field(None, max_length=4, description="ICAO code, e.g. EDDB, KJFK")
    name: str = Field(..., max_length=255)
    city: str = Field(..., max_length=128)
    country: str = Field(..., max_length=100)
    country_code: str = Field(..., max_length=4)
    latitude: float
    longitude: float
    altitude_m: float = 0.0
    timezone: str = "UTC"


class AirportCreate(AirportBase):
    pass


class AirportRead(AirportBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FlightRouteBase(BaseModel):
    flight_number: str = Field(..., max_length=16, description="Flight number, e.g. LH400")
    airline: str = Field(..., max_length=128)
    title: str = Field(..., max_length=255)
    distance_km: float
    real_duration_minutes: int
    cruising_altitude_m: float = 10600.0
    cruising_speed_kmh: float = 890.0
    recommended_vibe: str = "world_odyssey"
    description: str | None = None
    is_featured: bool = True
    waypoints: list[dict] | None = None


class FlightRouteCreate(FlightRouteBase):
    origin_airport_id: int
    destination_airport_id: int


class FlightRouteRead(FlightRouteBase):
    id: int
    origin_airport_id: int
    destination_airport_id: int
    created_at: datetime
    origin: AirportRead
    destination: AirportRead

    model_config = ConfigDict(from_attributes=True)


class UserFlightSessionCreate(BaseModel):
    route_id: int
    progress_percent: float = 0.0
    playback_speed: float = 1.0
    is_paused: bool = False
    session_token: str | None = None


class UserFlightSessionRead(BaseModel):
    id: int
    user_id: int | None = None
    session_token: str | None = None
    route_id: int
    progress_percent: float
    playback_speed: float
    is_paused: bool
    started_at: datetime
    last_active_at: datetime
    route: FlightRouteRead

    model_config = ConfigDict(from_attributes=True)


class FlightTuningResponse(BaseModel):
    route_id: int
    progress_percent: float
    current_lat: float
    current_lon: float
    current_altitude_m: float
    distance_from_origin_km: float
    distance_to_destination_km: float
    elapsed_minutes: int
    remaining_minutes: int
    region_label: str
    station: StationRead | None = None


class PointTuningResponse(BaseModel):
    lat: float
    lon: float
    distance_km: float
    station: StationRead | None = None
