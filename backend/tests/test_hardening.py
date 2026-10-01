import asyncio
import threading

import pytest
from httpx import AsyncClient

import app.core.security as security
from app.core.cache import TTLCache
from app.models.identity import UserIdentity
from app.models.user import User, UserRole
from app.services.vibe_service import VibeService
from tests.helpers import API, bearer, login


@pytest.fixture
def bcrypt_calls(monkeypatch):
    calls = []
    real = security.verify_password

    def spy(plain, hashed):
        calls.append(threading.get_ident())
        return real(plain, hashed)

    monkeypatch.setattr(security, "verify_password", spy)
    return calls


async def _failed_login(client: AsyncClient, login_name: str):
    res = await client.post(
        f"{API}/auth/login", json={"login": login_name, "password": "WrongPassword!"}
    )
    assert res.status_code == 401
    return res.json()["detail"]


@pytest.mark.asyncio
async def test_bcrypt_runs_off_the_event_loop(client: AsyncClient, create_users, bcrypt_calls):
    await _failed_login(client, "testuser")
    assert len(bcrypt_calls) == 1
    assert bcrypt_calls[0] != threading.get_ident()


@pytest.mark.asyncio
async def test_failed_logins_are_indistinguishable(
    client: AsyncClient, create_users, db_session, bcrypt_calls
):
    no_password = User(username="tguser", email="tg@example.com", role=UserRole.USER)
    db_session.add(no_password)
    await db_session.flush()
    db_session.add(UserIdentity(user_id=no_password.id, provider="telegram", provider_uid="42"))
    await db_session.commit()

    details = [
        await _failed_login(client, "testuser"),
        await _failed_login(client, "no-such-user"),
        await _failed_login(client, "tguser"),
    ]
    assert len(set(details)) == 1
    assert len(bcrypt_calls) == 3


@pytest.mark.asyncio
async def test_unknown_vibe_is_rejected(client: AsyncClient):
    assert (await client.get(f"{API}/stations/vibe/stations?vibe=anything")).status_code == 422
    assert (await client.get(f"{API}/stations/vibe/next?vibe=anything")).status_code == 422
    assert (await client.get(f"{API}/stations/vibe/stations?vibe=coffee")).status_code == 200


@pytest.mark.asyncio
async def test_page_size_is_capped(client: AsyncClient):
    assert (await client.get(f"{API}/stations?limit=201")).status_code == 422
    assert (await client.get(f"{API}/stations?limit=200")).status_code == 200


@pytest.mark.asyncio
async def test_excluded_languages_are_capped(client: AsyncClient):
    many = ",".join(f"lang{i}" for i in range(201))
    res = await client.get(f"{API}/stations/vibe/stations?vibe=coffee&exclude_languages={many}")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_vibe_catalogue_is_cached_and_invalidated(
    client: AsyncClient, create_users, monkeypatch
):
    built = []
    real_build = VibeService.build_vibe_query

    def counting_build(vibe, exclude_languages=None):
        built.append(vibe)
        return real_build(vibe, exclude_languages)

    monkeypatch.setattr(VibeService, "build_vibe_query", staticmethod(counting_build))
    url = f"{API}/stations/vibe/stations?vibe=coffee&exclude_languages=French, german"

    assert (await client.get(url)).json() == []
    await client.get(f"{API}/stations/vibe/stations?vibe=coffee&exclude_languages=german,french")
    await client.get(f"{API}/stations/vibe/next?vibe=coffee&exclude_languages=GERMAN,French")
    assert len(built) == 1

    admin = await login(client, "adminuser", "AdminPassword123!")
    created = await client.post(
        f"{API}/admin/stations",
        headers=bearer(admin),
        json={"name": "Jazz Cafe", "stream_url": "https://example.com/jazz.mp3",
              "country": "France", "latitude": 48.85, "longitude": 2.35, "tags": ["jazz"]},
    )
    assert created.status_code == 201

    names = [s["name"] for s in (await client.get(url)).json()]
    assert names == ["Jazz Cafe"]
    assert len(built) == 2


@pytest.mark.asyncio
async def test_cache_runs_one_producer_for_concurrent_misses():
    cache = TTLCache(ttl=60, max_entries=10)
    calls = 0

    async def slow_producer():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return "value"

    results = await asyncio.gather(*[cache.get_or_set("k", slow_producer) for _ in range(20)])
    assert results == ["value"] * 20
    assert calls == 1


@pytest.mark.asyncio
async def test_cache_expiry_and_eviction():
    cache = TTLCache(ttl=0.05, max_entries=2)

    async def const(v):
        return v

    await cache.get_or_set("a", lambda: const(1))
    await asyncio.sleep(0.06)
    assert await cache.get_or_set("a", lambda: const(2)) == 2

    await cache.get_or_set("b", lambda: const(3))
    await cache.get_or_set("c", lambda: const(4))
    assert await cache.get_or_set("a", lambda: const(5)) == 5


@pytest.mark.asyncio
async def test_cache_does_not_store_value_computed_before_clear():
    cache = TTLCache(ttl=60, max_entries=10)

    async def stale():
        cache.clear()
        return "stale"

    async def fresh():
        return "fresh"

    assert await cache.get_or_set("k", stale) == "stale"
    assert await cache.get_or_set("k", fresh) == "fresh"
