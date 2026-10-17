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
    return res.cookies.get(settings.REFRESH_COOKIE_NAME)


def cookie_header(refresh_token: str) -> dict[str, str]:
    return {"Cookie": f"{settings.REFRESH_COOKIE_NAME}={refresh_token}"}


def bearer(res: Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def refresh(client: AsyncClient, refresh_token: str) -> Response:
    return await client.post(f"{API}/auth/refresh", headers=cookie_header(refresh_token))


def telegram_init_data(
    bot_token: str,
    user_id: int = 4242,
    username: str | None = "tg_user",
    first_name: str = "Tele",
    auth_date: int | None = None,
) -> str:
    import hashlib
    import hmac
    import json
    import time
    from urllib.parse import urlencode

    user = {"id": user_id, "first_name": first_name}
    if username:
        user["username"] = username
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAH",
        "user": json.dumps(user, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)
