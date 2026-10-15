import httpx
import pytest
import respx

from aroundfm_bot.api import (
    AlreadyLinkedError,
    BackendClient,
    BackendError,
    LinkExpiredError,
    NotLinkedError,
)

BASE = "http://backend.test"
STATION = {"id": 5, "name": "Jazz FM", "country": "UK"}


@pytest.fixture
async def api():
    client = BackendClient(BASE, "secret-0123456789abcdef0123456789abcdef")
    yield client
    await client.aclose()


@respx.mock
async def test_now_playing(api):
    respx.get(f"{BASE}/api/v1/stations/vibe/next", params={"vibe": "focus"}).respond(json=STATION)
    respx.get(f"{BASE}/api/v1/stations/5/now-playing").respond(
        json={"artist": "Moby", "title": "Porcelain", "spotify_url": "https://open.spotify.com/x"}
    )
    playing = await api.now_playing("focus")
    assert playing.station.name == "Jazz FM"
    assert playing.title == "Porcelain"


@respx.mock
async def test_now_playing_without_track(api):
    respx.get(f"{BASE}/api/v1/stations/vibe/next").respond(json=STATION)
    respx.get(f"{BASE}/api/v1/stations/5/now-playing").respond(status_code=404)
    playing = await api.now_playing("focus")
    assert playing.title is None


@respx.mock
async def test_now_playing_empty_vibe(api):
    respx.get(f"{BASE}/api/v1/stations/vibe/next").respond(status_code=404)
    assert await api.now_playing("focus") is None


@respx.mock
async def test_backend_down(api):
    respx.get(f"{BASE}/api/v1/stations/vibe/next").mock(side_effect=httpx.ConnectError("x"))
    with pytest.raises(BackendError):
        await api.now_playing("focus")


@respx.mock
async def test_favorites_sends_secret(api):
    route = respx.get(f"{BASE}/api/v1/internal/telegram/users/42/favorites").respond(json=[STATION])
    stations = await api.favorites(42)
    assert stations[0].id == 5
    assert route.calls.last.request.headers["x-bot-secret"].startswith("secret-")


@respx.mock
async def test_favorites_not_linked(api):
    respx.get(f"{BASE}/api/v1/internal/telegram/users/42/favorites").respond(status_code=404)
    with pytest.raises(NotLinkedError):
        await api.favorites(42)


@respx.mock
@pytest.mark.parametrize(
    ("status", "error"), [(410, LinkExpiredError), (409, AlreadyLinkedError), (500, BackendError)]
)
async def test_link_errors(api, status, error):
    respx.post(f"{BASE}/api/v1/internal/telegram/link").respond(status_code=status)
    with pytest.raises(error):
        await api.link("t" * 20, 1, None, None, None)


@respx.mock
async def test_link_success(api):
    route = respx.post(f"{BASE}/api/v1/internal/telegram/link").respond(json={"username": "neo"})
    assert await api.link("t" * 20, 1, "neo_tg", "Neo", None) == "neo"
    assert b'"telegram_id":1' in route.calls.last.request.content


async def test_internal_calls_require_secret():
    client = BackendClient(BASE, None)
    with pytest.raises(BackendError):
        await client.favorites(1)
    with pytest.raises(BackendError):
        await client.link("t" * 20, 1, None, None, None)
    await client.aclose()
