from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.core.config import Settings, settings
from tests.helpers import API, bearer, cookie_header, login, refresh, refresh_cookie


def _cookie_cleared(res) -> bool:
    set_cookie = res.headers.get("set-cookie", "").lower()
    return set_cookie.startswith("refresh_token=") and "max-age=0" in set_cookie


@pytest.mark.asyncio
async def test_refresh_rotates_token(client: AsyncClient, create_users):
    t1 = refresh_cookie(await login(client))

    res = await refresh(client, t1)
    assert res.status_code == 200
    t2 = refresh_cookie(res)
    assert t2 and t2 != t1

    # The new token keeps working, and the new access token is valid
    me = await client.get(f"{API}/users/me", headers=bearer(res))
    assert me.status_code == 200
    assert (await refresh(client, t2)).status_code == 200


@pytest.mark.asyncio
async def test_concurrent_refresh_within_grace_is_not_theft(client: AsyncClient, create_users):
    """Two tabs refresh with the same token at once: the loser must not kill the session."""
    t1 = refresh_cookie(await login(client))

    winner = await refresh(client, t1)
    t2 = refresh_cookie(winner)
    loser = await refresh(client, t1)

    assert loser.status_code == 200
    # No new cookie for the loser: the browser already has t2 from the winner
    assert refresh_cookie(loser) is None
    me = await client.get(f"{API}/users/me", headers=bearer(loser))
    assert me.status_code == 200
    assert (await refresh(client, t2)).status_code == 200


@pytest.mark.asyncio
async def test_refresh_token_reuse_revokes_session(
    client: AsyncClient, create_users, monkeypatch
):
    """A rotated token shown again after the grace window means it was copied."""
    monkeypatch.setattr(settings, "REFRESH_REUSE_GRACE_SECONDS", 0)
    login_res = await login(client)
    t1 = refresh_cookie(login_res)
    t2 = refresh_cookie(await refresh(client, t1))

    stolen = await refresh(client, t1)
    assert stolen.status_code == 401
    assert "повторное использование" in stolen.json()["detail"]

    # The whole session is dead: the legitimate token and access token too
    assert (await refresh(client, t2)).status_code == 401
    me = await client.get(f"{API}/users/me", headers=bearer(login_res))
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_revoked_session_blocks_access_token_immediately(client: AsyncClient, create_users):
    login_res = await login(client)
    headers = bearer(login_res)
    session_id = (await client.get(f"{API}/auth/sessions", headers=headers)).json()[0]["id"]

    revoke = await client.delete(f"{API}/auth/sessions/{session_id}", headers=headers)
    assert revoke.status_code == 200
    assert _cookie_cleared(revoke)  # revoking the current session is a logout

    # The access token is still unexpired, but its session is gone
    me = await client.get(f"{API}/users/me", headers=headers)
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_sessions_list_marks_only_current(client: AsyncClient, create_users):
    dev1 = await login(client, user_agent="Device-1")
    await login(client, user_agent="Device-2")

    sessions = (await client.get(f"{API}/auth/sessions", headers=bearer(dev1))).json()
    assert len(sessions) == 2
    current = [s for s in sessions if s["is_current"]]
    assert len(current) == 1
    assert current[0]["user_agent"] == "Device-1"


@pytest.mark.asyncio
async def test_revoke_all_keeps_current_session(client: AsyncClient, create_users):
    dev1 = await login(client)
    dev2 = await login(client)

    res = await client.post(f"{API}/auth/sessions/revoke-all", headers=bearer(dev1))
    assert res.status_code == 200
    assert "1" in res.json()["message"]

    assert (await client.get(f"{API}/users/me", headers=bearer(dev1))).status_code == 200
    assert (await refresh(client, refresh_cookie(dev1))).status_code == 200
    assert (await client.get(f"{API}/users/me", headers=bearer(dev2))).status_code == 401
    assert (await refresh(client, refresh_cookie(dev2))).status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_session_and_clears_cookie(client: AsyncClient, create_users):
    login_res = await login(client)
    token = refresh_cookie(login_res)

    res = await client.post(f"{API}/auth/logout", headers=cookie_header(token))
    assert res.status_code == 200
    assert _cookie_cleared(res)

    assert (await refresh(client, token)).status_code == 401
    me = await client.get(f"{API}/users/me", headers=bearer(login_res))
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_logout_without_cookie_is_harmless(client: AsyncClient):
    res = await client.post(f"{API}/auth/logout")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_refresh_without_cookie_fails(client: AsyncClient):
    res = await client.post(f"{API}/auth/refresh")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_access_token_must_match_its_session(client: AsyncClient, create_users):
    """A token with no sid, or with another user's session id, is rejected."""
    admin_login = await login(client, "adminuser", "AdminPassword123!")
    admin_sid = jwt.decode(
        admin_login.json()["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )["sid"]
    user_id = create_users["user"].id
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)

    def forge(extra: dict) -> dict:
        payload = {"sub": str(user_id), "type": "access", "exp": exp, **extra}
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return {"Authorization": f"Bearer {token}"}

    assert (await client.get(f"{API}/users/me", headers=forge({}))).status_code == 401
    borrowed = forge({"sid": admin_sid})
    assert (await client.get(f"{API}/users/me", headers=borrowed)).status_code == 401


@pytest.mark.asyncio
async def test_change_password_ends_every_session(client: AsyncClient, create_users):
    login_res = await login(client)
    token = refresh_cookie(login_res)

    res = await client.post(
        f"{API}/users/me/change-password",
        json={"old_password": "Password123!", "new_password": "NewPassword456!"},
        headers=bearer(login_res),
    )
    assert res.status_code == 200
    assert _cookie_cleared(res)

    assert (await client.get(f"{API}/users/me", headers=bearer(login_res))).status_code == 401
    assert (await refresh(client, token)).status_code == 401
    await login(client, password="NewPassword456!")


def test_short_secrets_are_rejected():
    long_enough = "x" * 32
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="too-short", SECRET_PEPPER=long_enough)
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY=long_enough, SECRET_PEPPER="")
    Settings(SECRET_KEY=long_enough, SECRET_PEPPER=long_enough)
