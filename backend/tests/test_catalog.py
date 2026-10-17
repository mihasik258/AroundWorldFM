import pytest
from httpx import AsyncClient

from tests.helpers import API, bearer, login

VALID = {"name": "X FM", "stream_url": "https://example.com/x.mp3", "country": "X"}


@pytest.mark.asyncio
async def test_favorite_unknown_station_is_404(client: AsyncClient, create_users):
    headers = bearer(await login(client))
    res = await client.post(f"{API}/stations/favorites/999999", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_favorite_is_idempotent(client: AsyncClient, create_users, station):
    headers = bearer(await login(client))
    url = f"{API}/stations/favorites/{station.id}"
    assert (await client.post(url, headers=headers)).json()["message"] == "Добавлено"
    assert (await client.post(url, headers=headers)).json()["message"] == "Уже в избранном"
    favs = await client.get(f"{API}/stations/favorites/my", headers=headers)
    assert [s["id"] for s in favs.json()] == [station.id]
    assert (await client.delete(url, headers=headers)).status_code == 200
    assert (await client.delete(url, headers=headers)).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "patch",
    [
        {"stream_url": "javascript:alert(1)"},
        {"stream_url": "file:///etc/passwd"},
        {"homepage_url": "javascript:alert(1)"},
        {"stream_url": "https://user:pass@example.com/x"},
        {"latitude": 91},
        {"longitude": -181},
        {"bitrate": 0},
    ],
)
async def test_station_input_validation(client: AsyncClient, create_users, patch):
    headers = bearer(await login(client, "adminuser", "AdminPassword123!"))
    res = await client.post(f"{API}/admin/stations", headers=headers, json={**VALID, **patch})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_station_update_rejects_null_required(client: AsyncClient, create_users, station):
    headers = bearer(await login(client, "adminuser", "AdminPassword123!"))
    res = await client.patch(
        f"{API}/admin/stations/{station.id}", headers=headers, json={"name": None}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_validation_errors_do_not_echo_input(client: AsyncClient):
    res = await client.post(
        f"{API}/auth/register",
        json={"email": "bad", "username": "ok_name", "password": "SecretValue!"},
    )
    assert res.status_code == 422
    assert "SecretValue!" not in res.text


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    assert (await client.get("/health")).json()["status"] == "ok"
    ready = await client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.headers["x-request-id"]


@pytest.mark.asyncio
async def test_request_id_is_propagated(client: AsyncClient):
    res = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert res.headers["x-request-id"] == "abc-123"
    bad = await client.get("/health", headers={"X-Request-ID": "bad id\nwith newline"})
    assert bad.headers["x-request-id"] != "bad id\nwith newline"
