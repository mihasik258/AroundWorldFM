import pytest
from httpx import AsyncClient

from app.core.config import settings
from tests.helpers import API, bearer, login, telegram_init_data

BOT_TOKEN = "123456:TEST-telegram-bot-token"


@pytest.fixture(autouse=True)
def telegram_enabled(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", BOT_TOKEN)


async def _telegram_user(client: AsyncClient) -> dict:
    res = await client.post(
        f"{API}/auth/telegram", json={"init_data": telegram_init_data(BOT_TOKEN)}
    )
    assert res.status_code == 200
    return bearer(res)


@pytest.mark.asyncio
async def test_cannot_unlink_last_login_method(client: AsyncClient):
    headers = await _telegram_user(client)
    res = await client.delete(f"{API}/users/me/identities/telegram", headers=headers)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_external_user_sets_password_then_unlinks(client: AsyncClient):
    headers = await _telegram_user(client)
    me = (await client.get(f"{API}/users/me", headers=headers)).json()

    res = await client.post(
        f"{API}/users/me/change-password", headers=headers, json={"new_password": "NewPass123!"}
    )
    assert res.status_code == 200, res.text

    pw = await login(client, me["username"], "NewPass123!")
    pw_headers = bearer(pw)
    res = await client.delete(f"{API}/users/me/identities/telegram", headers=pw_headers)
    assert res.status_code == 200
    me = (await client.get(f"{API}/users/me", headers=pw_headers)).json()
    assert me["auth_providers"] == ["password"]


@pytest.mark.asyncio
async def test_change_password_requires_old_one(client: AsyncClient, create_users):
    headers = bearer(await login(client))
    res = await client.post(
        f"{API}/users/me/change-password", headers=headers, json={"new_password": "Another123!"}
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_unlink_unknown_provider(client: AsyncClient, create_users):
    headers = bearer(await login(client))
    res = await client.delete(f"{API}/users/me/identities/github", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_account(client: AsyncClient, create_users):
    headers = bearer(await login(client))
    wrong = await client.request(
        "DELETE", f"{API}/users/me", headers=headers, json={"confirm_username": "nope"}
    )
    assert wrong.status_code == 400
    res = await client.request(
        "DELETE", f"{API}/users/me", headers=headers, json={"confirm_username": "testuser"}
    )
    assert res.status_code == 200
    assert (await client.get(f"{API}/users/me", headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_last_admin_cannot_delete_self(client: AsyncClient, create_users):
    headers = bearer(await login(client, "adminuser", "AdminPassword123!"))
    res = await client.request(
        "DELETE", f"{API}/users/me", headers=headers, json={"confirm_username": "adminuser"}
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_email_is_case_insensitive(client: AsyncClient):
    body = {"email": "Mixed@Example.com", "username": "mixed", "password": "Password123!"}
    assert (await client.post(f"{API}/auth/register", json=body)).status_code == 201
    dup = {**body, "email": "mixed@example.COM", "username": "other"}
    assert (await client.post(f"{API}/auth/register", json=dup)).status_code == 400
    await login(client, "MIXED@example.com", "Password123!")
