from httpx import AsyncClient, Response

from app.core.config import settings

API = "/api/v1"


async def login(
    client: AsyncClient,
    login: str = "testuser",
    password: str = "Password123!",
    user_agent: str | None = None,
) -> Response:
    headers = {"User-Agent": user_agent} if user_agent else {}
    res = await client.post(
        f"{API}/auth/login", json={"login": login, "password": password}, headers=headers
    )
    assert res.status_code == 200, res.text
    return res


def refresh_cookie(res: Response) -> str | None:
    """The refresh token set by a response, or None if it set no new cookie."""
    return res.cookies.get(settings.REFRESH_COOKIE_NAME)


def cookie_header(refresh_token: str) -> dict[str, str]:
    # The cookie is Secure and the test client talks plain http, so the cookie
    # jar would never send it — pass it explicitly, the way a browser would.
    return {"Cookie": f"{settings.REFRESH_COOKIE_NAME}={refresh_token}"}


def bearer(res: Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def refresh(client: AsyncClient, refresh_token: str) -> Response:
    return await client.post(f"{API}/auth/refresh", headers=cookie_header(refresh_token))
