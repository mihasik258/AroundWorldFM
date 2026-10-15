import asyncio
import hashlib
import json
import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.net import USER_AGENT, UnsafeURLError, optional_http_url, validate_http_url
from app.models.station import Station, StationStream, StreamHealth
from app.services.catalog_normalize import normalize_language
from app.services.vibe_service import CHATTER_KEYWORDS, VIBE_KEYWORDS, infer_vibes

logger = logging.getLogger(__name__)

COUNTRIES_FILE = Path(__file__).resolve().parent.parent / "data" / "countries.json"
RADIO_BROWSER_URL = "https://all.api.radio-browser.info"
PLAYABLE_CODECS = {"MP3", "AAC", "AAC+"}
MIN_BITRATE = 48
CAP_FACTOR = 0.035
CAP_MIN = 3
CAP_MAX = 120
MAX_TAGS = 20
REQUEST_PAUSE_SECONDS = 0.3

ALL_VIBE_KEYWORDS = sorted(
    {kw for kws in VIBE_KEYWORDS.values() for kw in kws}, key=len, reverse=True
)


@lru_cache(maxsize=1)
def load_countries() -> dict[str, dict[str, Any]]:
    return json.loads(COUNTRIES_FILE.read_text(encoding="utf-8"))


def country_cap(area_km2: float) -> int:
    return max(CAP_MIN, min(CAP_MAX, round(CAP_FACTOR * math.sqrt(max(area_km2, 0.0)))))


