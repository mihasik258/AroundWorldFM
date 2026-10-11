import httpx
import pytest
from httpx import AsyncClient

from app.services import now_playing_service
from app.services.now_playing_service import now_playing_cache, read_icy_title
from tests.helpers import API


@pytest.fixture(autouse=True)
def clear_now_playing():
    now_playing_cache.clear()


@pytest.mark.asyncio
async def test_catalog_listing_and_filters(client: AsyncClient, station):
    assert [s["name"] for s in (await client.get(f"{API}/stations")).json()] == ["Test FM"]
    assert (await client.get(f"{API}/stations", params={"genres": "jazz"})).json()
    assert not (await client.get(f"{API}/stations", params={"genres": "metal"})).json()
    assert (await client.get(f"{API}/stations", params={"search": "test"})).json()
    assert (await client.get(f"{API}/stations", params={"country": "testland"})).json()
    assert (await client.get(f"{API}/stations", params={"languages": "english"})).json()
    assert (await client.get(f"{API}/stations/genres")).json() == ["chillout", "jazz"]
    assert (await client.get(f"{API}/stations/languages")).json() == ["english"]
    assert (await client.get(f"{API}/stations/random")).json()["id"] == station.id
    assert (await client.get(f"{API}/stations/{station.id}")).json()["name"] == "Test FM"
    assert (await client.get(f"{API}/stations/999999")).status_code == 404


@pytest.mark.asyncio
async def test_random_without_match_is_404(client: AsyncClient, station):
    res = await client.get(f"{API}/stations/random", params={"genres": "metal"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_vibes(client: AsyncClient, station):
    vibes = (await client.get(f"{API}/stations/vibe/list")).json()
    assert {"id": "focus", "label": "Deep Focus"} in vibes
    stations = (await client.get(f"{API}/stations/vibe/stations", params={"vibe": "focus"})).json()
    assert [s["id"] for s in stations] == [station.id]
    nxt = await client.get(f"{API}/stations/vibe/next", params={"vibe": "focus"})
    assert nxt.json()["id"] == station.id
    excluded = await client.get(
        f"{API}/stations/vibe/next", params={"vibe": "focus", "exclude_languages": "english"}
    )
    assert excluded.status_code == 404
    langs = (await client.get(f"{API}/stations/vibe/languages")).json()
    assert langs == [{"code": "english", "name": "English", "count": 1}]
    bad = await client.get(f"{API}/stations/vibe/next", params={"vibe": "unknown"})
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_too_many_excluded_languages(client: AsyncClient):
    many = ",".join(f"l{i}" for i in range(201))
    res = await client.get(f"{API}/stations/vibe/stations", params={"exclude_languages": many})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_now_playing(client: AsyncClient, station, monkeypatch):
    calls = []

    async def fake_title(url: str) -> str:
        calls.append(url)
        return "Moby - Everloving"

    monkeypatch.setattr(now_playing_service, "read_icy_title", fake_title)
    for _ in range(2):
        res = await client.get(f"{API}/stations/{station.id}/now-playing")
        assert res.json()["artist"] == "Moby"
    assert len(calls) == 1
    assert (await client.get(f"{API}/stations/999/now-playing")).status_code == 404


def _icy_body(title: str, metaint: int = 16) -> bytes:
    meta = f"StreamTitle='{title}';".encode()
    blocks = -(-len(meta) // 16)
    return b"\x00" * metaint + bytes([blocks]) + meta.ljust(blocks * 16, b"\x00") + b"audio"


@pytest.mark.asyncio
async def test_read_icy_title(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["icy-metadata"] == "1"
        return httpx.Response(
            200, headers={"icy-metaint": "16"}, content=_icy_body("Röyksopp - Eple")
        )

    real = now_playing_service.outbound_client
    monkeypatch.setattr(
        now_playing_service,
        "outbound_client",
        lambda timeout, **kw: real(timeout, transport=httpx.MockTransport(handler), **kw),
    )
    assert await read_icy_title("http://93.184.216.34/s") == "Röyksopp - Eple"


@pytest.mark.asyncio
async def test_stream_proxy(client: AsyncClient, station, monkeypatch):
    from app.api.v1 import stations as stations_api

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "audio/aac"}, content=b"AAC" * 100)

    real = stations_api.outbound_client
    monkeypatch.setattr(
        stations_api,
        "outbound_client",
        lambda timeout, **kw: real(timeout, transport=httpx.MockTransport(handler), **kw),
    )
    res = await client.get(f"{API}/stations/{station.id}/stream")
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/aac"
    assert res.content == b"AAC" * 100


@pytest.mark.asyncio
async def test_stream_proxy_upstream_failure(client: AsyncClient, station, monkeypatch):
    from app.api.v1 import stations as stations_api

    real = stations_api.outbound_client
    monkeypatch.setattr(
        stations_api,
        "outbound_client",
        lambda timeout, **kw: real(
            timeout, transport=httpx.MockTransport(lambda r: httpx.Response(503)), **kw
        ),
    )
    assert (await client.get(f"{API}/stations/{station.id}/stream")).status_code == 502
    assert (await client.get(f"{API}/stations/999/stream")).status_code == 404


@pytest.mark.asyncio
async def test_vibe_map_is_compact_and_cacheable(client: AsyncClient, station):
    res = await client.get(f"{API}/stations/vibe/map", params={"vibe": "focus"})
    assert res.status_code == 200
    assert res.json() == {"stations": [[station.id, 10.0, 20.0]]}
    assert "max-age" in res.headers["cache-control"]
    full = await client.get(f"{API}/stations/{station.id}")
    assert full.json()["location_precision"] == "exact"
