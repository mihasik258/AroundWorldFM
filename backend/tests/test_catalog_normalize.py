import pytest
from sqlalchemy import text

from app.services.catalog_normalize import normalize_language, resolve_coordinates
from app.services.now_playing_service import parse_stream_title
from app.services.seed_service import build_station
from tests.conftest import _alembic, test_engine


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("English", "english"),
        ("  American   English ", "english"),
        ("englsih", "english"),
        ("язык: русский", "russian"),
        ("العربية", "arabic"),
        ("Español Internacional", "spanish"),
        ("africa", None),
        ("", None),
        (None, None),
        ("Swahili", "swahili"),
        ("#spanish", "spanish"),
        ("Español Chile", "spanish"),
        ("Português (Brasil)", "portuguese"),
        ("english - twi", "english"),
        ("uzbek،russian", "uzbek"),
        ("Inglés/Portugués/Español", "english"),
        ("finish", "finnish"),
        ("tonga", "tongan"),
        ("willemstad", None),
        ("dutch colombo", None),
    ],
)
def test_normalize_language(raw, expected):
    assert normalize_language(raw) == expected


def test_placeholder_coordinates_resolve_to_capital():
    assert resolve_coordinates("Serbia", 20.0, 0.0) == (44.7866, 20.4489)
    assert resolve_coordinates("World", 20.0, 0.0) == (None, None)
    assert resolve_coordinates("Serbia", 45.0, 20.0) == (45.0, 20.0)
    assert resolve_coordinates("Serbia", None, 0.0) == (None, None)


def test_seed_normalizes_station():
    station = build_station(
        {
            "name": "X",
            "stream_url": "https://ok.example/x",
            "country": "Nepal",
            "latitude": 20,
            "longitude": 0,
            "language": "Bangla",
        }
    )
    assert station.language == "bengali"
    assert (station.latitude, station.longitude) == (27.7172, 85.3240)


@pytest.mark.parametrize(
    "raw",
    ["Ad-Trigger - Ad-Trigger", "Station - Commercial Break", "Radio X - Jingle", "Foo - foo"],
)
def test_service_titles_are_hidden(raw):
    assert parse_stream_title(raw) is None


@pytest.mark.asyncio
async def test_migration_0003_cleans_existing_rows():
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.run_sync(_alembic, "0002", False)
            await conn.execute(
                text(
                    "INSERT INTO stations (name, country, latitude, longitude, language, tags, "
                    "created_at, updated_at) VALUES "
                    "('a', 'Serbia', 20, 0, ' Rus ', '{}', now(), now()), "
                    "('b', 'World', 20, 0, 'Africa', '{}', now(), now()), "
                    "('c', 'France', 48.85, 2.35, 'Francaise', '{}', now(), now())"
                )
            )
            await conn.run_sync(_alembic, "head", True)
            rows = (
                await conn.execute(
                    text("SELECT name, latitude, longitude, language FROM stations ORDER BY name")
                )
            ).all()
        finally:
            await trans.rollback()
    assert rows == [
        ("a", 44.7866, 20.4489, "russian"),
        ("b", None, None, None),
        ("c", 48.85, 2.35, "french"),
    ]


@pytest.mark.asyncio
async def test_migration_0005_maps_languages_to_closed_set():
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.run_sync(_alembic, "0004", False)
            await conn.execute(
                text(
                    "INSERT INTO stations (name, country, language, tags, created_at, updated_at) "
                    "VALUES ('a', 'Chile', 'español chile', '{}', now(), now()), "
                    "('b', 'Curacao', 'willemstad', '{}', now(), now()), "
                    "('c', 'Kenya', 'swahili', '{}', now(), now())"
                )
            )
            await conn.run_sync(_alembic, "head", True)
            rows = (
                await conn.execute(text("SELECT name, language FROM stations ORDER BY name"))
            ).all()
        finally:
            await trans.rollback()
    assert rows == [("a", "spanish"), ("b", None), ("c", "swahili")]