def _hash_unit(key: str, salt: str) -> float:
    digest = hashlib.sha256(f"{salt}:{key}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def scatter_around(lat: float, lon: float, area_km2: float, key: str) -> tuple[float, float]:
    radius_deg = min(1.2, 0.12 + 0.0004 * math.sqrt(max(area_km2, 0.0)))
    distance = radius_deg * math.sqrt(_hash_unit(key, "r"))
    angle = 2 * math.pi * _hash_unit(key, "a")
    new_lat = max(-89.0, min(89.0, lat + distance * math.sin(angle)))
    cos_lat = max(0.2, math.cos(math.radians(lat)))
    new_lon = lon + distance * math.cos(angle) / cos_lat
    new_lon = (new_lon + 180) % 360 - 180
    return round(new_lat, 4), round(new_lon, 4)


def canonical_tags(raw_tags: str, name: str) -> list[str]:
    text = f"{raw_tags or ''} {name}".lower()
    matched = sorted({kw for kw in ALL_VIBE_KEYWORDS if kw in text})
    own = sorted(
        {t.strip().lower()[:64] for t in (raw_tags or "").split(",") if t.strip()} - set(matched)
    )
    return (matched + own)[:MAX_TAGS]


def is_chatter(raw_tags: str, name: str) -> bool:
    text = f"{raw_tags or ''} {name}".lower()
    return any(kw in text for kw in CHATTER_KEYWORDS)


@dataclass
class Candidate:
    uuid: str
    name: str
    stream_url: str
    country_code: str
    country: str
    latitude: float
    longitude: float
    precise: bool
    language: str | None
    tags: list[str]
    codec: str
    bitrate: int
    homepage_url: str | None
    favicon_url: str | None
    score: float


@dataclass
class ImportReport:
    fetched: int = 0
    rejected: Counter = field(default_factory=Counter)
    selected: list[Candidate] = field(default_factory=list)
    by_continent: Counter = field(default_factory=Counter)
    by_country: Counter = field(default_factory=Counter)
    failed_countries: list[str] = field(default_factory=list)


def _https_url(value: Any) -> str | None:
    url = optional_http_url(value)
    return url if url and url.startswith("https://") and len(url) <= 1024 else None


UNTAGGED_TAG = "world"
UNTAGGED_PENALTY = 3.0


def build_candidate(
    raw: dict[str, Any], countries: dict[str, dict[str, Any]], allow_untagged: bool = False
) -> Candidate | str:
    url = str(raw.get("url_resolved") or raw.get("url") or "").strip()
    if not url.startswith("https://"):
        return "not_https"
    try:
        validate_http_url(url)
    except UnsafeURLError:
        return "bad_url"
    if len(url) > 1024:
        return "bad_url"
    if raw.get("hls") == 1 or ".m3u8" in url.lower():
        return "hls"
    if raw.get("lastcheckok") != 1:
        return "offline"
    codec = str(raw.get("codec") or "").upper()
    if codec not in PLAYABLE_CODECS:
        return "codec"
    bitrate = int(raw.get("bitrate") or 0)
    if 0 < bitrate < MIN_BITRATE:
        return "low_bitrate"
    name = " ".join(str(raw.get("name") or "").split())[:255]
    if len(name) < 2:
        return "no_name"
    tags_raw = str(raw.get("tags") or "")
    if is_chatter(tags_raw, name):
        return "talk"
    tagged = bool(infer_vibes(tags_raw, name))
    if not tagged and not (allow_untagged and not tags_raw.strip()):
        return "no_vibe"
    cc = str(raw.get("countrycode") or "").upper()
    country = countries.get(cc)
    if country is None:
        return "no_country"

    uuid = str(raw.get("stationuuid") or url)
    lat, lon = raw.get("geo_lat"), raw.get("geo_long")
    if (
        isinstance(lat, int | float)
        and isinstance(lon, int | float)
        and -90 <= lat <= 90
        and -180 <= lon <= 180
        and (lat, lon) != (0, 0)
    ):
        precise = True
        latitude, longitude = round(float(lat), 4), round(float(lon), 4)
    else:
        precise = False
        latitude, longitude = scatter_around(
            country["lat"], country["lon"], country["area_km2"], uuid
        )

    languages = [lang for lang in str(raw.get("language") or "").split(",") if lang.strip()]
    clicks = int(raw.get("clickcount") or 0)
    votes = int(raw.get("votes") or 0)
    trend = int(raw.get("clicktrend") or 0)
    score = 2 * math.log1p(clicks) + math.log1p(votes) + 0.5 * math.log1p(max(trend, 0))
    score += 0.5 if precise else 0.0
    score -= 0.0 if tagged else UNTAGGED_PENALTY

    return Candidate(
        uuid=uuid[:64],
        name=name,
        stream_url=url,
        country_code=cc,
        country=country["name"][:100],
        latitude=latitude,
        longitude=longitude,
        precise=precise,
        language=normalize_language(languages[0]) if languages else None,
        tags=canonical_tags(tags_raw, name) if tagged else [UNTAGGED_TAG],
        codec=codec,
        bitrate=bitrate or 128,
        homepage_url=_https_url(raw.get("homepage")),
        favicon_url=_https_url(raw.get("favicon")),
        score=score,
    )


async def fetch_country(
    client: httpx.AsyncClient, base_url: str, country_code: str, limit: int
) -> list[dict[str, Any]]:
    resp = await client.get(
        f"{base_url}/json/stations/bycountrycodeexact/{country_code}",
        params={
            "hidebroken": "true",
            "order": "clickcount",
            "reverse": "true",
            "limit": str(limit),
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


async def _existing(db: AsyncSession) -> tuple[set[str], set[str], set[tuple[str, str]], Counter]:
    uuids = {u for u in (await db.execute(select(Station.station_uuid))).scalars() if u is not None}
    urls = set((await db.execute(select(StationStream.stream_url))).scalars())
    names = {
        (str(n).lower(), str(c or "").upper())
        for n, c in (await db.execute(select(Station.name, Station.country_code))).all()
    }
    rows = await db.execute(
        select(Station.country_code, func.count(Station.id))
        .where(Station.country_code.isnot(None))
        .group_by(Station.country_code)
    )
    per_country = Counter({cc.upper(): n for cc, n in rows.all()})
    return uuids, urls, names, per_country


async def collect(
    db: AsyncSession,
    country_codes: list[str] | None = None,
    per_country_fetch: int = 300,
    base_url: str = RADIO_BROWSER_URL,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ImportReport:
    countries = load_countries()
    codes = sorted(country_codes or countries.keys())
    uuids, urls, names, per_country = await _existing(db)
    report = ImportReport()

    async with httpx.AsyncClient(
        timeout=30.0, headers={"User-Agent": USER_AGENT}, transport=transport, trust_env=False
    ) as client:
        for index, cc in enumerate(codes):
            if cc not in countries:
                continue
            if index:
                await asyncio.sleep(REQUEST_PAUSE_SECONDS if transport is None else 0)
            try:
                raw_stations = await fetch_country(client, base_url, cc, per_country_fetch)
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("Radio Browser fetch failed for %s: %r", cc, exc)
                report.failed_countries.append(cc)
                continue
            report.fetched += len(raw_stations)

            cap = country_cap(countries[cc]["area_km2"])
            room = cap - per_country.get(cc, 0)
            sparse = per_country.get(cc, 0) < cap // 2
            if room <= 0:
                report.rejected["country_full"] += len(raw_stations)
                continue

            candidates: list[Candidate] = []
            for raw in raw_stations:
                built = build_candidate(raw, countries, allow_untagged=sparse)
                if isinstance(built, str):
                    report.rejected[built] += 1
                    continue
                name_key = (built.name.lower(), built.country_code)
                if built.uuid in uuids or built.stream_url in urls or name_key in names:
                    report.rejected["duplicate"] += 1
                    continue
                uuids.add(built.uuid)
                urls.add(built.stream_url)
                names.add(name_key)
                candidates.append(built)

            candidates.sort(key=lambda c: c.score, reverse=True)
            chosen = candidates[:room]
            report.rejected["over_cap"] += len(candidates) - len(chosen)
            report.selected.extend(chosen)
            report.by_country[cc] += len(chosen)
            report.by_continent[countries[cc]["continent"]] += len(chosen)
    return report


async def save(db: AsyncSession, candidates: list[Candidate]) -> int:
    for c in candidates:
        db.add(
            Station(
                station_uuid=c.uuid,
                name=c.name,
                homepage_url=c.homepage_url,
                favicon_url=c.favicon_url,
                country=c.country,
                country_code=c.country_code,
                latitude=c.latitude,
                longitude=c.longitude,
                location_precision="exact" if c.precise else "country",
                language=c.language,
                tags=c.tags,
                streams=[
                    StationStream(
                        stream_url=c.stream_url,
                        codec=c.codec,
                        bitrate=c.bitrate,
                        is_primary=True,
                        health=StreamHealth(is_active=False, check_fail_count=0),
                    )
                ],
            )
        )
    await db.commit()
    return len(candidates)
