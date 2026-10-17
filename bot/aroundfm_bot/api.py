from dataclasses import dataclass
from typing import Any

import httpx


class BackendError(Exception):
    pass


class NotLinkedError(BackendError):
    pass


class LinkExpiredError(BackendError):
    pass


class AlreadyLinkedError(BackendError):
    pass


@dataclass(frozen=True)
class Station:
    id: int
    name: str
    country: str


@dataclass(frozen=True)
class NowPlaying:
    station: Station
    artist: str | None
    title: str | None
    spotify_url: str | None


def _station(data: dict[str, Any]) -> Station:
    return Station(id=int(data["id"]), name=str(data["name"]), country=str(data.get("country", "")))


class BackendClient:
    def __init__(self, base_url: str, bot_secret: str | None, timeout: float = 8.0) -> None:
        headers = {"User-Agent": "AroundFM-Bot/2.1"}
        if bot_secret:
            headers["X-Bot-Secret"] = bot_secret
        self._bot_secret = bot_secret
        self._client = httpx.AsyncClient(
            base_url=f"{base_url}/api/v1", timeout=timeout, headers=headers, trust_env=False
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise BackendError(str(exc)) from exc

    async def now_playing(self, vibe: str) -> NowPlaying | None:
        res = await self._request("GET", "/stations/vibe/next", params={"vibe": vibe})
        if res.status_code == 404:
            return None
        if res.status_code != 200:
            raise BackendError(f"vibe/next returned {res.status_code}")
        station = _station(res.json())
        track = await self._request("GET", f"/stations/{station.id}/now-playing")
        data = track.json() if track.status_code == 200 else {}
        return NowPlaying(
            station=station,
            artist=data.get("artist"),
            title=data.get("title"),
            spotify_url=data.get("spotify_url"),
        )

    async def favorites(self, telegram_id: int) -> list[Station]:
        if not self._bot_secret:
            raise BackendError("bot secret is not configured")
        res = await self._request("GET", f"/internal/telegram/users/{telegram_id}/favorites")
        if res.status_code == 404:
            raise NotLinkedError
        if res.status_code != 200:
            raise BackendError(f"favorites returned {res.status_code}")
        return [_station(item) for item in res.json()]

    async def link(
        self,
        token: str,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> str:
        if not self._bot_secret:
            raise BackendError("bot secret is not configured")
        res = await self._request(
            "POST",
            "/internal/telegram/link",
            json={
                "token": token,
                "telegram_id": telegram_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        if res.status_code == 200:
            return str(res.json()["username"])
        if res.status_code in (410, 422):
            raise LinkExpiredError
        if res.status_code == 409:
            raise AlreadyLinkedError
        raise BackendError(f"link returned {res.status_code}")
