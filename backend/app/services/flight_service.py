import logging
import math
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.flight import Airport, FlightRoute, UserFlightSession
from app.models.station import Station, StationStream, StreamHealth
from app.schemas.flight import (
    FlightTuningResponse,
    PointTuningResponse,
)
from app.services.radio_service import RadioService

logger = logging.getLogger(__name__)
UTC = timezone.utc


INITIAL_AIRPORTS = [
    {
        "iata_code": "BER",
        "icao_code": "EDDB",
        "name": "Berlin Brandenburg Airport",
        "city": "Berlin",
        "country": "Germany",
        "country_code": "DE",
        "latitude": 52.3667,
        "longitude": 13.5033,
        "altitude_m": 148.0,
        "timezone": "Europe/Berlin",
    },
    {
        "iata_code": "JFK",
        "icao_code": "KJFK",
        "name": "John F. Kennedy International Airport",
        "city": "New York",
        "country": "United States",
        "country_code": "US",
        "latitude": 40.6413,
        "longitude": -73.7781,
        "altitude_m": 13.0,
        "timezone": "America/New_York",
    },
    {
        "iata_code": "CDG",
        "icao_code": "LFPG",
        "name": "Charles de Gaulle Airport",
        "city": "Paris",
        "country": "France",
        "country_code": "FR",
        "latitude": 49.0097,
        "longitude": 2.5479,
        "altitude_m": 119.0,
        "timezone": "Europe/Paris",
    },
    {
        "iata_code": "HND",
        "icao_code": "RJTT",
        "name": "Tokyo Haneda Airport",
        "city": "Tokyo",
        "country": "Japan",
        "country_code": "JP",
        "latitude": 35.5494,
        "longitude": 139.7798,
        "altitude_m": 11.0,
        "timezone": "Asia/Tokyo",
    },
    {
        "iata_code": "LHR",
        "icao_code": "EGLL",
        "name": "London Heathrow Airport",
        "city": "London",
        "country": "United Kingdom",
        "country_code": "GB",
        "latitude": 51.4700,
        "longitude": -0.4543,
        "altitude_m": 25.0,
        "timezone": "Europe/London",
    },
    {
        "iata_code": "SIN",
        "icao_code": "WSSS",
        "name": "Singapore Changi Airport",
        "city": "Singapore",
        "country": "Singapore",
        "country_code": "SG",
        "latitude": 1.3644,
        "longitude": 103.9915,
        "altitude_m": 22.0,
        "timezone": "Asia/Singapore",
    },
    {
        "iata_code": "DXB",
        "icao_code": "OMDB",
        "name": "Dubai International Airport",
        "city": "Dubai",
        "country": "United Arab Emirates",
        "country_code": "AE",
        "latitude": 25.2532,
        "longitude": 55.3657,
        "altitude_m": 19.0,
        "timezone": "Asia/Dubai",
    },
    {
        "iata_code": "LAX",
        "icao_code": "KLAX",
        "name": "Los Angeles International Airport",
        "city": "Los Angeles",
        "country": "United States",
        "country_code": "US",
        "latitude": 33.9416,
        "longitude": -118.4085,
        "altitude_m": 38.0,
        "timezone": "America/Los_Angeles",
    },
    {
        "iata_code": "SVO",
        "icao_code": "UUEE",
        "name": "Sheremetyevo International Airport",
        "city": "Moscow",
        "country": "Russia",
        "country_code": "RU",
        "latitude": 55.9726,
        "longitude": 37.4146,
        "altitude_m": 190.0,
        "timezone": "Europe/Moscow",
    },
    {
        "iata_code": "VVO",
        "icao_code": "UHWW",
        "name": "Vladivostok International Airport",
        "city": "Vladivostok",
        "country": "Russia",
        "country_code": "RU",
        "latitude": 43.3990,
        "longitude": 132.1480,
        "altitude_m": 14.0,
        "timezone": "Asia/Vladivostok",
    },
    {
        "iata_code": "EZE",
        "icao_code": "SAEZ",
        "name": "Ministro Pistarini International Airport",
        "city": "Buenos Aires",
        "country": "Argentina",
        "country_code": "AR",
        "latitude": -34.8222,
        "longitude": -58.5358,
        "altitude_m": 20.0,
        "timezone": "America/Argentina/Buenos_Aires",
    },
    {
        "iata_code": "MAD",
        "icao_code": "LEMD",
        "name": "Adolfo Suárez Madrid–Barajas Airport",
        "city": "Madrid",
        "country": "Spain",
        "country_code": "ES",
        "latitude": 40.4839,
        "longitude": -3.5680,
        "altitude_m": 610.0,
        "timezone": "Europe/Madrid",
    },
    {
        "iata_code": "SYD",
        "icao_code": "YSSY",
        "name": "Sydney Kingsford Smith Airport",
        "city": "Sydney",
        "country": "Australia",
        "country_code": "AU",
        "latitude": -33.9461,
        "longitude": 151.1772,
        "altitude_m": 6.0,
        "timezone": "Australia/Sydney",
    },
    {
        "iata_code": "HNL",
        "icao_code": "PHNL",
        "name": "Daniel K. Inouye International Airport",
        "city": "Honolulu",
        "country": "United States",
        "country_code": "US",
        "latitude": 21.3187,
        "longitude": -157.9224,
        "altitude_m": 4.0,
        "timezone": "Pacific/Honolulu",
    },
]

