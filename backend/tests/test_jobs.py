import json

import httpx
import pytest
from sqlalchemy import func, select

from app.core.jobs import LOCK_STREAM_CHECK, run_exclusive
from app.models.station import Station, StreamHealth
from app.services import stream_checker
from app.services.flight_service import FlightService
from app.services.seed_service import seed_catalog, seed_demo_users


@pytest.mark.asyncio
async def test_stream_check_marks_dead_streams(db_session, station, monkeypatch):
    real = stream_checker.outbound_client
    monkeypatch.setattr(
        stream_checker,
        "outbound_client",
        lambda timeout, **kw: real(
            timeout, transport=httpx.MockTransport(lambda r: httpx.Response(404)), **kw
        ),
    )
    for _ in range(2):
        result = await stream_checker.run_stream_health_check(db_session)
        assert result == {"checked": 1, "alive": 0}
    health = (await db_session.execute(select(StreamHealth))).scalar_one()
    await db_session.refresh(health)
    assert health.is_active is False
    assert health.check_fail_count == 2


@pytest.mark.asyncio
async def test_stream_check_revives_stream(db_session, station, monkeypatch):
    real = stream_checker.outbound_client
    monkeypatch.setattr(
        stream_checker,
        "outbound_client",
        lambda timeout, **kw: real(
            timeout,
            transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"x")),
            **kw,
        ),
    )
    assert (await stream_checker.run_stream_health_check(db_session))["alive"] == 1


@pytest.mark.asyncio
async def test_advisory_lock_is_exclusive():
    entered = []

    async def inner():
        entered.append("inner")

    async def outer():
        entered.append("outer")
        assert await run_exclusive(LOCK_STREAM_CHECK, inner) is False

    assert await run_exclusive(LOCK_STREAM_CHECK, outer) is True
    assert entered == ["outer"]


@pytest.mark.asyncio
async def test_seed_catalog_is_idempotent_and_validates(db_session, tmp_path):
    data = [
        {
            "name": "Good",
            "stream_url": "https://ok.example/a",
            "country": "X",
            "tags": "Jazz, jazz",
        },
        {"name": "Dup", "stream_url": "https://ok.example/a", "country": "X"},
        {"name": "Bad", "stream_url": "javascript:alert(1)", "country": "X"},
        {"name": "Geo", "stream_url": "https://ok.example/b", "country": "X", "latitude": 99},
    ]
    path = tmp_path / "stations.json"
    path.write_text(json.dumps(data))
    assert await seed_catalog(db_session, path) == 2
    assert await seed_catalog(db_session, path) == 0
    stations = (await db_session.execute(select(Station).order_by(Station.id))).scalars().all()
    assert stations[0].tags == ["jazz"]
    assert stations[1].latitude is None


@pytest.mark.asyncio
async def test_seed_demo_users(db_session):
    assert await seed_demo_users(db_session) == 2
    assert await seed_demo_users(db_session) == 0


@pytest.mark.asyncio
async def test_flights(client, db_session, station):
    await FlightService.seed_flight_data(db_session)
    routes = (await client.get("/api/v1/flights/routes")).json()
    assert routes
    route_id = routes[0]["id"]
    assert (await client.get(f"/api/v1/flights/routes/{route_id}")).status_code == 200
    assert (await client.get("/api/v1/flights/routes/99999")).status_code == 404
    tuning = await client.get(f"/api/v1/flights/routes/{route_id}/tuning", params={"progress": 50})
    assert tuning.status_code == 200
    assert -90 <= tuning.json()["current_lat"] <= 90
    point = await client.get("/api/v1/flights/tuning/point", params={"lat": 10, "lon": 20})
    assert point.json()["station"]["id"] == station.id
    count = (await db_session.execute(select(func.count()).select_from(Station))).scalar_one()
    assert count == 1
