import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.identity import UserIdentity
from app.models.station import Station, StationStream, StreamHealth
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

INITIAL_STATIONS = [
    # France
    {
        "name": "FIP Radio",
        "stream_url": "https://icecast.radiofrance.fr/fip-midfi.mp3",
        "homepage_url": "https://www.radiofrance.fr/fip",
        "country": "France",
        "country_code": "FR",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "language": "french",
        "tags": "eclectic,jazz,world,chillout",
        "codec": "MP3",
        "bitrate": 128,
    },
    {
        "name": "France Musique",
        "stream_url": "https://icecast.radiofrance.fr/francemusique-midfi.mp3",
        "homepage_url": "https://www.radiofrance.fr/francemusique",
        "country": "France",
        "country_code": "FR",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "language": "french",
        "tags": "classical,jazz",
        "codec": "MP3",
        "bitrate": 128,
    },
    {
        "name": "Radio Nova",
        "stream_url": "https://novazz.ice.infomaniak.ch/novazz-128.mp3",
        "homepage_url": "https://www.nova.fr",
        "country": "France",
        "country_code": "FR",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "language": "french",
        "tags": "hip hop,world,electronic,funk",
        "codec": "MP3",
        "bitrate": 128,
    },
    # United Kingdom
    {
        "name": "BBC Radio 1",
        "stream_url": "https://stream.live.vc.bbcmedia.co.uk/bbc_radio_one",
        "homepage_url": "https://www.bbc.co.uk/sounds/play/live:bbc_radio_one",
        "country": "United Kingdom",
        "country_code": "GB",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "language": "english",
        "tags": "pop,dance,rock,charts",
        "codec": "MP3",
        "bitrate": 128,
    },
    {
        "name": "BBC Radio 6 Music",
        "stream_url": "https://stream.live.vc.bbcmedia.co.uk/bbc_6music",
        "homepage_url": "https://www.bbc.co.uk/sounds/play/live:bbc_6music",
        "country": "United Kingdom",
        "country_code": "GB",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "language": "english",
        "tags": "rock,alternative,indie,electronic",
        "codec": "MP3",
        "bitrate": 128,
    },
    {
        "name": "Classic FM UK",
        "stream_url": "https://media-ice.musicradio.com/ClassicFMMP3",
        "homepage_url": "https://www.classicfm.com",
        "country": "United Kingdom",
        "country_code": "GB",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "language": "english",
        "tags": "classical",
        "codec": "MP3",
        "bitrate": 128,
    },
    # Germany
    {
        "name": "FluxFM Berlin",
        "stream_url": "https://fluxfm.streamabc.net/flx-fluxfmberlin-mp3-320-8025247",
        "homepage_url": "https://www.fluxfm.de",
        "country": "Germany",
        "country_code": "DE",
        "latitude": 52.5200,
        "longitude": 13.4050,
        "language": "german",
        "tags": "indie,alternative,rock",
        "codec": "MP3",
        "bitrate": 320,
    },
    {
        "name": "ByteFM",
        "stream_url": "https://bytefm.streamabc.net/byte-bytefmhq-mp3-192-3580523",
        "homepage_url": "https://www.byte.fm",
        "country": "Germany",
        "country_code": "DE",
        "latitude": 53.5511,
        "longitude": 9.9937,
        "language": "german",
        "tags": "eclectic,indie,pop,rock",
        "codec": "MP3",
        "bitrate": 192,
    },
    # USA
    {
        "name": "KEXP 90.3 FM Seattle",
        "stream_url": "https://kexp.streamguys1.com/kexp128.mp3",
        "homepage_url": "https://www.kexp.org",
        "country": "United States",
        "country_code": "US",
        "latitude": 47.6062,
        "longitude": -122.3321,
        "language": "english",
        "tags": "indie,rock,alternative,world",
        "codec": "MP3",
        "bitrate": 128,
    },
    {
        "name": "KCRW Eclectic 24",
        "stream_url": "https://kcrw.streamguys1.com/kcrw_192k_mp3_e24_internet_radio",
        "homepage_url": "https://www.kcrw.com",
        "country": "United States",
        "country_code": "US",
        "latitude": 34.0522,
        "longitude": -118.2437,
        "language": "english",
        "tags": "eclectic,indie,electronic,world",
        "codec": "MP3",
        "bitrate": 192,
    },
    {
        "name": "SomaFM: Groove Salad",
        "stream_url": "https://ice1.somafm.com/groovesalad-128-mp3",
        "homepage_url": "https://somafm.com/groovesalad/",
        "country": "United States",
        "country_code": "US",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "language": "english",
        "tags": "ambient,chillout,electronic,downtempo",
        "codec": "MP3",
        "bitrate": 128,
    },
    # Japan
    {
        "name": "Shonan Beach FM 78.9",
        "stream_url": "https://beachfm.out.airtime.pro/beachfm_a",
        "homepage_url": "https://www.beachfm.co.jp",
        "country": "Japan",
        "country_code": "JP",
        "latitude": 35.2974,
        "longitude": 139.5786,
        "language": "japanese",
        "tags": "jazz,chillout,pop",
        "codec": "MP3",
        "bitrate": 128,
    },
    {
        "name": "J-Pop Sakura 17",
        "stream_url": "https://igor.torontocast.com:1025/;",
        "homepage_url": "https://j-pop.torontocast.stream",
        "country": "Japan",
        "country_code": "JP",
        "latitude": 35.6762,
        "longitude": 139.6503,
        "language": "japanese",
        "tags": "pop,j-pop,dance",
        "codec": "MP3",
        "bitrate": 128,
    },
    # Brazil
    {
        "name": "Radio Nova Brasil FM",
        "stream_url": "https://ice.fabricahost.com.br/novabrasilsp",
        "homepage_url": "https://novabrasilfm.com.br",
        "country": "Brazil",
        "country_code": "BR",
        "latitude": -23.5505,
        "longitude": -46.6333,
        "language": "portuguese",
        "tags": "mpb,bossa nova,pop,latin",
        "codec": "MP3",
        "bitrate": 128,
    },
    # Spain
    {
        "name": "Radio 3 RNE",
        "stream_url": "https://rtvelivestream.akamaized.net/rne_r3_main.mp3",
        "homepage_url": "https://www.rtve.es/radio/radio3/",
        "country": "Spain",
        "country_code": "ES",
        "latitude": 40.4168,
        "longitude": -3.7038,
        "language": "spanish",
        "tags": "culture,indie,rock,electronic",
        "codec": "MP3",
        "bitrate": 128,
    },
    {
        "name": "Ibiza Global Radio",
        "stream_url": "https://inforadio.streamguys1.com/live",
        "homepage_url": "https://ibizaglobalradio.com",
        "country": "Spain",
        "country_code": "ES",
        "latitude": 38.9067,
        "longitude": 1.4206,
        "language": "spanish",
        "tags": "electronic,dance,house,techno",
        "codec": "MP3",
        "bitrate": 128,
    },
    # Italy
    {
        "name": "Rai Radio 3 Classica",
        "stream_url": "https://icstream.rai.it/11.mp3",
        "homepage_url": "https://www.raiplaysound.it/radioclassica",
        "country": "Italy",
        "country_code": "IT",
        "latitude": 41.9028,
        "longitude": 12.4964,
        "language": "italian",
        "tags": "classical,opera",
        "codec": "MP3",
        "bitrate": 128,
    },
]





