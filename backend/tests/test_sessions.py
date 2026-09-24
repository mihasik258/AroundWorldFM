import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_session_lifecycle_and_revocation(client: AsyncClient, create_users):
    # 1. Login to create a session
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"login": "testuser", "password": "Password123!"},
        headers={"User-Agent": "Pytest-Device-1"},
    )
    assert login_res.status_code == 200
    tokens = login_res.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # 2. View active sessions
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    sessions_res = await client.get("/api/v1/auth/sessions", headers=auth_headers)
    assert sessions_res.status_code == 200
    sessions = sessions_res.json()
    assert len(sessions) >= 1
    session_id = sessions[0]["id"]
    assert sessions[0]["user_agent"] == "Pytest-Device-1"

    # 3. Refresh token works
    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    new_access_token = refresh_res.json()["access_token"]
    assert new_access_token is not None

    # 4. Revoke the session
    revoke_res = await client.delete(f"/api/v1/auth/sessions/{session_id}", headers=auth_headers)
    assert revoke_res.status_code == 200

    # 5. Refresh token must now fail because session was revoked!
    revoked_refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert revoked_refresh_res.status_code == 401
    assert "отозвана" in revoked_refresh_res.json()["detail"]


@pytest.mark.asyncio
async def test_revoke_all_sessions(client: AsyncClient, create_users):
    # Login twice (two devices)
    res1 = await client.post(
        "/api/v1/auth/login", json={"login": "testuser", "password": "Password123!"}
    )
    res2 = await client.post(
        "/api/v1/auth/login", json={"login": "testuser", "password": "Password123!"}
    )
    access_token = res1.json()["access_token"]
    refresh2 = res2.json()["refresh_token"]

    auth_headers = {"Authorization": f"Bearer {access_token}"}

    # Revoke all sessions
    revoke_all_res = await client.post("/api/v1/auth/sessions/revoke-all", headers=auth_headers)
    assert revoke_all_res.status_code == 200

    # Device 2 cannot refresh
    refresh_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh2})
    assert refresh_res.status_code == 401
