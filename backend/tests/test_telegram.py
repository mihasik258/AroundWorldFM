import time

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.security import TelegramAuthError, verify_telegram_init_data
from tests.helpers import API, bearer, login, telegram_init_data

BOT_TOKEN = "123456:TEST-telegram-bot-token"
BOT_SECRET = "bot-api-secret-for-tests-0123456789abcdef"


@pytest.fixture(autouse=True)
def telegram_enabled(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "aroundfm_bot")
    monkeypatch.setattr(settings, "BOT_API_SECRET", BOT_SECRET)


def test_signature_roundtrip():
    data = verify_telegram_init_data(telegram_init_data(BOT_TOKEN), BOT_TOKEN, 3600)
    assert data["id"] == 4242
    assert data["username"] == "tg_user"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.replace("first_name%22%3A%22Tele", "first_name%22%3A%22Evil"),
        lambda d: d + "&extra=1",
        lambda d: d.split("&hash=")[0],
    ],
)
def test_tampered_init_data_rejected(mutate):
    with pytest.raises(TelegramAuthError):
        verify_telegram_init_data(mutate(telegram_init_data(BOT_TOKEN)), BOT_TOKEN, 3600)


def test_wrong_bot_token_rejected():
    with pytest.raises(TelegramAuthError):
        verify_telegram_init_data(telegram_init_data("999:other"), BOT_TOKEN, 3600)


def test_expired_init_data_rejected():
    old = telegram_init_data(BOT_TOKEN, auth_date=int(time.time()) - 7200)
    with pytest.raises(TelegramAuthError):
        verify_telegram_init_data(old, BOT_TOKEN, 3600)


@pytest.mark.asyncio
async def test_telegram_login_creates_and_reuses_account(client: AsyncClient):
    first = await client.post(
        f"{API}/auth/telegram", json={"init_data": telegram_init_data(BOT_TOKEN)}
    )
    assert first.status_code == 200, first.text
    assert first.cookies.get(settings.REFRESH_COOKIE_NAME)
    me = await client.get(f"{API}/users/me", headers=bearer(first))
    assert me.json()["auth_providers"] == ["telegram"]
    assert me.json()["role"] == "user"

    second = await client.post(
        f"{API}/auth/telegram", json={"init_data": telegram_init_data(BOT_TOKEN)}
    )
    assert second.json()["user_id"] == first.json()["user_id"]


@pytest.mark.asyncio
async def test_telegram_login_rejects_bad_signature(client: AsyncClient):
    res = await client.post(
        f"{API}/auth/telegram", json={"init_data": telegram_init_data("1:wrong")}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_telegram_disabled_returns_404(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", None)
    res = await client.post(
        f"{API}/auth/telegram", json={"init_data": telegram_init_data(BOT_TOKEN)}
    )
    assert res.status_code == 404


async def _link_token(client: AsyncClient) -> tuple[str, dict]:
    headers = bearer(await login(client))
    res = await client.post(f"{API}/users/me/identities/telegram/link", headers=headers)
    assert res.status_code == 200, res.text
    url = res.json()["url"]
    assert url.startswith("https://t.me/aroundfm_bot?start=link_")
    return url.split("start=link_")[1], headers


@pytest.mark.asyncio
async def test_link_via_bot_and_login_into_same_account(client: AsyncClient, create_users):
    token, headers = await _link_token(client)
    bot = {"X-Bot-Secret": BOT_SECRET}
    res = await client.post(
        f"{API}/internal/telegram/link",
        headers=bot,
        json={"token": token, "telegram_id": 4242, "username": "tg_user", "first_name": "Tele"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["username"] == "testuser"

    replay = await client.post(
        f"{API}/internal/telegram/link",
        headers=bot,
        json={"token": token, "telegram_id": 4242},
    )
    assert replay.status_code == 410

    tg = await client.post(
        f"{API}/auth/telegram", json={"init_data": telegram_init_data(BOT_TOKEN)}
    )
    assert tg.json()["user_id"] == create_users["user"].id

    me = await client.get(f"{API}/users/me", headers=headers)
    assert sorted(me.json()["auth_providers"]) == ["password", "telegram"]


@pytest.mark.asyncio
async def test_internal_api_requires_secret(client: AsyncClient, create_users):
    token, _ = await _link_token(client)
    payload = {"token": token, "telegram_id": 1}
    assert (await client.post(f"{API}/internal/telegram/link", json=payload)).status_code == 404
    wrong = {"X-Bot-Secret": "x" * 40}
    res = await client.post(f"{API}/internal/telegram/link", json=payload, headers=wrong)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_telegram_already_linked_elsewhere_conflicts(client: AsyncClient, create_users):
    await client.post(f"{API}/auth/telegram", json={"init_data": telegram_init_data(BOT_TOKEN)})
    token, _ = await _link_token(client)
    res = await client.post(
        f"{API}/internal/telegram/link",
        headers={"X-Bot-Secret": BOT_SECRET},
        json={"token": token, "telegram_id": 4242},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_bot_reads_favorites_of_linked_user(client: AsyncClient, create_users, station):
    token, headers = await _link_token(client)
    bot = {"X-Bot-Secret": BOT_SECRET}
    await client.post(
        f"{API}/internal/telegram/link", headers=bot, json={"token": token, "telegram_id": 77}
    )
    await client.post(f"{API}/stations/favorites/{station.id}", headers=headers)

    res = await client.get(f"{API}/internal/telegram/users/77/favorites", headers=bot)
    assert res.status_code == 200
    assert [s["id"] for s in res.json()] == [station.id]

    unknown = await client.get(f"{API}/internal/telegram/users/78/favorites", headers=bot)
    assert unknown.status_code == 404