async def seed_initial_data(db: AsyncSession) -> None:
    """Populates database with initial admin user, identities, and curated radio stations."""
    # 1. Seed Admin & Test User if missing
    admin_stmt = select(User).where(User.username == "admin")
    res = await db.execute(admin_stmt)
    if not res.scalar_one_or_none():
        admin_user = User(
            email="admin@aroundfm.org",
            username="admin",
            role=UserRole.ADMIN,
            is_active=True,
        )
        test_user = User(
            email="listener@aroundfm.org",
            username="listener",
            role=UserRole.USER,
            is_active=True,
        )
        db.add_all([admin_user, test_user])
        await db.flush()

        admin_id = UserIdentity(
            user_id=admin_user.id,
            provider="password",
            provider_uid="admin",
            secret_hash=hash_password("Admin12345!"),
        )
        test_id = UserIdentity(
            user_id=test_user.id,
            provider="password",
            provider_uid="listener",
            secret_hash=hash_password("User12345!"),
        )
        db.add_all([admin_id, test_id])
        await db.commit()
        logger.info("Admin ('admin') and demo user ('listener') created successfully.")

    # 2. Seed Stations if table is empty
    count_stmt = select(func.count(Station.id))
    count = (await db.execute(count_stmt)).scalar() or 0
    if count == 0:
        import json
        from pathlib import Path

        data_file = Path(__file__).parent.parent / "data" / "stations_curated.json"
        raw_stations = []
        if data_file.exists():
            try:
                with open(data_file, encoding="utf-8") as f:
                    raw_stations = json.load(f)
                logger.info(f"Loaded {len(raw_stations)} curated stations from {data_file.name}")
            except Exception as e:
                logger.error(f"Failed to load {data_file}: {e}")

        if not raw_stations:
            raw_stations = INITIAL_STATIONS

        for item in raw_stations:
            # Parse tags to list of lowercase strings
            raw_tags = item.get("tags") or ""
            if isinstance(raw_tags, str):
                tag_list = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]
            elif isinstance(raw_tags, list):
                tag_list = [str(t).strip().lower() for t in raw_tags if str(t).strip()]
            else:
                tag_list = []

            station = Station(
                station_uuid=item.get("station_uuid"),
                name=item.get("name", "Unknown Radio"),
                homepage_url=item.get("homepage_url"),
                favicon_url=item.get("favicon_url"),
                country=item.get("country", "Unknown"),
                country_code=item.get("country_code"),
                latitude=item.get("latitude"),
                longitude=item.get("longitude"),
                language=item.get("language"),
                tags=tag_list,
            )
            db.add(station)
            await db.flush()

            stream = StationStream(
                station_id=station.id,
                stream_url=item.get("stream_url", ""),
                codec=item.get("codec", "MP3"),
                bitrate=item.get("bitrate", 128) or 128,
                is_primary=True,
            )
            db.add(stream)
            await db.flush()

            health = StreamHealth(
                stream_id=stream.id,
                is_active=item.get("is_active", True),
                check_fail_count=0,
            )
            db.add(health)

        await db.commit()
        logger.info(f"Seeded {len(raw_stations)} stations into database.")
