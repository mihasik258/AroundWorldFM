import re
import time
import urllib.parse

import httpx

# In-memory cache for live track metadata: station_id -> (timestamp, data)
_METADATA_CACHE: dict[int, tuple[float, dict]] = {}
CACHE_TTL_SECONDS = 20.0


class NowPlayingService:
    @classmethod
    async def get_now_playing(cls, station_id: int, stream_url: str) -> dict:
        """Extracts live track metadata (ICY) from the station stream and formats Spotify search link."""
        now = time.time()
        cached = _METADATA_CACHE.get(station_id)
        if cached and (now - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]

        data = await cls._fetch_icy_metadata(stream_url)
        res = {
            "station_id": station_id,
            "has_track": data is not None,
            "raw_title": data.get("raw_title") if data else None,
            "artist": data.get("artist") if data else None,
            "title": data.get("title") if data else None,
            "spotify_url": data.get("spotify_url") if data else None,
        }

        _METADATA_CACHE[station_id] = (now, res)
        return res

    @staticmethod
    async def _fetch_icy_metadata(stream_url: str) -> dict | None:
        headers = {
            "User-Agent": "AroundFM/2.0 (Mozilla/5.0)",
            "Icy-MetaData": "1",
        }
        try:
            async with httpx.AsyncClient(timeout=3.5, verify=False, trust_env=False) as client:
                async with client.stream("GET", stream_url, headers=headers) as resp:
                    metaint_hdr = resp.headers.get("icy-metaint")
                    if not metaint_hdr or not metaint_hdr.isdigit():
                        return None
                    metaint = int(metaint_hdr)
                    if metaint <= 0 or metaint > 65536:
                        return None

                    # Read up to 2 metaint chunks to catch metadata frame
                    buf = bytearray()
                    target_bytes = metaint * 2 + 512
                    async for chunk in resp.aiter_bytes():
                        buf.extend(chunk)
                        if len(buf) >= target_bytes:
                            break

                    text = buf.decode("latin1", errors="ignore")
                    match = re.search(r"StreamTitle='([^']*)';", text)
                    if not match:
                        return None

                    raw_title = match.group(1).strip()
                    if not raw_title:
                        return None

                    # Clean unwanted tags like "StreamTitle=' - ';" or station ads
                    if raw_title in ["-", "--", "Unknown", "Various Artists", "Ad"]:
                        return None

                    # Split "Artist - Title"
                    artist = ""
                    title = raw_title
                    if " - " in raw_title:
                        parts = raw_title.split(" - ", 1)
                        artist = parts[0].strip()
                        title = parts[1].strip()

                    # Filter out purely station station names if title matches station name
                    clean_query = f"{artist} {title}".strip() if artist else title
                    clean_query = re.sub(r"\[.*?\]|\(.*?\)", "", clean_query).strip()

                    spotify_url = f"https://open.spotify.com/search/{urllib.parse.quote(clean_query)}"

                    return {
                        "raw_title": raw_title,
                        "artist": artist,
                        "title": title,
                        "spotify_url": spotify_url,
                    }
        except Exception:
            return None