INITIAL_ROUTES = [
    {
        "flight_number": "LH400",
        "airline": "Lufthansa",
        "title": "Berlin → New York (Transatlantic Sunset)",
        "origin_iata": "BER",
        "destination_iata": "JFK",
        "distance_km": 6385.0,
        "real_duration_minutes": 540,
        "cruising_altitude_m": 10800.0,
        "cruising_speed_kmh": 890.0,
        "recommended_vibe": "chill",
        "description": "Cruising over Northern Europe, the British Isles, the vast North Atlantic, and the coast of Nova Scotia into New York.",
        "is_featured": True,
    },
    {
        "flight_number": "AF275",
        "airline": "Air France",
        "title": "Tokyo → Paris (Eurasian Horizon)",
        "origin_iata": "HND",
        "destination_iata": "CDG",
        "distance_km": 9710.0,
        "real_duration_minutes": 870,
        "cruising_altitude_m": 11300.0,
        "cruising_speed_kmh": 910.0,
        "recommended_vibe": "electronic",
        "description": "From neon Tokyo skies across the Japanese sea, Eurasia, the Baltic, and into romantic Paris.",
        "is_featured": True,
    },
    {
        "flight_number": "BA11",
        "airline": "British Airways",
        "title": "London → Singapore (Spice Route Skylink)",
        "origin_iata": "LHR",
        "destination_iata": "SIN",
        "distance_km": 10880.0,
        "real_duration_minutes": 780,
        "cruising_altitude_m": 11000.0,
        "cruising_speed_kmh": 905.0,
        "recommended_vibe": "world_odyssey",
        "description": "Flying past the Alps, the Bosporus, the Arabian Gulf, and the Indian Ocean to Singapore's tropical equator.",
        "is_featured": True,
    },
    {
        "flight_number": "EK215",
        "airline": "Emirates",
        "title": "Dubai → Los Angeles (Polar Oasis Hop)",
        "origin_iata": "DXB",
        "destination_iata": "LAX",
        "distance_km": 13420.0,
        "real_duration_minutes": 980,
        "cruising_altitude_m": 11800.0,
        "cruising_speed_kmh": 895.0,
        "recommended_vibe": "ambient",
        "description": "An ultra-long haul great-circle voyage traversing Scandinavia, Greenland, the Canadian subarctic, and the Sierra Nevada.",
        "is_featured": True,
    },
    {
        "flight_number": "SU1700",
        "airline": "Aeroflot",
        "title": "Moscow → Vladivostok (Great Siberian Skyway)",
        "origin_iata": "SVO",
        "destination_iata": "VVO",
        "distance_km": 6420.0,
        "real_duration_minutes": 500,
        "cruising_altitude_m": 10600.0,
        "cruising_speed_kmh": 880.0,
        "recommended_vibe": "rock",
        "description": "Soaring above the Ural Mountains, endless Siberian taiga, Lake Baikal, and the Sikhote-Alin mountain range to the Pacific Ocean.",
        "is_featured": True,
    },
    {
        "flight_number": "IB6842",
        "airline": "Iberia",
        "title": "Buenos Aires → Madrid (Southern Cross Express)",
        "origin_iata": "EZE",
        "destination_iata": "MAD",
        "distance_km": 10040.0,
        "real_duration_minutes": 735,
        "cruising_altitude_m": 11200.0,
        "cruising_speed_kmh": 900.0,
        "recommended_vibe": "jazz",
        "description": "From the Rio de la Plata across Brazilian coastlines, crossing the equator over the Atlantic, into sunny Madrid.",
        "is_featured": True,
    },
    {
        "flight_number": "UA1",
        "airline": "United Airlines",
        "title": "Los Angeles → Honolulu (Pacific Blue Passage)",
        "origin_iata": "LAX",
        "destination_iata": "HNL",
        "distance_km": 4120.0,
        "real_duration_minutes": 340,
        "cruising_altitude_m": 10500.0,
        "cruising_speed_kmh": 860.0,
        "recommended_vibe": "chill",
        "description": "Endless azure blue waters of the Pacific Ocean beneath endless sunshine, descending onto the island of Oahu.",
        "is_featured": True,
    },
    {
        "flight_number": "QF1",
        "airline": "Qantas",
        "title": "Sydney → Singapore (Southern Outback to Tropics)",
        "origin_iata": "SYD",
        "destination_iata": "SIN",
        "distance_km": 6300.0,
        "real_duration_minutes": 510,
        "cruising_altitude_m": 10900.0,
        "cruising_speed_kmh": 890.0,
        "recommended_vibe": "world_odyssey",
        "description": "Crossing the red deserts of Central Australia and the Timor Sea, landing in lush green Singapore.",
        "is_featured": True,
    },
]


