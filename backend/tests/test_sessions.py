import pytest
from httpx import AsyncClient

from tests.helpers import API, bearer, login, refresh, refresh_cookie


@pytest.mark.asyncio
async def test_session_lifecycle_and_revocation(client: AsyncClient, create_users):
    login_res = await login(client, user_agent="Pytest-Device-1")
    refresh_token = refresh_cookie(login_res)
    auth_headers = bearer(login_res)

    sessions_res = await client.get(f"{API}/auth/sessions", headers=auth_headers)
    assert sessions_res.status_code == 200
    sessions = sessions_res.json()
    assert len(sessions) == 1
    session_id = sessions[0]["id"]
    assert sessions[0]["user_agent"] == "Pytest-Device-1"
    assert sessions[0]["is_current"] is True

    refresh_res = await refresh(client, refresh_token)
    assert refresh_res.status_code == 200
    assert refresh_res.json()["access_token"]
    refresh_token = refresh_cookie(refresh_res)

    revoke_res = await client.delete(f"{API}/auth/sessions/{session_id}", headers=auth_headers)
    assert revoke_res.status_code == 200

    revoked_refresh_res = await refresh(client, refresh_token)
    assert revoked_refresh_res.status_code == 401
    assert "отозвана" in revoked_refresh_res.json()["detail"]


@pytest.mark.asyncio
async def test_revoke_all_sessions(client: AsyncClient, create_users):
    res1 = await login(client)
    res2 = await login(client)

    revoke_all_res = await client.post(f"{API}/auth/sessions/revoke-all", headers=bearer(res1))
    assert revoke_all_res.status_code == 200

    refresh_res = await refresh(client, refresh_cookie(res2))
    assert refresh_res.status_code == 401
