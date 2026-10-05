import jwt
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.models.user import UserRole
from tests.helpers import API, bearer, login

ADMIN_ENDPOINTS = [
    ("GET", "/admin/stats", None),
    ("POST", "/admin/stations", {"name": "X", "stream_url": "https://example.com/x.mp3", "country": "X"}),
    ("PATCH", "/admin/stations/1", {"name": "Y"}),
    ("DELETE", "/admin/stations/1", None),
    ("POST", "/admin/trigger-stream-check", None),
]

USER_ENDPOINTS = [
    ("GET", "/users/me"),
    ("GET", "/auth/sessions"),
    ("GET", "/stations/favorites/my"),
]


async def _admin(client: AsyncClient):
    return await login(client, "adminuser", "AdminPassword123!")


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", ADMIN_ENDPOINTS)
async def test_admin_endpoints_reject_guest(client: AsyncClient, method, path, body):
    res = await client.request(method, f"{API}{path}", json=body)
    assert res.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", ADMIN_ENDPOINTS)
async def test_admin_endpoints_reject_user(client: AsyncClient, create_users, method, path, body):
    user = await login(client)
    res = await client.request(method, f"{API}{path}", json=body, headers=bearer(user))
    assert res.status_code == 403
    assert res.json()["detail"] == "Недостаточно прав"


@pytest.mark.asyncio
async def test_admin_can_manage_stations(client: AsyncClient, create_users):
    headers = bearer(await _admin(client))

    assert (await client.get(f"{API}/admin/stats", headers=headers)).status_code == 200

    created = await client.post(
        f"{API}/admin/stations",
        headers=headers,
        json={"name": "Admin FM", "stream_url": "https://example.com/admin.mp3", "country": "X"},
    )
    assert created.status_code == 201
    station_id = created.json()["id"]

    updated = await client.patch(
        f"{API}/admin/stations/{station_id}", headers=headers, json={"name": "Admin FM 2"}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Admin FM 2"

    assert (await client.delete(f"{API}/admin/stations/{station_id}", headers=headers)).status_code == 200
    assert (await client.post(f"{API}/admin/trigger-stream-check", headers=headers)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", USER_ENDPOINTS)
async def test_user_endpoints_require_login(client: AsyncClient, create_users, method, path):
    assert (await client.request(method, f"{API}{path}")).status_code == 401

    user = await login(client)
    assert (await client.request(method, f"{API}{path}", headers=bearer(user))).status_code == 200


@pytest.mark.asyncio
async def test_registration_always_gives_user_role(client: AsyncClient):
    res = await client.post(
        f"{API}/auth/register",
        json={"email": "r@example.com", "username": "roleseeker", "password": "Password123!",
              "role": "admin"},
    )
    assert res.status_code == 201
    assert res.json()["role"] == "user"


@pytest.mark.asyncio
async def test_role_claim_in_token_is_ignored(client: AsyncClient, create_users):
    user = await login(client)
    payload = jwt.decode(
        user.json()["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    payload["role"] = "admin"
    forged = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    res = await client.get(f"{API}/admin/stats", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_demoted_admin_loses_access_immediately(client: AsyncClient, create_users, db_session):
    headers = bearer(await _admin(client))
    assert (await client.get(f"{API}/admin/stats", headers=headers)).status_code == 200

    admin = create_users["admin"]
    admin.role = UserRole.USER
    await db_session.commit()

    assert (await client.get(f"{API}/admin/stats", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_deactivated_user_is_rejected(client: AsyncClient, create_users, db_session):
    headers = bearer(await login(client))

    user = create_users["user"]
    user.is_active = False
    await db_session.commit()

    res = await client.get(f"{API}/users/me", headers=headers)
    assert res.status_code == 403