class FlightService:
    @staticmethod
    def slerp_coordinates(
        lat1_deg: float, lon1_deg: float, lat2_deg: float, lon2_deg: float, t: float
    ) -> tuple[float, float]:
        t = max(0.0, min(1.0, float(t)))
        if t <= 0.0:
            return (lat1_deg, lon1_deg)
        if t >= 1.0:
            return (lat2_deg, lon2_deg)

        phi1 = math.radians(lat1_deg)
        lambda1 = math.radians(lon1_deg)
        phi2 = math.radians(lat2_deg)
        lambda2 = math.radians(lon2_deg)

        x1 = math.cos(phi1) * math.cos(lambda1)
        y1 = math.cos(phi1) * math.sin(lambda1)
        z1 = math.sin(phi1)

        x2 = math.cos(phi2) * math.cos(lambda2)
        y2 = math.cos(phi2) * math.sin(lambda2)
        z2 = math.sin(phi2)

        dot = max(-1.0, min(1.0, x1 * x2 + y1 * y2 + z1 * z2))
        omega = math.acos(dot)

        if omega < 1e-6:
            return (lat1_deg, lon1_deg)

        sin_omega = math.sin(omega)
        w1 = math.sin((1.0 - t) * omega) / sin_omega
        w2 = math.sin(t * omega) / sin_omega

        x = w1 * x1 + w2 * x2
        y = w1 * y1 + w2 * y2
        z = w1 * z1 + w2 * z2

        norm = math.sqrt(x * x + y * y + z * z)
        if norm < 1e-9:
            return (lat1_deg, lon1_deg)

        x /= norm
        y /= norm
        z /= norm

        lat = math.degrees(math.asin(max(-1.0, min(1.0, z))))
        lon = math.degrees(math.atan2(y, x))
        return (lat, lon)

    @staticmethod
    def calculate_altitude(cruising_altitude_m: float, t: float) -> float:
        t = max(0.0, min(1.0, float(t)))
        climb_fraction = 0.08
        descent_fraction = 0.08

        if t < climb_fraction:
            progress = t / climb_fraction
            return cruising_altitude_m * math.sin(progress * (math.pi / 2))
        elif t > (1.0 - descent_fraction):
            progress = (1.0 - t) / descent_fraction
            return cruising_altitude_m * math.sin(progress * (math.pi / 2))
        else:
            return cruising_altitude_m

    @classmethod
    async def seed_flight_data(cls, db: AsyncSession) -> None:
        airport_count = (await db.execute(select(func.count(Airport.id)))).scalar_one()
        if airport_count == 0:
            logger.info("Seeding initial airports...")
            for a in INITIAL_AIRPORTS:
                airport = Airport(
                    iata_code=a["iata_code"],
                    icao_code=a.get("icao_code"),
                    name=a["name"],
                    city=a["city"],
                    country=a["country"],
                    country_code=a["country_code"],
                    latitude=a["latitude"],
                    longitude=a["longitude"],
                    altitude_m=a.get("altitude_m", 0.0),
                    timezone=a.get("timezone", "UTC"),
                )
                db.add(airport)
            await db.commit()
            logger.info(f"Seeded {len(INITIAL_AIRPORTS)} airports.")

        airports_res = await db.execute(select(Airport))
        airport_map = {a.iata_code: a.id for a in airports_res.scalars().all()}

        route_count = (await db.execute(select(func.count(FlightRoute.id)))).scalar_one()
        if route_count == 0:
            logger.info("Seeding initial flight routes...")
            for r in INITIAL_ROUTES:
                orig_id = airport_map.get(r["origin_iata"])
                dest_id = airport_map.get(r["destination_iata"])
                if not orig_id or not dest_id:
                    continue

                route = FlightRoute(
                    flight_number=r["flight_number"],
                    airline=r["airline"],
                    title=r["title"],
                    origin_airport_id=orig_id,
                    destination_airport_id=dest_id,
                    distance_km=r["distance_km"],
                    real_duration_minutes=r["real_duration_minutes"],
                    cruising_altitude_m=r.get("cruising_altitude_m", 10600.0),
                    cruising_speed_kmh=r.get("cruising_speed_kmh", 890.0),
                    recommended_vibe=r.get("recommended_vibe", "world_odyssey"),
                    description=r.get("description"),
                    is_featured=r.get("is_featured", True),
                )
                db.add(route)
            await db.commit()
            logger.info(f"Seeded {len(INITIAL_ROUTES)} flight routes.")

    @classmethod
    async def get_routes(cls, db: AsyncSession, featured_only: bool = False) -> list[FlightRoute]:
        stmt = (
            select(FlightRoute)
            .options(
                selectinload(FlightRoute.origin),
                selectinload(FlightRoute.destination),
            )
            .order_by(FlightRoute.is_featured.desc(), FlightRoute.id.asc())
        )
        if featured_only:
            stmt = stmt.where(FlightRoute.is_featured == True)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_route(cls, db: AsyncSession, route_id: int) -> FlightRoute | None:
        stmt = (
            select(FlightRoute)
            .options(
                selectinload(FlightRoute.origin),
                selectinload(FlightRoute.destination),
            )
            .where(FlightRoute.id == route_id)
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def find_closest_station(
        cls, db: AsyncSession, lat: float, lon: float
    ) -> tuple[Station | None, float]:
        dist_expr = (
            6371.0
            * func.acos(
                func.least(
                    1.0,
                    func.greatest(
                        -1.0,
                        func.sin(func.radians(lat)) * func.sin(func.radians(Station.latitude))
                        + func.cos(func.radians(lat))
                        * func.cos(func.radians(Station.latitude))
                        * func.cos(func.radians(Station.longitude) - func.radians(lon)),
                    ),
                )
            )
        ).label("dist_km")

        stmt = (
            select(Station, dist_expr)
            .join(Station.streams)
            .join(StationStream.health)
            .options(selectinload(Station.streams).selectinload(StationStream.health))
            .where(StationStream.is_primary == True, StreamHealth.is_active == True)
            .order_by(dist_expr.asc())
            .limit(1)
        )

        res = await db.execute(stmt)
        row = res.first()
        if not row:
            return (None, 0.0)
        station, dist = row
        return (station, float(dist))

    @staticmethod
    def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        phi1, lam1 = math.radians(lat1), math.radians(lon1)
        phi2, lam2 = math.radians(lat2), math.radians(lon2)
        dphi = phi2 - phi1
        dlam = lam2 - lam1
        a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(max(0.0, a)), math.sqrt(max(0.0, 1.0 - a)))
        return 6371.0 * c

    @classmethod
    async def pick_station_with_hysteresis(
        cls,
        db: AsyncSession,
        lat: float,
        lon: float,
        current_station_id: int | None = None,
    ) -> tuple[Station | None, float]:
        best_station, dist_best_km = await cls.find_closest_station(db, lat, lon)
        chosen_station = best_station
        dist_station_km = dist_best_km

        if current_station_id and best_station and current_station_id != best_station.id:
            curr_stmt = (
                select(Station)
                .options(selectinload(Station.streams).selectinload(StationStream.health))
                .where(Station.id == current_station_id)
            )
            curr_res = await db.execute(curr_stmt)
            curr_st = curr_res.scalar_one_or_none()

            if curr_st and curr_st.latitude is not None and curr_st.longitude is not None:
                dist_curr_km = cls.haversine_distance_km(
                    lat, lon, curr_st.latitude, curr_st.longitude
                )
                if dist_curr_km < 550.0 and (dist_curr_km - dist_best_km) < 220.0:
                    chosen_station = curr_st
                    dist_station_km = dist_curr_km

        return (chosen_station, dist_station_km)

    @classmethod
    async def get_point_tuning(
        cls,
        db: AsyncSession,
        lat: float,
        lon: float,
        current_station_id: int | None = None,
    ) -> PointTuningResponse:
        station, dist_km = await cls.pick_station_with_hysteresis(db, lat, lon, current_station_id)
        return PointTuningResponse(
            lat=round(lat, 5),
            lon=round(lon, 5),
            distance_km=round(dist_km, 1),
            station=RadioService._station_to_read(station) if station else None,
        )

    @classmethod
    async def get_flight_tuning(
        cls,
        db: AsyncSession,
        route_id: int,
        progress_percent: float,
        current_station_id: int | None = None,
    ) -> FlightTuningResponse | None:
        route = await cls.get_route(db, route_id)
        if not route:
            return None

        p = max(0.0, min(100.0, float(progress_percent))) / 100.0
        cur_lat, cur_lon = cls.slerp_coordinates(
            route.origin.latitude,
            route.origin.longitude,
            route.destination.latitude,
            route.destination.longitude,
            p,
        )

        cur_alt = cls.calculate_altitude(route.cruising_altitude_m, p)
        dist_from_origin = round(route.distance_km * p, 1)
        dist_to_dest = round(route.distance_km * (1.0 - p), 1)
        elapsed_min = int(round(route.real_duration_minutes * p))
        remain_min = max(0, route.real_duration_minutes - elapsed_min)

        chosen_station, dist_station_km = await cls.pick_station_with_hysteresis(
            db, cur_lat, cur_lon, current_station_id
        )

        station_read = RadioService._station_to_read(chosen_station) if chosen_station else None

        if p < 0.05:
            region_label = f"Departing {route.origin.city} ({route.origin.iata_code})"
        elif p > 0.95:
            region_label = f"Approaching {route.destination.city} ({route.destination.iata_code})"
        else:
            if chosen_station:
                region_label = f"Over {chosen_station.country} ({round(dist_station_km)} km to {chosen_station.name})"
            else:
                region_label = f"En route to {route.destination.city}"

        return FlightTuningResponse(
            route_id=route.id,
            progress_percent=round(p * 100.0, 2),
            current_lat=round(cur_lat, 5),
            current_lon=round(cur_lon, 5),
            current_altitude_m=round(cur_alt, 1),
            distance_from_origin_km=dist_from_origin,
            distance_to_destination_km=dist_to_dest,
            elapsed_minutes=elapsed_min,
            remaining_minutes=remain_min,
            region_label=region_label,
            station=station_read,
        )

    @classmethod
    async def get_or_create_session(
        cls,
        db: AsyncSession,
        route_id: int,
        session_token: str | None = None,
        user_id: int | None = None,
    ) -> UserFlightSession:
        stmt = select(UserFlightSession).where(UserFlightSession.route_id == route_id)
        if user_id:
            stmt = stmt.where(UserFlightSession.user_id == user_id)
        elif session_token:
            stmt = stmt.where(UserFlightSession.session_token == session_token)
        else:
            stmt = stmt.limit(1)

        stmt = stmt.options(
            selectinload(UserFlightSession.route).selectinload(FlightRoute.origin),
            selectinload(UserFlightSession.route).selectinload(FlightRoute.destination),
        )

        res = await db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session:
            session = UserFlightSession(
                route_id=route_id,
                user_id=user_id,
                session_token=session_token,
                progress_percent=0.0,
                playback_speed=1.0,
                is_paused=False,
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            session = await cls.get_session_by_id(db, session.id)

        return session

    @classmethod
    async def get_session_by_id(cls, db: AsyncSession, session_id: int) -> UserFlightSession | None:
        stmt = (
            select(UserFlightSession)
            .options(
                selectinload(UserFlightSession.route).selectinload(FlightRoute.origin),
                selectinload(UserFlightSession.route).selectinload(FlightRoute.destination),
            )
            .where(UserFlightSession.id == session_id)
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def update_session(
        cls,
        db: AsyncSession,
        session_id: int,
        progress_percent: float,
        playback_speed: float,
        is_paused: bool,
    ) -> UserFlightSession | None:
        session = await cls.get_session_by_id(db, session_id)
        if not session:
            return None
        session.progress_percent = max(0.0, min(100.0, progress_percent))
        session.playback_speed = playback_speed
        session.is_paused = is_paused
        session.last_active_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(session)
        return session
