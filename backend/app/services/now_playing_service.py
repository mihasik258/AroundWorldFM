import logging
import re
import urllib.parse

import httpx

from app.core.cache import TTLCache
from app.core.config import settings
from app.core.net import UnsafeURLError, outbound_client

logger = logging.getLogger(__name__)

ICY_TIMEOUT_SECONDS = 4.0
MAX_METAINT = 65536
JUNK_TITLES = {"", "-", "--", "unknown", "various artists", "ad", "advert", "advertisement"}
_SERVICE_TITLE_RE = re.compile(
    r"^(ad[\s_-]*(trigger|break|block|insert)|adv?ert\w*|commercial( break)?|jingle|station id|"
    r"spot|promo)$",
    re.IGNORECASE,
)
_STREAM_TITLE_RE = re.compile(r"StreamTitle='(.*?)';", re.DOTALL)
_BRACKETS_RE = re.compile(r"\[.*?\]|\(.*?\)")

now_playing_cache = TTLCache(ttl=settings.NOW_PLAYING_CACHE_TTL_SECONDS, max_entries=4096)


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def parse_stream_title(raw_title: str) -> dict | None:
    raw_title = raw_title.strip()
    if raw_title.lower() in JUNK_TITLES:
        return None
    artist, sep, title = raw_title.partition(" - ")
    if not sep:
        artist, title = "", raw_title
    artist, title = artist.strip(), title.strip()
    if _SERVICE_TITLE_RE.match(title) or (artist and artist.lower() == title.lower()):
        return None
    query = _BRACKETS_RE.sub("", f"{artist} {title}".strip()).strip()
    return {
        "raw_title": raw_title,
        "artist": artist or None,
        "title": title or None,
        "spotify_url": f"https://open.spotify.com/search/{urllib.parse.quote(query)}"
        if query
        else None,
    }


async def read_icy_title(stream_url: str) -> str | None:
    async with (
        outbound_client(ICY_TIMEOUT_SECONDS, headers={"Icy-MetaData": "1"}) as client,
        client.stream("GET", stream_url) as resp,
    ):
        if resp.status_code != 200:
            return None
        metaint_raw = resp.headers.get("icy-metaint", "")
        if not metaint_raw.isdigit():
            return None
        metaint = int(metaint_raw)
        if not 0 < metaint <= MAX_METAINT:
            return None

        buf = bytearray()
        meta_len: int | None = None
        async for chunk in resp.aiter_bytes():
            buf.extend(chunk)
            if meta_len is None and len(buf) > metaint:
                meta_len = buf[metaint] * 16
                if meta_len == 0:
                    return None
            if meta_len is not None and len(buf) >= metaint + 1 + meta_len:
                block = bytes(buf[metaint + 1 : metaint + 1 + meta_len]).rstrip(b"\x00")
                match = _STREAM_TITLE_RE.search(_decode(block))
                return match.group(1) if match else None
        return None


class NowPlayingService:
    @staticmethod
    async def get_now_playing(station_id: int, stream_url: str) -> dict:
        async def load() -> dict:
            parsed = None
            try:
                title = await read_icy_title(stream_url)
                parsed = parse_stream_title(title) if title else None
            except (httpx.HTTPError, UnsafeURLError, OSError) as exc:
                logger.debug("Now playing unavailable for station %s: %r", station_id, exc)
            return {
                "station_id": station_id,
                "has_track": parsed is not None,
                "raw_title": parsed["raw_title"] if parsed else None,
                "artist": parsed["artist"] if parsed else None,
                "title": parsed["title"] if parsed else None,
                "spotify_url": parsed["spotify_url"] if parsed else None,
            }

        return await now_playing_cache.get_or_set(station_id, load)
