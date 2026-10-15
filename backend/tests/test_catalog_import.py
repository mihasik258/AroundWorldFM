from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.models.station import Station, StationStream, StreamHealth
from app.services import catalog_import
from app.services.catalog_import import (
    build_candidate,
    canonical_tags,
    country_cap,
    scatter_around,
)
from app.services.stream_checker import due_streams_query

COUNTRIES = {
    "KE": {
        "name": "Kenya",
        "continent": "AF",
        "area_km2": 580367.0,
        "lat": -1.2833,
        "lon": 36.8167,
    },
    "MT": {"name": "Malta", "continent": "EU", "area_km2": 316.0, "lat": 35.8997, "lon": 14.5147},
}


def raw(**overrides):
    base = {
        "stationuuid": "uuid-1",
        "name": "Nairobi One",
        "url_resolved": "https://stream.example.com/live",
        "countrycode": "KE",
        "codec": "MP3",
        "bitrate": 128,
        "lastcheckok": 1,
        "hls": 0,
        "tags": "afrobeat,dance",
        "language": "swahili,english",
        "clickcount": 50,
        "votes": 3,
        "geo_lat": None,
        "geo_long": None,
    }
    return {**base, **overrides}


def test_country_cap_scales_with_area():
    assert country_cap(9_800_000) == 110
    assert country_cap(357_000) == 21
    assert country_cap(316) == 3
    assert country_cap(17_000_000) == 120


def test_scatter_is_deterministic_and_near_capital():
    a = scatter_around(-1.28, 36.82, 580_367, "uuid-1")
    assert a == scatter_around(-1.28, 36.82, 580_367, "uuid-1")
    assert a != scatter_around(-1.28, 36.82, 580_367, "uuid-2")
    assert abs(a[0] + 1.28) < 1.3
    assert abs(a[1] - 36.82) < 1.4


def test_canonical_tags_keep_vibe_keywords_first():
    tags = canonical_tags(",".join(f"t{i}" for i in range(30)) + ",Smooth Jazz Music", "X")
    assert "jazz" in tags
    assert len(tags) == 20


def test_candidate_without_coordinates_is_placed_in_capital_area():
    c = build_candidate(raw(), COUNTRIES)
    assert not isinstance(c, str)
    assert not c.precise
    assert c.language == "swahili"
    assert "afrobeat" in c.tags


def test_candidate_with_coordinates_is_exact():
    c = build_candidate(raw(geo_lat=-4.05, geo_long=39.66), COUNTRIES)
    assert not isinstance(c, str)
    assert c.precise
    assert (c.latitude, c.longitude) == (-4.05, 39.66)


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"url_resolved": "http://stream.example.com/live"}, "not_https"),
        ({"url_resolved": "https://x.example/live.m3u8"}, "hls"),
        ({"lastcheckok": 0}, "offline"),
        ({"codec": "OGG"}, "codec"),
        ({"bitrate": 24}, "low_bitrate"),
        ({"tags": "news,talk"}, "talk"),
        ({"name": "Radio Futbol 24"}, "talk"),
        ({"tags": "pop"}, "no_vibe"),
        ({"countrycode": "ZZ"}, "no_country"),
    ],
)
def test_candidate_rejections(overrides, reason):
    assert build_candidate(raw(**overrides), COUNTRIES) == reason


def test_untagged_allowed_only_for_sparse_countries():
    untagged = raw(tags="")
    assert build_candidate(untagged, COUNTRIES) == "no_vibe"
    c = build_candidate(untagged, COUNTRIES, allow_untagged=True)
    assert not isinstance(c, str)
    assert c.tags == ["world"]
    tagged = build_candidate(raw(), COUNTRIES, allow_untagged=True)
    assert tagged.score > c.score


@pytest.mark.asyncio
async def test_collect_and_save(db_session, monkeypatch):
    monkeypatch.setattr(catalog_import, "load_countries", lambda: COUNTRIES)
    db_session.add(
        Station(
            name="Existing Malta",
            country="Malta",
            country_code="MT",
            latitude=35.9,
            longitude=14.5,
            tags=["jazz"],
            streams=[StationStream(stream_url="https://mt.example/1", is_primary=True)],
        )
    )
    await db_session.commit()

    kenya = [
        raw(
            stationuuid=f"ke-{i}",
            name=f"Kenya {i}",
            url_resolved=f"https://ke.example/{i}",
            clickcount=i,
        )
        for i in range(40)
    ]
    kenya.append(raw(stationuuid="dup", name="Kenya 3", url_resolved="https://ke.example/other"))
    malta = [
        raw(
            stationuuid=f"mt-{i}",
            name=f"Malta {i}",
            countrycode="MT",
            url_resolved=f"https://mt.example/x{i}",
        )
        for i in range(5)
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"].startswith("AroundFM")
        code = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json={"KE": kenya, "MT": malta}[code])

    report = await catalog_import.collect(
        db_session, ["KE", "MT"], transport=httpx.MockTransport(handler)
    )
    assert report.by_country["KE"] == country_cap(580_367.0)
    assert report.by_country["MT"] == 2
    assert report.rejected["duplicate"] == 1
    assert report.selected[0].name == "Kenya 39"

    saved = await catalog_import.save(db_session, report.selected)
    assert saved == len(report.selected)
    rows = (
        await db_session.execute(
            select(Station.location_precision, StreamHealth.is_active)
            .join(StationStream, StationStream.station_id == Station.id)
            .join(StreamHealth, StreamHealth.stream_id == StationStream.id)
            .where(Station.country_code == "KE")
        )
    ).all()
    assert set(rows) == {("country", False)}


@pytest.mark.asyncio
async def test_failed_country_is_reported(db_session, monkeypatch):
    monkeypatch.setattr(catalog_import, "load_countries", lambda: COUNTRIES)
    transport = httpx.MockTransport(lambda r: httpx.Response(503))
    report = await catalog_import.collect(db_session, ["KE"], transport=transport)
    assert report.failed_countries == ["KE"]


@pytest.mark.asyncio
async def test_due_streams_prioritise_unchecked(db_session):
    now = datetime.now(UTC)

    def station(name, is_active, checked_at):
        return Station(
            name=name,
            country="X",
            tags=[],
            streams=[
                StationStream(
                    stream_url=f"https://s.example/{name}",
                    is_primary=True,
                    health=StreamHealth(
                        is_active=is_active, check_fail_count=0, last_checked_at=checked_at
                    ),
                )
            ],
        )

    db_session.add_all(
        [
            station("fresh-active", True, now - timedelta(hours=1)),
            station("stale-active", True, now - timedelta(hours=7)),
            station("fresh-dead", False, now - timedelta(hours=2)),
            station("stale-dead", False, now - timedelta(hours=30)),
            station("pending", False, None),
        ]
    )
    await db_session.commit()
    streams = (await db_session.execute(due_streams_query(10, now))).scalars().all()
    names = [s.stream_url.rsplit("/", 1)[-1] for s in streams]
    assert names == ["pending", "stale-dead", "stale-active"]
