import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    payload = {
        "email": "newuser@example.com",
        "username": "newuser",
        "password": "SecurePassword123!",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert data["username"] == payload["username"]
    assert "hashed_password" not in data
    assert data["role"] == "user"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_duplicate_fails(client: AsyncClient, create_users):
    payload = {
        "email": "testuser@example.com",  # Already exists
        "username": "unique_name",
        "password": "Password123!",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert "уже зарегистрирован" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, create_users):
    login_payload = {
        "login": "testuser",
        "password": "Password123!",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["username"] == "testuser"
    assert data["role"] == "user"


@pytest.mark.asyncio
async def test_login_wrong_password_fails(client: AsyncClient, create_users):
    login_payload = {
        "login": "testuser",
        "password": "WrongPassword!",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert "Неверный логин или пароль" in response.json()["detail"]
